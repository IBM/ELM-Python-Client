##
## © Copyright 2025- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# NOTE THIS ONLY WORKS FOR FORM-BASED login, i.e. doesn't work with JAS!

# this a BASIC example because it uses HTTP calls irect to your ELM deployment, i.e. avoids the elmclient APIs, useful if you wan tto see the details of a sequence

#
# RM discovery srequence steps 1-7
# See my new article about using the RM APIs
#
# this code has a simple GET function which logs in if needed
#
# One sophistication is that once authenticated the cookies are saved to file 
# and reloaded before the next operation - so if the auth cookie hasn't expired (usually two hours)
# there won't be any need to redo authentication
#
# Another sophistication is that the GET function logs the request and response in a useful form showing important headers and body
# To reduce cutter uninteresting/irrelevant headers aren't shown
# If the body is XML it's pretty-printed :-) means the Content-Length shown in headers is no longer accurate
#

import logging

import argparse
import codecs
import csv
import html
import os
import pickle
import re
import requests
import socket
import urllib.parse

from elmclient import __meta__
from elmclient import rdfxml

# this code uses lxml (rather than ElementTree) because of its xpath support for using text() 
import lxml.etree as ET

# Disable the InsecureRequestWarning so we can quietly control SSL certificate validation
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# some prefixes need for easy findinbg of tags in ET
prefixes = {
    'dcterms':          'http://purl.org/dc/terms/',
    'oslc':             'http://open-services.net/ns/core#',
    'oslc_config':      'http://open-services.net/ns/config#',
    'rm_config':        'http://jazz.net/ns/rm/dng/config#',
    'oslc_rm':          'http://open-services.net/ns/rm#',
    'rdf':              'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs':             'http://www.w3.org/2000/01/rdf-schema#',
}

# headers which aren't logged, to reduce clutter
ignore_headers = [
    "Accept-Encoding",
    "Connection",
    "Content-Language",
    "User-Agent",
    "Date",
    "Cache-Control",
    "Expires",
    "Vary",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-Powered-By",
    "X-com-ibm-team-Trace-Identifier",
]

# make this an empty string to supppress saving/reloading cookies
COOKIE_SAVE_FILE = ".cookies_discovery"

jazzhost = 'https://jazz.ibm.com:9443'
username = 'ibm'
password = 'ibm'

rmcontext  = 'rm'

projectname = "rm_gc_p1"
componentname = "rm_gc_p1"
configname="rm_gc_p1 Initial Stream"

#projectname = "SGC Requirements"
#componentname = "SGC AMR"
#configname="test1"

use_proxy = True
proxydict = None
proxyport = 8888

#######################################################################################################
# utility functions to configure a proxy so you can see communication with the server in a https
# proxy such as Telerik Fiddler Classic configured as a MITM https proxy

# utility to see if a port is active listening for connections
def tcp_can_connect_to_url(host, port, timeout=5):
    # create an INET, STREAMing socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # now connect to the web server on port
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False

def setupproxy(url,proxyportT):
    # If a proxy is running on proxyport, setup proxydict so requests uses the proxy - this helps with tracing HTTP operations using e.g. Telerik Fiddler Classic
    proxydict = None
    if proxyport!=0:
        # test if proxy is running
        if tcp_can_connect_to_url('127.0.0.1', proxyport, timeout=2.0):
            # proxy e.g. Telerik Fiddler Classic on port 8888 is running so setup proxy
            urlparts = urllib.parse.urlsplit(url)
            if urlparts.port:
                proxyurl = urlparts.scheme + "://" + urlparts.netloc[:urlparts.netloc.find(':')]
            else:
                proxyurl = urlparts.scheme + "://" + urlparts.netloc
            # insert the proxy dictionary
            proxydict = {
                            'https':'http://127.0.0.1:'+str(proxyport) # NOTE the proxy URL is "http:" - Fiddler doesn't provide a https proxy by default so don't change this!
                            ,'http':'http://127.0.0.1:'+str(proxyport)
                        }
            logger.info( f'Setting proxy to {proxydict}' )
    return proxydict

