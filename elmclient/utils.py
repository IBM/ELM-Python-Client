##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

import os
import logging
import datetime
import inspect
import base64
import logging
import xml.etree.ElementTree as ET

from . import rdfxml

import cryptography.fernet
import cryptography.hazmat.backends
import cryptography.hazmat.primitives
import cryptography.hazmat.primitives.kdf.pbkdf2

############################################################################
# setup logging

# from https://stackoverflow.com/a/55276759/2318649

import logging
import logging.handlers

import functools

# settings for the rotating logs
LOGFILEROLLOVERSIZE_MIB=50
LOGFILEROLLOVERCOUNT=10

# the TRACE level is between warning and info so the httpops can just log communication with the server without getting all the other info/debug logged
logging.TRACE = 25
logging.addLevelName(logging.TRACE, 'TRACE')
logging.Logger.trace = functools.partialmethod(logging.Logger.log, logging.TRACE)
logging.trace = functools.partial(logging.log, logging.TRACE)

#

logger = logging.getLogger(__name__)

LOGFOLDER = './logs'

loglevels = {
        'DEBUG':        logging.DEBUG
        ,'INFO':        logging.INFO
        ,'TRACE':       logging.TRACE
        ,'WARNING':     logging.WARNING
        ,'ERROR':       logging.ERROR
        ,'CRITICAL':    logging.CRITICAL
        ,'OFF':         None
        }

def setup_logging( *, filelevel=logging.INFO, consolelevel=None ):
    # make sure logs folder exists for logging output
    os.makedirs(LOGFOLDER, exist_ok=True)

    if filelevel is not None or consolelevel is not None:
        # set default logging level
        log = logging.getLogger()  # init the root logger
#        log.setLevel(logging.DEBUG)
        log.setLevel(max(filelevel or 0,consolelevel or 0))
        # make a formatter to use for the file logs
        filelogformatter = logging.Formatter("%(asctime)s [%(levelname)-5s|%(name)s] %(message)s")

        datetimestamp = '{:%Y%m%d-%H%M%S}'.format(datetime.datetime.now())

        if filelevel is not None:
            # file handler gets *all* log messages
# older non-rotating file handler:           handler = logging.FileHandler(os.path.join(LOGFOLDER,f"elmclient-{datetimestamp}.log"), mode='w')  # create a 'log1.log' handler
            handler = logging.handlers.RotatingFileHandler(
                os.path.join(LOGFOLDER,f"elmclient-{datetimestamp}.log"),
                maxBytes = LOGFILEROLLOVERSIZE_MIB*1024*1024,
                backupCount = LOGFILEROLLOVERCOUNT,
                mode='w'
            )
            handler.setLevel(filelevel)  # make sure all levels go to it
            handler.setFormatter(filelogformatter)  # use the above formatter
            log.addHandler(handler)  # add the file handler to the root logger

        if consolelevel is not None:
            # define a Handler which writes messages to the sys.stderr
            console = logging.StreamHandler()
            console.setLevel(consolelevel)
            # set a format which is simpler for console use
            formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
            # tell the handler to use this format
            console.setFormatter(formatter)
            # add the handler to the root logger
            log.addHandler(console)
            
############################################################################

def parsexml(file, stripnamespaces=True):
    # instead of ET.fromstring(xml)
    it = ET.iterparse(file)
    for _, el in it:
        text = (el.text or "").strip()
        tail = (el.tail or "").strip()
        if stripnamespaces:
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]  # strip all namespaces
            for at in list(el.attrib.keys()): # strip namespaces from attributes too
                if '}' in at:
                    newat = at.split('}', 1)[1]
                    el.attrib[newat] = el.attrib[at]
                    del el.attrib[at]
        # sort the children by string
#        print "=================\nsorting",list(el)
        el[:] = sorted(el, key=lambda child: ET.tostring(child))
#        print "sorted",list(el)
    root = it.root
    tree = ET.ElementTree(root)
    return tree

############################################################################

def log_commandline( prog,args=None ):
    args = args or []
    def optquote(s):
        if " " in s:
            return '"s"'
        return s
    arg = " ".join([optquote(a) for a in args])
    logger.trace( f"COMMANDLINE: {prog} {arg}" )

############################################################################

def log_state( statename ):
    logger.trace( f"STATE: {statename}" )