#######################################################################################################
# utilities for making body content readable on a console
# decode response text
def to_text(response, encoding=None, errors='replace'):
    if response is None or isinstance(response, str):
        return response

    if isinstance(response, requests.models.Response) or isinstance(response, requests.Response):
        return response.text

    encoding = find_encoding(response, encoding)

    if isinstance(response, bytes) or isinstance(response, bytearray):
        content = response
    else:
        raise Exception()

    if "7bit" == encoding:
        encoding = 'us-ascii'

    try:
        if encoding is None:
            result = codecs.decode(content, errors=errors)
        else:
            result = codecs.decode(content, encoding=encoding, errors=errors)
    except:
        raise
    return result

def to_text_strict(response, encoding=None):
    return to_text(response, encoding, 'strict')

# find the encoding of a response
def find_encoding(response, encoding):
    if isinstance(encoding, str):
        encoding = encoding
    elif encoding is None and (
        isinstance(response, requests.Response) or isinstance(response, requests.models.Response)):
        encoding = response.encoding
    elif encoding is None:
        pass
    else:
        raise Exception('Unknown encoding type [%s]' % encoding)
    if encoding is None:
        encoding = 'utf-8'  # default
    if "7bit" == encoding:
        encoding = 'us-ascii'
    return encoding

# encode to binary for non-XML strings
def to_binary(text, encoding=None, errors='strict'):
    if isinstance(text, bytes) or isinstance(text, bytearray):
        return text
    encoding = find_encoding(None, encoding)
    if encoding is None:
        result = codecs.encode(text, errors=errors)
    else:
        result = codecs.encode(text, encoding=encoding, errors=errors)
    return result        


#######################################################################################################
# for RM - this is a bit primitive but works well enough for now
def getconfigtype( configuri ):
    if '/baseline/' in configuri:   return "Baseline" 
    if '/stream/' in configuri:     return "Stream"
    if '/changeset/' in configuri:  return "Changeset"
    raise Exception( f"Unrecognized configuration {configuri}" )
    
#######################################################################################################
#
# low-level version NOT using elmclient AT ALL - everything including authentication for basic Liberty form auth is done here
#
# NOTE THIS ONLY WORKS FOR FORM-BASED login, i.e. doesn't work with JAS!
#

# generic HTTP GET with login if auth is needed
def get_with_optional_login( sess, url, *, params=None, headers=None, username="", password="", verify=False, intent=None, action=None, donotlog=False ):
    '''
    This function tries to perform a GET on url - and checks the result,
    If authentication is needed it does this using provided username/password, and then returns the data
    ONLY WORKS LIBERTY FOR FORM AUTHENTICATION!
    '''
    params = params or {}
    headers = headers or {}

    retry_needed = False
    
    # try to load previous cookies - helps avoid authentication when previous cookies already authenticatded us
    if COOKIE_SAVE_FILE:
        if os.path.isfile(COOKIE_SAVE_FILE):
            with open(COOKIE_SAVE_FILE, 'rb') as f:
                sess.cookies.update(pickle.load(f))
    
    # execute the request - NOTE verify (of SSL cert) is set to False because test server using self-signed cert
    response = sess.get(url,headers=headers, params=params, verify=verify )
    response.raise_for_status()

    # The response is "good" (i.e. 200) but if auth is needed there is a specific header+value
    # (in which case the response is not the data requested, but the data will be returned by authenticating)
    if response.headers.get('X-com-ibm-team-repository-web-auth-msg',"") == 'authrequired':
        print("Authentication required")
        # get the auth path from the JazzFormAuth cookie path
        cookiedetails = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path} for c in sess.cookies if c.name=='JazzFormAuth'][0]
        authpath = cookiedetails['path']
        # unparse to get the host then construct the auth url
        parts = urllib.parse.urlparse( url )
        host = f"{parts.scheme}://{parts.netloc}"
        auth_url = f"{host}{authpath}/j_security_check?j_username={username}&j_password={password}"
        response = sess.get( auth_url, verify=verify )
        log_redirection_history( response, intent=f"Authenticate user {username}", donotlogbody=True )
        response.raise_for_status()
        # check the auth was successful - is there a JAZZ_AUTH_TOKEN?
        if 'JAZZ_AUTH_TOKEN' not in response.cookies:
            raise Exception ( f"Authentication failed using {username=} {password=}!" )
        print("Auth successful - redoing the GET now authenticated")
        # a re-request is needed because the authentication redirection will have finished with a GET on the original URL but
        # this will have lost the original request headers during redirects
        # So re-GET using the original headers and parameters
        response = sess.get(url,headers=headers, params=params, verify=verify )
        response.raise_for_status()
        if not donotlog:
            log_redirection_history( response, intent="Retry GET after authentication: "+intent, action=action  )
    else:
        if not donotlog:
            log_redirection_history( response, intent=intent, action=action )
        # could check here for 401 response from OIDC/JAS    
        
    # save cookies
    if COOKIE_SAVE_FILE:
        with open( COOKIE_SAVE_FILE, 'wb') as f:
            pickle.dump(sess.cookies, f)

    return response

# these logging functions are simplified versions of simiar functions in httpops.py

# log a request/response, which may be the result of one or more redirections, so first log each of their request/response
def log_redirection_history( response, intent=None, action=None, donotlogbody=False ):
    thisintent = intent
    after = ""
    for i,r in enumerate(response.history):
        after= " (after redirects)"
        loghtml( f"{_log_request( r.request, intent=thisintent, donotlogbody=donotlogbody )}")
        loghtml( f"{_log_response( r )}")
        thisintent = 'Redirection of '+intent
    loghtml( f"{_log_request( response.request, intent=intent, donotlogbody=donotlogbody)}")
    loghtml( f"{_log_response( response, action=action )}")

# generate a string for logging of a http request with a stacktrace of the collers and showing URL, headers and any data
def _log_request( request, donotlogbody=False, intent=None ):
    logtext = ""
    
    if intent:
        logtext += f"\n\nINTENT: {intent}\n\n"
        
    if donotlogbody:
        # redact username/password parameter values
        # unparse the url
        url_parts = list(urllib.parse.urlparse(request.url))
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        if 'j_username' in query:
            query['j_username'] = "REDACTED"
        if 'j_password' in query:
            query['j_password'] = "REDACTED"
        url_parts[4] = urllib.parse.urlencode(query)
        # reconstruct the possibly-redacted URL
        query_url = urllib.parse.urlunparse(url_parts)        
        logtext += f"{request.method} {query_url}\n"
    else:
        logtext += f"{request.method} {request.url}\n"

    # show headers
    for k in sorted(request.headers.keys()):
        if k in ignore_headers:
            continue
        logtext += "  " + k + ": " + to_text(request.headers[k]) + "\n"
    # show cookies
    if hasattr(request, 'cookies'):
        cjd = requests.utils.dict_from_cookiejar(request.cookies)
        for k in sorted(cjd.keys()):
            logtext += "  Cookie " + k + ": " + cjd[k] + "\n"

    logtext += "\n"
    
    # add the body
    if request.body is not None:
        if donotlogbody:
            rawtext = "BODY REDACTED"
        elif len(request.body) > 1000000:
            rawtext = "LONG LONG CONTENT NOT SHOWN..."
        else:
            rawtext = repr(request.body)[1:-1]
            if len(rawtext) > 0:
                if rawtext[0] == '<' or rawtext[0] == '{':
#                    if rawtext[0] == '{' or ( rawtext[0]=='<' and not rawtext.startswith( '<?xml' ) and not rawtext.startswith( '<rdf' ) ):
                    rawtext = re.sub(r"\\n", "\n", rawtext)
                    rawtext = re.sub(r"\\t", "  ", rawtext)
#                    elif rawtext.startswith( '<?xml' ) or rawtext.startswith( '<rdf' ):
                if rawtext.startswith( '<?xml' ) or rawtext.startswith( '<rdf' ):
                    # assume XML
                    tree = ET.fromstring( rawtext )
                    ET.indent(tree, space="  " )
                    rawtext = ET.tostring( tree )
                else:
                    pass
            logtext += rawtext
        # the surroundings allow splitting out the request body when parsing the log
        logtext += "\n"
        
    return logtext