############################################################################
# return string for the n
def nth( n ):
    if n < 1:
        raise Exception( f"nth can't figure out what to return for {n} - should be greater than 0!" )
    if n==1:
        return "1st"
    elif n==2:
        return "2nd"
    elif n==3:
        return "3rd"
    return f"{str(n)}th"
    
############################################################################
# code to support obfuscated credentials files

ITERATIONS = 100000
TTL = 28*24*60*60

def _derive_key( password, salt, iterations=ITERATIONS ):
    kdf =  cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC(
        algorithm=cryptography.hazmat.primitives.hashes.SHA256(), length=32, salt=salt,
        iterations=iterations, backend=cryptography.hazmat.backends.default_backend())
    return base64.urlsafe_b64encode(kdf.derive(password))

def fernet_encrypt( message, password, iterations=ITERATIONS ) :
    salt = os.urandom(16)
    key = _derive_key(password.encode(), salt, iterations)
    return base64.urlsafe_b64encode( b'%b%b%b' % ( salt, iterations.to_bytes(4, 'big'), base64.urlsafe_b64decode( cryptography.fernet.Fernet(key).encrypt(message)), ) )

def fernet_decrypt( token, password, ttl=TTL ):
    decoded = base64.urlsafe_b64decode(token)
    salt, iter, token = decoded[:16], decoded[16:20], base64.urlsafe_b64encode(decoded[20:])
    iterations = int.from_bytes(iter, 'big')
    key = _derive_key(password.encode(), salt, iterations)
    return  cryptography.fernet.Fernet(key).decrypt(token,ttl=ttl)

############################################################################
#
# For Reportable REST
#
# visit an xml tag hierarchy, extracting values into rows, one per first-level tag
# this is aimed at Reportable REST XML output
#
# to avoid duplicate names and map clearly to the XML:
#   the path to a tag is turned into /-separated tag path
#   at a level, all attributes of a tag are added to the tag path with "-attributename"
#
def getcontentrow( node, remove_ns=True ):
    thisrowdict = {}
    allcolumns=[]
    path=""
    row,columns = getacontentrow( node, thisrowdict, allcolumns, 1, path, remove_ns=remove_ns)
    return row

def getacontentrow( node, thisrowdict, allcolumns, level, path, remove_ns=True, merge_duplicates=False ):
    logger.debug( f"2 {node=} {allcolumns=} {thisrowdict=}" )
#    print( f"2 {node=} {allcolumns=} {thisrowdict=} {level=} {path=}" )
    children = list(node)

    # ensure path is unique
    if path in allcolumns:
        # add a digit to get a unique path
        for i in range(1000):
            if f"{path}{i}" not in allcolumns:
                break
        path = f"{path}{i}"
        logger.debug( f"unique1 ============================= {path=}" )
#        print( f"unique1 ============================= {path=}" )
        
    if path not in allcolumns:
        allcolumns.append(path)
        
    logger.debug( f"{path=}" )
#    print( f"{path=}" )
    # record attributes of node
    for k in node.keys():
        # work out the path to this attribute
        if remove_ns and '}' in k:
            k1 = k.split('}',1)[1]
        else:
            k1 = k

        if path:
            kpath = f"{path}-{k1}"
        else:
            kpath = k1
            
        # ensure the path is remembered in allcolumns
        if kpath not in allcolumns:
            allcolumns.append(kpath)
        else:
            logger.debug( f"{kpath=}" )
            raise Exception( "Unexpected {kpath} not in allcolumns" )
            
        # store the value into the row
        thisrowdict[kpath] = node.get(k,"")

    text = (node.text or "").strip()
    tail = (node.tail or "").strip()

    if tail:
        raise Exception("XML has tail - can't handle this!")

    if text or node.tag==f'{{{rdfxml.RDF_DEFAULT_PREFIX["rm_text"]}}}richTextBody':            
        if len(children)>0 and node.tag==f'{{{rdfxml.RDF_DEFAULT_PREFIX["rm_text"]}}}richTextBody':
            # this is a special case - this tag with children contains literal XHTML which we want
            # to use as-is so copy the string version of the text content and don't recurse into it
            thisrowdict[path] = ET.tostring(node)
        else:
            # this is just all the the content
            thisrowdict[path]=text+tail
        # remember paths that have a value stored
    elif len(children)>0:
        # recurse into the children