# generate a string for logging of a http response showing response code, headers and any data
def _log_response( response, action=None ):
    logtext = f"Response: {response.status_code}\n"
    # use the urllib3 cookiejar so Set-Cookie-s don't get folded into one single unparseable value by Requests
    # see https://github.com/psf/requests/issues/3957
    cs = response.raw.headers.items()
    for c,v in sorted(cs):
        if c in ignore_headers:
            continue
        logtext += "  " + c + ": " + v + "\n"
        
    logtext += "\n"
        
    # add the body
    if response.content is not None:
        if len(response.content) > 1000000:
            rawtext = "LONG LONG CONTENT..."
        else:
            rawtext = repr(response.content)[2:-1]
            if len(rawtext) > 0:
                if rawtext[0] == '<' or rawtext[0] == '{':
#                    if rawtext[0] == '{' or ( rawtext[0]=='<' and not rawtext.startswith( '<?xml' ) and not rawtext.startswith( '<rdf' ) ):
                    rawtext = re.sub(r"\\r", "", rawtext)
                    rawtext = re.sub(r"\\n", "\n", rawtext)
                    rawtext = re.sub(r"\\t", "  ", rawtext)
#                    elif rawtext.startswith( '<?xml' ) or rawtext.startswith( '<rdf' ):
                if rawtext.startswith( '<?xml' ) or rawtext.startswith( '<rdf' ):
                    # assume XML
                    tree = ET.fromstring( rawtext.encode() )
                    ET.indent(tree, space="  " )
                    rawtext = ET.tostring( tree ).decode()
                else:
                    pass
            logtext += rawtext
        logtext += "\n"

    if action:
        logtext += f"\nACTION: {action}\n"

    return logtext

def logtext( s ):
    if args.outputfile:
        open( args.outputfile,"at").write(s)
    else:
        print( s )
    
def inithtml():
    global htmltoc, htmlcontent
    htmltoc=""
    htmlcontent=""
    
def loghtml( s, *, anchorid=None, anchortext=None, sectionbreak=False, minorbreak=False ):
    global htmltoc, htmlcontent
    if sectionbreak:
        htmlcontent += "\n============================================================================================\n"
    if minorbreak:
        htmlcontent += "\n--------------------------------------------------------------------------------------------\n"
    if anchorid:
        # make sure the anchor doesn't have any space
        anchorid = anchorid.replace( " ","-" )
        if not anchortext:
            raise Exception( "Must provide anchortext if specifying anchorid!" )
        htmltoc += f'<p><a href="#{anchorid}">{anchortext}</a></p>'
        htmlcontent += f'<a id={anchorid}>{anchortext}</a>'
    if s:
        htmlcontent += f'<pre>{html.escape(s)}</pre>\n'

def savehtml():
    global htmltoc, htmlcontent
    global args
    if args.htmloutputfile:
        with open( args.htmloutputfile, "wt" ) as f:
            f.write( "<HTML><BODY>" )
            f.write( f"<div>{htmltoc}</div>\n" )
            f.write( f"<div>{htmlcontent}</div>\n" )
            f.write( "</BODY></HTML>" )
            f.close()
      
# setup commandline args
print( f"Version {__meta__.version}" )

# get some defaults from the environment (which can be overridden on the commandline or the saved obfuscated credentials)
JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
USER        = os.environ.get("QUERY_USER"       ,"ibm" )
PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,None )

# setup arghandler
parser = argparse.ArgumentParser(description="Perform OSLC query on a Jazz application, with results output to CSV (and other) formats - use -h to get some basic help")