#        print( f"{children=}" )
        for child in children:
            if remove_ns and '}' in child.tag:
                thistag = child.tag.split('}',1)[1]
            else:
                thistag=child.tag
            subpath = path + "/" + thistag if path !='' else thistag
            # recurse
            getacontentrow( child, thisrowdict, allcolumns, level + 1, subpath, remove_ns=remove_ns)
    else:
        # empty tag
        pass

#    print( f"{thisrowdict=}" )
#    print( f"{allcolumns=}" )
    return (thisrowdict,allcolumns)

#####################################################################################
# return function stack trace of the calling line, as a string of file:function:line<=file:function:ine<=...
def callers():
    caller_list = []
    frame = inspect.currentframe().f_back.f_back
    while frame.f_back:
        caller_list.append('{2}:{1}:{0}()'.format(frame.f_code.co_name,frame.f_lineno,frame.f_code.co_filename.split("\\")[-1]))
        frame = frame.f_back
    callers =  ' <= '.join(caller_list)
    return callers

#####################################################################################
# based on https://stackoverflow.com/a/12065663/2318649
def print_in_columns( rows ):
    result = ""
    colcount = max([len(row) for row in rows])
    rows = [row + ['']*(colcount-len(row)) for row in rows]
    widths = [max(map(len, col)) for col in zip(*rows)]
    # ensure the final column doesn't have spaces added on the end
    widths[-1]=0
    for row in rows:
        result += "  ".join((val.ljust(width) for val, width in zip(row, widths)))+"\n"
    return result

#####################################################################################
# based on https://stackoverflow.com/a/12065663/2318649
def print_in_html( rows,headings=None ):
    result = ""
    if headings is None:
        headings = []
    colcount = max([len(row) for row in rows]) if rows else 0
    # extend all the rows
    if rows:
        rows = [row + ['']*(colcount-len(row)) for row in rows]
    # extend the headings
    headings += ['']*(colcount-len(headings))
    result += "<TABLE><THEADING>\n"
    for heading in headings:
        result += f"<TH>{heading}</TH>"
    result += "</THEADING>\n"
    for row in rows:
        result += "  <TR>"
        for col in row:
            result += f"    <TD>{col}</TD>\n"
        result += "  </TR>\n"
    result += "</TABLE>\n"
    return result

#####################################################################################
# decorator for users of mixin classes - ensures all their __init__ gets called
# based on https://stackoverflow.com/a/6100595/2318649
#
# USE WITH CARE:
#  If the class's __init__ calls super() then super's init will get called twice!
#
def mixinomatic(cls):
    """ Mixed-in class decorator. """
    classinit = cls.__dict__.get('__init__')  # Possibly None.

    # Define an __init__ function for the class.
    def __init__(self, *args, **kwargs):
        # Call the __init__ functions of all the bases.
        for base in cls.__bases__:
            if base is object or ( len(args)==0 and len(kwargs)==0): # added, doesn't pass args to object
                base.__init__(self)
            else:
                logger.debug( f"{base=} {args=} {kwargs=}" )
                base.__init__(self, *args, **kwargs)
        # Also (and finally) call any __init__ function that is in the decorated class.
        if classinit:
            classinit(self, *args, **kwargs)

    # Make the local function the class's __init__.
    setattr(cls, '__init__', __init__)
    return cls

############################################################################

def isint(s ):
    try:
        i = int(s)
    except:
        return None
    return i
    
############################################################################
    
    
def kb_connected():
    # this fix courtesy of wulmer avoids an exception from termios when running in Docker/container
    # of course there's no keyboard attached when in a container, so it's anyway not possible to escape by a keypress :-(
    if not sys.stdin.isatty():
        return False
    return True
    
try:
    # Win32
#    from msvcrt import getch,kbhit
    import msvcrt
    def getch():
        return msvcrt.getch()
    def kbhit():
        result = msvcrt.kbhit()
        return result
except ImportError:
    # UNIX
    import sys
    import tty
    import termios
    import atexit
    import select

    def getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def kbhit():
        if not kb_connected():
            return False
            
        # Save the terminal settings
        fd = sys.stdin.fileno()
        new_term = termios.tcgetattr(fd)
        old_term = termios.tcgetattr(fd)

        # New terminal setting unbuffered
        new_term[3] = (new_term[3] & ~termios.ICANON & ~termios.ECHO)
        termios.tcsetattr(fd, termios.TCSAFLUSH, new_term)
        dr,dw,de = select.select([sys.stdin], [], [], 0)
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
        return dr != []