parser.add_argument('projectname', default=None, help='Name of the project')
parser.add_argument('componentname', default=None, help='Source configuration')
parser.add_argument('configname', default=None, help='Target configuration')
parser.add_argument('-A', '--appstrings', default=APPSTRINGS, help=f'A comma-seperated list of apps, the query goes to the first entry, default "{APPSTRINGS}". Each entry must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using environemnt variable QUERY_APPSTRINGS')
parser.add_argument('-H', '--htmloutputfile', default=None, help='Name of the file to save the html log')
parser.add_argument("-J", "--jazzurl", default=JAZZURL, help=f"jazz server url (without the /jts!) default {JAZZURL} - Default can be set using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
parser.add_argument('-L', '--loglevel', default=None,help=f'Set logging to file and (by adding a "," and a second level) to console to one of DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
parser.add_argument('-O', '--outputfile', default=None, help='Name of the file to save the log')
parser.add_argument("-P", "--password", default=PASSWORD, help=f"user password, default {PASSWORD} - Default can be set using environment variable QUERY_PASSWORD - set to PROMPT to be asked for password at runtime")
parser.add_argument('-S', '--schemafile', default=None, help='Name of file to save the schema to')
parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
parser.add_argument("-U", "--username", default=USER, help=f"user id, default {USER} - Default can be set using environment variable QUERY_USER")
parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')

args = parser.parse_args()

username = args.username
password= args.password

jazzhost = args.jazzurl
rmcontext = args.appstrings.split( ",", 1 )[0].split( ":",1 )[0]

projectname = args.projectname
componentname = args.componentname
configname = args.configname

proxyport = args.proxyport

verify = args.certs

# Create the session used for all requests to the server
# BECAUSE it gets the authentication cookie and provides it on later requests
thesession = requests.session()

if use_proxy:
    proxydict = setupproxy( jazzhost, proxyport )
    if proxydict:
        thesession.proxies.update( proxydict )
     

inithtml()

loghtml( "",anchorid="Discovery1", anchortext="Discovery step #1", sectionbreak=True )

headers = { 'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml' }
params = {}

# get rootservices
response = get_with_optional_login( thesession, urllib.parse.urljoin(jazzhost,f"/{rmcontext}/rootservices"),headers=headers, username=username, password=password, intent='Discovery #1: GET rootservices', action='Follow <oslc_config:cmServiceProviders rdf:resource="https://jazz.ibm.com:9443/rm/oslc_config"/>' )
rootservices_x = ET.fromstring(response.content)

# refer to discovery example here https://jazz.net/forum/questions/266334/dng-oslcfetch-components-from-project-area
cmsp_x = rootservices_x.find( './/oslc_config:cmServiceProviders',prefixes )
cmsp_u = cmsp_x.get(f"{{{prefixes['rdf']}}}resource")

print( f"Config Managment service provider URL is {cmsp_u}" )

loghtml( "",anchorid="Discovery2", anchortext="Discovery step #2", minorbreak=True )

# get the compponents entry point
response = get_with_optional_login( thesession, cmsp_u,headers=headers, username=username, password=password, intent='Discovery #2 Find the components entry point', action='Follow <oslc:ServiceProvider rdf:about="https://jazz.ibm.com:9443/rm/oslc_config/components">' )
candc_x = ET.fromstring( response.content )

comps_x = candc_x.find( './/oslc:ServiceProvider',prefixes )
comps_u = comps_x.get( f"{{{prefixes['rdf']}}}about" )

print( f"Components Service Provider URL is {comps_u=}" )

loghtml( "",anchorid="Discovery3", anchortext="Discovery step #3", minorbreak=True )

# get the projects
response = get_with_optional_login( thesession, comps_u,headers=headers, username=username, password=password, intent="Discovery #3 Get list of all projects", action='Locate an oslc:CreationFactory tag which contains the dcterms:title of your project – in that oslc:CreationFactory follow the adjacent oslc:creation tag' )
projs_x = ET.fromstring( response.content )

## could list all projects here
for proj_title_x in projs_x.xpath( './/oslc:CreationFactory/oslc:resourceType[@rdf:resource="http://open-services.net/ns/config#Component"]/../dcterms:title', namespaces=prefixes ):
    loghtml( f'INFO: Project {proj_title_x.text}')
    print( f'INFO: Project {proj_title_x.text}')

# find the project
project_x = projs_x.xpath( './/oslc:CreationFactory/oslc:resourceType[@rdf:resource="http://open-services.net/ns/config#Component"]/../dcterms:title[text()="'+projectname+'"]/../oslc:creation', namespaces=prefixes )
project_u = project_x[0].get(f"{{{prefixes['rdf']}}}resource")

print( f"The project URL is {project_u}" )

loghtml( "",anchorid="Discovery4", anchortext="Discovery step #4", minorbreak=True )

# find the component
response = get_with_optional_login( thesession, project_u,headers=headers, username=username, password=password, intent="Discovery #4 Retrieve project details to find conponent", action='For the rdf:Description tag which contains the title of your component of interest, follow its rdf:about attribute' )
thecomps_x = ET.fromstring( response.content )

## could list all components here
for comptitle_x in thecomps_x.xpath( f'.//rdf:Description/dcterms:title', namespaces=prefixes ):
    loghtml( f"INFO: Component {comptitle_x.text}" )
    print( f"INFO: Component {comptitle_x.text}" )
    
thecomp_x = thecomps_x.xpath( f'.//rdf:Description/dcterms:title[text()="{componentname}"]/..', namespaces=prefixes )
thecomp_u = thecomp_x[0].get(f"{{{prefixes['rdf']}}}about")

print( f"Component URL is {thecomp_u}" )

loghtml( "",anchorid="Discovery5", anchortext="Discovery step #5", minorbreak=True )

# find the configuration list pointer
response = get_with_optional_login( thesession, thecomp_u,headers=headers, username=username, password=password, intent="Discovery #5 Find configurations in the component", action='Follow the contained oslc:configurations tags' )
proj_services_x = ET.fromstring( response.content )
comp_configs_x = proj_services_x.find( './/oslc_config:configurations', prefixes )
comp_configs_u = comp_configs_x.get(f"{{{prefixes['rdf']}}}resource")

print( f"Streams and Baselines URL is {comp_configs_u}" )

loghtml( "",anchorid="Discovery6", anchortext="Discovery step #6", minorbreak=True )

# search for the config we want
response = get_with_optional_login( thesession, comp_configs_u,headers=headers, username=username, password=password, intent="Discovery #6 Search for the config in streams, baselines and changesets", action='Follow rdfs:member tags to find one which has the dcterms:title of your configuraiton of interest' )
aconf_x = ET.fromstring( response.content )

# search for the config name we want by going through all the members in all the configurations, and if they have rm_config:changesets then checking those too
# finding the first stream/baseline/changeset that matches the name - duplicated names won't be noticed/used!
thisconf_u = None

# this list will be extended as new configs are found - in particular changesets are added to it.
# entries in this list are all rdfs:member - if it has a rdf:about then it's retrieved otherwise it's checked for dcterms:title
confstocheck = aconf_x.findall( './/rdfs:member', prefixes )
while len(confstocheck)>0:
    aconf_x = confstocheck.pop() #take config off the front
    aconf_u = aconf_x.get( f"{{{prefixes['rdf']}}}resource" )
    if aconf_u is not None:
        # retrieve the definition
        response = get_with_optional_login( thesession, aconf_u,headers=headers, username=username,password=password, intent="Retrieve this configuraiton to check its dcterms:title")
        aconf_x = ET.fromstring( response.content )
#    thisconf_x = aconf_x.xpath( f".//oslc_config:Configuration/dcterms:title[text()='{configname}']/..", namespaces=prefixes ) or aconf_x.xpath( f".//oslc_config:Stream/dcterms:title[text()='{configname}']/..", namespaces=prefixes ) or aconf_x.xpath( f".//oslc_config:Baseline/dcterms:title[text()='{configname}']/..", namespaces=prefixes )
    thisconf_x = aconf_x.find( f".//oslc_config:Configuration", prefixes )
    if thisconf_x is None:
        thisconf_x = aconf_x.find( f".//oslc_config:Stream", prefixes )
    if thisconf_x is None:
        thisconf_x = aconf_x.find( f".//oslc_config:Baseline", prefixes )
    if thisconf_x is None:
        thisconf_x = aconf_x.find( f".//oslc_config:ChangeSet", prefixes )
#    print( ET.tostring( thisconf_x ) )

    # check if this is the config we're looking for
    if thisconf_x is not None:
        # check for changesets and if found retrieve them add to confstocheck
        changesets_x = thisconf_x.find( ".//rm_config:changesets", prefixes )
        if changesets_x is not None:
            # retrieve the CS details
            cs_u = changesets_x.get( f"{{{prefixes['rdf']}}}resource" )
            response = get_with_optional_login( thesession, cs_u, headers=headers, username=username,password=password)
            thecs_x =  ET.fromstring( response.content )
            confstocheck.extend( thecs_x.findall( './/rdfs:member', prefixes ) )

        title = thisconf_x.find( ".//dcterms:title",prefixes ).text
        loghtml( f'INFO: Configuration {aconf_u} title {title}')
        print( f'INFO: Configuration {aconf_u} title {title}')
        if title == configname:
            if thisconf_u:
                raise Exception( "Duplicate config name found!" )
            # use the tag to determine the name for the configuration type
            thisconf_u = thisconf_x.get( f"{{{prefixes['rdf']}}}about" )
            configtype = getconfigtype( thisconf_u )
            break
        
if thisconf_u is None:
    raise Exception( f"Config {configname} not found" )

print( f"Found configuration {thisconf_u} which is a {configtype}" )    
thisconf_x = aconf_x

loghtml( "",anchorid="Discovery7", anchortext="Discovery step #7", minorbreak=True )

# setup headers/params for the rest of the operations - these are all config-specific
params[httpops.chooseconfigheader(thisconf_u)] = thisconf_u
headers[ 'Configuration.context'] = thisconf_u

# retrieve the services.xml for the config
services_x = aconf_x.find( './/oslc:serviceProvider', prefixes )
services_u = services_x.get( f"{{{prefixes['rdf']}}}resource" )

response = get_with_optional_login( thesession, services_u,headers=headers, username=username,password=password, intent="Discovery #7 Retrieve the services.xml for your configuration", action='Use the services.xml to locate Query Capabilities, Creation Factories and resourceShapes' )

service_x = ET.fromstring( response.content )

## could list out all the CreationFactory, QueryCapability, resourceShape here

## Query Capabilities
print( "\nQuery Capabilities" )
loghtml( f'\nQuery Capabilities' )
for qc_x in service_x.findall( './/oslc:QueryCapability', prefixes ):
    qcqb_u = rdfxml.xmlrdf_get_resource_uri( qc_x, './/oslc:queryBase', prefix_map=prefixes )
    qcrt_u = rdfxml.xmlrdf_get_resource_uri( qc_x, './/oslc:resourceType', prefix_map=prefixes )
    qctitle = rdfxml.xmlrdf_get_resource_text( qc_x, './/dcterms:title', prefix_map=prefixes )
    print( f'{qctitle} {qcqb_u} {qcrt_u}' )
    loghtml( f'{qctitle} {qcqb_u} {qcrt_u}' )
    
## Creation Factory
print( "\nCreation Factories" )
loghtml( f'\nCreation Factories' )
for cf_x in service_x.findall( './/oslc:CreationFactory', prefixes ):
    cfcreation_u = rdfxml.xmlrdf_get_resource_uri( cf_x, './/oslc:creation', prefix_map=prefixes )
    cfrt_u = rdfxml.xmlrdf_get_resource_uri( cf_x, './/oslc:resourceType', prefix_map=prefixes )
    cftitle = rdfxml.xmlrdf_get_resource_text( cf_x, './/dcterms:title', prefix_map=prefixes )
    print( f'{cftitle} {cfcreation_u} {cfrt_u}' )
    loghtml( f'{cftitle} {cfcreation_u} {cfrt_u}' )

## Resource Shapes
print( "\nResource Shapes" )
loghtml( "\nResource Shapes" )
for cf_x in service_x.findall( './/oslc:resourceShape', prefixes ):
    # retrieve the shape
    shape_u = rdfxml.xmlrdf_get_resource_uri( cf_x, xpath=None, prefix_map=prefixes )
    response = get_with_optional_login( thesession, shape_u, headers=headers, username=username, password=password, intent=f"Retrieve type {shape_u}", donotlog=True ) # donotlog because they clutter the log
    shape_x = ET.fromstring( response.content )
    shapetitle = rdfxml.xmlrdf_get_resource_text( shape_x, './/oslc:ResourceShape/dcterms:title', prefix_map=prefixes )
    print( f"Type {shapetitle} {shape_u}" )
    loghtml( f"Type {shapetitle} {shape_u}" )

## resourceShape

loghtml( "", sectionbreak=True )

# find the query capability for oslc_rm:Requirement
req_query_x = service_x.find( './/oslc:QueryCapability/oslc:resourceType[@rdf:resource="http://open-services.net/ns/rm#Requirement"]/../oslc:queryBase', prefixes )
req_query_base_u = req_query_x.get( f"{{{prefixes['rdf']}}}resource" )

print( f"OSLC Query Base URL for requirements is {req_query_base_u}" )


savehtml()
