##
## © Copyright 2024- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# Read and process TRS base and changelog pages
#
#################################################
#################################################
# NOTE: VERY VERY UNFINISHED WORK IN PROGRESS!
#################################################
#################################################
#
# NOTE this requires that your user has the license trs_consumer assigned, which allows access to the TRS.
#  __DON'T__ reassign a license from lqe_user to yourself because then LQE will stop working!
#
# If you have the trs license you can access all the content in the TRS,
# BUT note that the TRS basically contains URLs pointing at e.g. DOORS Next resources, so there is no text of artifacts, etc., but you can say that a resource is in a certain configuration
# AND note that retrieving the data from DOORS Next is constrained by the access right of your user
#

# OSLC Tracked Resource Set 3.0   https://oslc-op.github.io/oslc-specs/specs/trs/tracked-resource-set.html
# OSLC TRS guidance (for clients) https://docs.oasis-open-projects.org/oslc-op/trs-guidance/v1.0/trs-guidance.html

import argparse
import pickle
import getpass
import io
import logging
import os
import os.path
import pprint as pp
import socket
import sys
import time
import concurrent.futures
import zipfile

import cryptography
import cryptography.fernet
import lxml.etree as ET
import urllib.parse
import shelve
import stat

from elmclient import __meta__
from elmclient import rdfxml
from elmclient import server
from elmclient import utils
from elmclient import _rm
from elmclient import httpops

import copyreg
import io
import tqdm
import contextlib
import rdflib
import rdflib.plugins.sparql

#######################################################################################
# element/lxml tree pickle/unpickle - by converting to/from textual XML
# from https://stackoverflow.com/q/25991860
def elementtree_unpickler(data):
    return ET.parse(io.BytesIO(data))

def elementtree_pickler(tree):
    return elementtree_unpickler, (ET.tostring(tree),)

copyreg.pickle(ET._ElementTree, elementtree_pickler, elementtree_unpickler)

#######################################################################################
class TRSmember( object ):
    def __init__( self, url, etag, xml ):
        self.url = url
        self.etag = etag #the etag is saved for when patches are handled
        self.xml = xml

#######################################################################################
class _TRS_resource(object):
    pass

class TRSChange( _TRS_resource ):
    def __init__( self, order, delta, changedurl, patch ):
        self.order = order
        self.delta = delta
        self.resource_u = changedurl
        self.patch = patch

    def __repr__( self ):
        return f"Change {self.order} {self.delta} {self.resource_u}"

class TRSBase( _TRS_resource ):
    def __init__( self, resource_u ):
        self.resource_u = resource_u
        self.delta="Base"
    def __repr__( self ):
        return f"Base {self.resource_u}"


#######################################################################################
# a better rmtree which hopefully won't have the problems that shutil.rmtree sometimes has of leaving stuff behind/not
def _win_rmtree(top,ignore_errors=False,leave_root=False):
    top = os.path.abspath(top)
    if not os.path.exists(top):
        return
    def __rmdir(folder):
        tries = 10
        for i in range(10): # try up to 10 times because sometimes the directory is not already empty
            try:
                os.rmdir(folder)
                break
            except BaseException as ex:
                if i >= tries -1:
                    if not ignore_errors:
                        raise
                    else:
                        return
                time.sleep(2)

    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            if os.path.exists(filename):
                try:
                    os.chmod(filename, stat.S_IWUSR)
                    os.remove(filename)
                except:
                    if ignore_errors:
                        raise
                    pass
        for name in dirs:
            filename = os.path.join(root, name)
            if os.path.exists(filename):
                try:
                    os.chmod(filename, stat.S_IWUSR)
                except:
                    if ignore_errors:
                        raise
#                ibjclreport("considering",filename,top,leave_root)
#                if filename != top or not leave_root:
#                    ibjclreport( "deleting",filename,top,leave_root)
                __rmdir(filename)
    if not leave_root:
        __rmdir(top)

#######################################################################################
def makedirs(path,exist_ok=False, removefilesifpresent=False):
    try:
        os.makedirs(path,exist_ok=exist_ok)
    except:
#        ibjclreport("Path already existed",path)
        pass
    if removefilesifpresent:
        _win_rmtree(path,ignore_errors=True,leave_root=True)
    return

#######################################################################################
# multi-threaded retrieve of a list of URLs, in any order
# exceptions are ignored!
# from https://stackoverflow.com/a/63834834
def retrieve_urls( app, urls, to_dict_x, trsheaders, maxthreads=20, progressbar=True, merge_linked_pages=False ):
    # Retrieve a single page and report the response headers and the resource content
    def load_url(url, timeout):
        try:
            return app.execute_get_rdf_xml( url, headers=trsheaders, return_headers=True, merge_linked_pages=merge_linked_pages )
        except:
            raise
    if progressbar:
        pbar =  tqdm.tqdm(total=len(urls))
    else:
        pbar = contextlib.nullcontext()

    with pbar:
        # We can use a with statement to ensure threads are cleaned up promptly
        with concurrent.futures.ThreadPoolExecutor(max_workers=maxthreads) as executor:
            # Start the load operations and mark each future with its URL
            future_to_url = {executor.submit(load_url, url, 60): url for url in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    page_x,respheaders = future.result()
                    to_dict_x[url] = TRSmember( url,respheaders.get("ETag"),page_x )
                except Exception as exc:
                    print('%r generated an exception: %s' % (url, exc))
                else:
                    pass
                if progressbar:
                    pbar.update(1)

#######################################################################################
def sanitiseurlforfilename( url ):
    # remove non-alpha chars from a URL to produce a usable file/folder name
    # assumes a valid URL
    result = ''
    shorturl = url.replace( "http://","")
    shorturl = shorturl.replace( "https://","")
    for ch in shorturl:
        if ch.isalnum() or ch in "-":
            result += ch
    return result

#######################################################################################
def timedwait(seconds,msg="", allow_escape=False):
    if msg is None:
        pass
    elif msg:
        print(msg)
    else:
        if allow_escape:
            print( f"Pausing for {int(seconds)} seconds - press Esc to exit immediately" )
        else:
            print( f"Pausing for {int(seconds)} seconds" )
    for t in tqdm.trange(int(seconds)):
        if allow_escape:
            if utils.kbhit():
                key = utils.getch()
#                print( f"{key=}" )
                if key == b'\x1b':
                    print( "Aborting!!" )
                    raise Exception( "User aborted" )
                else:
                    print( "\nPress Esc to cancel" )
        time.sleep(1)
    
#######################################################################################
def readtrs( trsname, args, app ):
    config = None

    baseappname = sanitiseurlforfilename( app.baseurl )

    makedirs(args.savefolder,exist_ok=True, removefilesifpresent=False)
    
    settings = shelve.open( os.path.join( args.savefolder, f"{baseappname}-{trsname}-settings" ) )

    basepagesfolder      = os.path.join( args.savefolder, f"{baseappname}-{trsname}-base_pages" )
    basemembers_u_file   = os.path.join( args.savefolder,f"{baseappname}-{trsname}-base_members_u.txt" )
    changelogpagesfolder = os.path.join( args.savefolder, f"{baseappname}-{trsname}-changelog_pages" )
    members_x_file       = os.path.join( args.savefolder,f"{baseappname}-{trsname}-members_x.pkl" )

    makedirs(basepagesfolder,exist_ok=True, removefilesifpresent=False)
    makedirs(changelogpagesfolder,exist_ok=True, removefilesifpresent=False)

    # pick up any existing base page data
    if not args.reindex and os.path.isfile( basemembers_u_file ):
        if args.verbose:
            print( f"reading {basemembers_u_file=}" )
        basemembers_u = open( basemembers_u_file,"rt").readlines()
    else:
        if args.verbose:
            print( f"resetting basemembers_u {basemembers_u_file}" )
        basemembers_u = {}

    if  not args.reindex and os.path.isfile( members_x_file ):
        # read the file
        if args.verbose:
            print( f"Members saved file {members_x_file} exists - using it" )
        with open(members_x_file, 'rb') as f:
            # The protocol version used is detected automatically, so we do not
            # have to specify it
            members_x = pickle.load(f)
    else:
        if args.verbose:
            print( f"Empty members_x" )
        members_x = {}

    trsurl = app.reluri( trsname )

    # headers for all requests
    trsheaders = {'OSLC-Core-Version': None, 'net.jazz.jfs.owning-context': None }

    # always get the trs page - if nothing else this points to the (first) base page
    changelogpage_u = trsurl
    changelogpage_x = app.execute_get_rdf_xml( changelogpage_u, headers=trsheaders, cacheable=False )
    changelogpages_x = [changelogpage_x]

    # always get the first base page
    basepage_u = rdfxml.xmlrdf_get_resource_uri(changelogpage_x, './/trs:base',exceptionifnotfound=True )
    ( basepage_x, respheaders ) = app.execute_get_rdf_xml( basepage_u, headers=trsheaders, return_headers=True, cacheable=False, merge_linked_pages=False, warn_linked_pages=False  )
    basepages_x = [basepage_x]

    cutoffevent = rdfxml.xmlrdf_get_resource_text( basepage_x, './/trs:cutoffEvent', exceptionifnotfound=True )
    fullrebasetime = rdfxml.xmlrdf_get_resource_text( basepage_x, './/rm:fullRebaseTime' )
    firstbasepageurl = httpops.findbasepagelink( respheaders.get("Link"),'rel="first"' )

    previouscutoffevent = settings.get('cutoffevent')
    previousfullrebasetime = settings.get('fullrebasetime')
    previoushighorder = int(settings.get('highorder',0))
    highorder = previoushighorder
    previousfirstbasepageurl = settings.get('firstbasepageurl')
    basepagesallread = settings.get('basepagesallread', False) and not args.reindex

    if args.verbose:
        print( f"{cutoffevent=}" )
        print( f"{previouscutoffevent=}" )
        print( f"{fullrebasetime=}" )
        print( f"{previousfullrebasetime=}" )
        print( f"{firstbasepageurl=}" )
        print( f"{previousfirstbasepageurl=}" )
        print( f"{highorder=}" )
        print( f"{basepagesallread=}" )

    # look for rebase having happened
    rebasehappened = False
    if previouscutoffevent != cutoffevent or previousfullrebasetime != fullrebasetime or previousfirstbasepageurl != firstbasepageurl:
        # TRS was rebased - could be IR or full rebase
        rebasehappened = True

    reindexneeded = False
    if not basemembers_u or args.reindex or not basepagesallread or rebasehappened:
        # erase all saved (possibly partial) base pages+members and changelog pages+members
        makedirs(basepagesfolder,exist_ok=True, removefilesifpresent=True)
        makedirs(changelogpagesfolder,exist_ok=True, removefilesifpresent=True)
        basemembers_u = []
#        changelogmembers_x = {}
        members_x = {}
        basepagesallread = False
        highorder = 0
        previoushighorder = 0
        if args.verbose:
            print( f"reset for full reindex" )
        reindexneeded = True

    changestoprocess = []

    if reindexneeded:
        # read base pages and work out base members
        # we have already read the first base page
        while basepage_u:
            if args.verbose:
                print( f"Processing base page {len(basepages_x)}" )
            # save the page
            open( f"{basepagesfolder}/{trsname}-{len(basepages_x)}.xml","wb" ).write( ET.tostring( basepage_x ) )
            # save the members
            # could use rdflib for this but it hardly seems worth doing unless one of the other apps (than rm) uses a different style of LDPC-RS RDF
            for basemember_x in rdfxml.xml_find_elements(basepage_x,'.//ldp:member'):
                basemember_u = rdfxml.xmlrdf_get_resource_uri( basemember_x )
                if basemember_u in basemembers_u:
                    raise Exception( f"Resource already specified in base {basemember_u}" )
                basemembers_u.append( basemember_u )

            #check for the next base page
            basepage_u = httpops.findbasepagelink( respheaders.get("Link"),'rel="next"' )
            if not basepage_u:
                break
            ( basepage_x, respheaders ) = app.execute_get_rdf_xml( basepage_u, headers=trsheaders, return_headers=True, warn_linked_pages=False  )
            basepages_x.append( basepage_x )
        open( f"{basepagesfolder}/basemembers_u.txt","wt" ).write( '\n'.join( basemembers_u ) )

        # remember that base pages were all read
        settings['basepagesallread'] = True
        settings.sync()
        # save the base members
        open( basemembers_u_file, "wt").write( "\n".join(basemembers_u) )
        if args.verbose:
            print( f"Base members saved to {basemembers_u_file}" )

    # get the changelog pages
#    # these are accumulated newest to oldest by sorting descending order
#    members = open( f"{args.pagesfolder}/{trsname}-baseurls.txt","rt" ).readlines()
#    print( f"{len(members)=}" )

    # prepare the SPARQL query for rdflib
    changes_query = """
    PREFIX trs: <http://open-services.net/ns/core/trs#>
    PREFIX trspatch: <http://open-services.net/ns/core/trspatch#>
    SELECT DISTINCT ?changelog ?changed ?delta ?order ?beforeetag ?afteretag ?patch ?createdfrom
    WHERE {
        ?a trs:changeLog ?changelog .
        ?changelog trs:change ?change .
        ?change trs:changed ?changed .
        ?change a ?delta .
        ?change trs:order ?order .
        OPTIONAL {
            ?change trspatch:beforeEtag ?beforeetag .
        }
        OPTIONAL {
            ?change trspatch:afterEtag ?afteretag .
        }
        OPTIONAL {
            ?change trspatch:rdfPatch ?patch .
        }
        OPTIONAL {
            ?change trspatch:createdFrom ?createdfrom .
        }
    }"""
    q = rdflib.plugins.sparql.prepareQuery( changes_query )

    while True:
        # we have already read the page
        if args.verbose:
            print( f"Processing changelog page {len(changelogpages_x)}" )
        # save the page
        open( f"{changelogpagesfolder}/{trsname}-{len(changelogpages_x)}.xml","wb" ).write( ET.tostring( changelogpage_x ) )

        # using rdflib parse the RDF
        g = rdflib.Graph()
        g.parse( data=ET.tostring(changelogpage_x), format="xml" )

        # query for changes
        qres = g.query(q)

        if not qres:
            print( f"No changes in this changelog page {changelogpage_u}" )

        if cutoffevent and cutoffevent==qres[0].changelog:
            # we've found the cutoff event - so stop reading the changelog
            if args.verbose:
                print( f"Found valid cutoffevent {cutoffevent}" )
            break

        # find all changelog entries in highest order first
        for row in sorted( list(qres), key=lambda q: int(q.order), reverse=True ):
            # keep the patch details but they're not currently used
            patch = (str(row.beforeetag), str(row.afteretag), str(row.patch), str(row.createdfrom))
            # get the order
            thisorder = int(row.order)
#                print( f"{thisorder=}" )
            # check for having previously seen this order, end if so
            if thisorder <= previoushighorder:
                # we've seen this before so give up now
                if args.verbose:
                    print( f"{thisorder=} less than or equal to {previoushighorder=} - finishing changelog processing" )
                break

            # remember the highest order seen
            if thisorder > highorder:
                highorder = thisorder

            if row.delta.endswith( "Modification" ):
                # modification - happens on streams and on OTs
                changestoprocess.append( TRSChange( thisorder,"Modification",row.changed,patch ) )
            elif row.delta.endswith( "Deletion" ):
                changestoprocess.append( TRSChange( thisorder,"Deletion",row.changed,patch ) )
            elif row.delta.endswith( "Creation" ):
                # create
                changestoprocess.append( TRSChange( thisorder,"Creation",row.changed,patch ) )
            else:
                raise Exception( f"Unrecognised delta {row.delta}" )

        # find the next page
        changelogpage_u = rdfxml.xmlrdf_get_resource_uri( changelogpage_x, './/trs:previous' )
        if not changelogpage_u:
            if args.verbose:
                print( "No previous link - reading changelog pages has finished" )
            break
        # get the next page
        changelogpage_x = app.execute_get_rdf_xml( changelogpage_u, headers=trsheaders, warn_linked_pages=False )
        changelogpages_x.append( changelogpage_x )

    # processing of changestoprocess: - IGNORING/NOT USING Patch!
    # principle is to check newest first, and add resource urls to either toretrieves or toignores
    # if a url is already in either toretrieves or toignores it is skipped

    # basic principal is that a resource should only be retrieved for the newest change
    # if already in members
        # Deletion - if already in toretrieve then ignore, otherwise set member to None
        # Creation - if already in toretrieve then ignore, otherwise add to toretrieve
        # Modification - if already in toretrieve then ignore, otherwise add to toretrieve
    # else (i.e. not in members)
        # Deletion - if not already in toretrieve then error! else set member to None
        # Creation - set member to None, if already in toretrieve then ignore, otherwise add to toretrieve
        # Modification - set member to None, if already in toretrieve then ignore, otherwise add to toretrieve

    # process the changes so only the most recent are retrieved, i.e. just once for a particular resource
    toretrieves = []
    toignores = []
    for c in changestoprocess:
#        print( f"change {c}" )
        if c.resource_u in toignores or c.resource_u in toretrieves:
            # this URL has already been seen - ignore this occurrence
            pass
        else:
            # remove any from the base which are in changelog - no point in retrieving them with base
            if reindexneeded and c.resource_u in basemembers_u:
                # ensure it isn't fetched as part of base
                basemembers_u.remove( c.resource_u )
            # must now allocate this resource into either toignores or toretrieves
            if c.delta == "Deletion":
                # do the delete
                if c.resource_u in members_x:
                    del members_x[c.resource_u]
                toignores.append( c.resource_u )
            elif c.delta == "Creation" or c.delta == "Modification" or c.delta == "Base":
                # make sure yto retrieve it
                toretrieves.append( c.resource_u )
            else:
                raise Exception( f"Unknown TRS action {c.delta}" )

    # if we're reindexing get the base - otherwise assume the base has already been read
    if reindexneeded:
        # retrieve the base
        if args.verbose or args.progressbar:
            print( f"Retrieving all {len(basemembers_u)} base page resources" )
        retrieve_urls( app, basemembers_u, members_x, trsheaders, maxthreads=20, progressbar=args.progressbar,merge_linked_pages=True )


    # then retrieve members in any order (i.e. multithreaded/as fast as possible)
    if toretrieves:
        if args.verbose or args.progressbar:
            print( f"Retrieving {len(toretrieves)} changelog resources" )
        retrieve_urls( app, toretrieves, members_x, trsheaders, maxthreads=20, progressbar=args.progressbar, merge_linked_pages=True )
    else:
        if args.verbose:
            print( f"No updates in the changelog!" )

    # save the members_x for next time
    if reindexneeded or toretrieves:
        # save the retrieved XML
        if args.verbose:
            print( f"Writing resources file {members_x_file}" )
        with open( members_x_file, 'wb') as f:
            # Pickle the 'data' dictionary using the highest protocol available.
            pickle.dump(members_x, f, pickle.HIGHEST_PROTOCOL)

    if args.separate:
        # split out configuration-related resources
        # split out type-related resources
        # split out all the other resources
        cm_x = {}
        types_x = {}
        others_x = {}
        for m in sorted(list(members_x.keys())):
            if "/rm/cm/" in m or '/rm/configSelections' in m:
                cm_x[m]=members_x[m]
            elif '/rm/versionedShapes' in m:
                types_x[m]=members_x[m]
            else:
                print( f"other {m}" )
                others_x[m]=members_x[m]
        # write them out
        cm_x_file = os.path.join( args.savefolder,f"{baseappname}-{trsname}-cm_x.pkl" )
        types_x_file = os.path.join( args.savefolder,f"{baseappname}-{trsname}-types_x.pkl" )
        others_x_file = os.path.join( args.savefolder,f"{baseappname}-{trsname}-others_x.pkl" )
        with open( cm_x_file, 'wb') as f:
            pickle.dump(cm_x, f, pickle.HIGHEST_PROTOCOL)
        with open( types_x_file, 'wb') as f:
            pickle.dump(types_x, f, pickle.HIGHEST_PROTOCOL)
        with open( others_x_file, 'wb') as f:
            pickle.dump(others_x, f, pickle.HIGHEST_PROTOCOL)
                
    if args.verbose:
        # successful completion - update the saved settings
        print( f"After {cutoffevent=}" )
        print( f"After {fullrebasetime=}" )
        print( f"After {firstbasepageurl=}" )
        print( f"After {highorder=}" )
        
    settings['cutoffevent'] = cutoffevent
    settings['fullrebasetime'] = fullrebasetime
    settings['highorder']=highorder
    settings['firstbasepageurl'] = firstbasepageurl
    # save the settings
    settings.close()

#######################################################################################
# start some threads to do the TRS reading
# read all the trs pages  - base and changelog - saving to disk
# process the saved pages

def main(inputargs=None):

    print( f"Version {__meta__.version}" )
    inputargs = inputargs or sys.argv[1:]

    # get some defaults from the environment (which can be overridden on the commandline or the saved obfuscated credentials)
    JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
    USER        = os.environ.get("QUERY_USER"       ,"ibm" )
    PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
    JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
    APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
    LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,None )

    # commandline options
    # setup arghandler
    parser = argparse.ArgumentParser(description="Perform OSLC query on a Jazz application, with results output to CSV (and other) formats - use -h to get some basic help")

    parser.add_argument('--forever', action="store_true", help="read and re-read forever (press Esc to exit)")
    parser.add_argument('--getthreads', default=4, type=int, help="Threads for getting details from source app as pages are processed")
    parser.add_argument('--pollinterval', default=60, type=int, help=f'interval between TRS polls when using --forever')
    parser.add_argument('--progressbar', action="store_false", help="Turn progress bar for reading base/changelog pages off")
    parser.add_argument('--retrievethreads', default=4, type=int, help="Threads for retrieving the TRS pages")
    parser.add_argument('--savefolder', default='trs', help=f'Folder to save details')
    parser.add_argument('-I', '--reindex', action="store_true", help="Reindex from scratch")
    parser.add_argument('-S', '--separate', action="store_true", help='Separate the resources')
    parser.add_argument('trsname', default=None, help='Comma-seperated list of names of the trs feeds e.g. trs2 or e.g. trs2,process-trs2 - each trs name will be added to the app context root, specified using -A')
    
    parser.add_argument('-A', '--appstrings', default=APPSTRINGS, help=f'A comma-seperated list of apps, the query goes to the first entry, default "{APPSTRINGS}". Each entry must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using environemnt variable QUERY_APPSTRINGS')
    parser.add_argument("-J", "--jazzurl", default=JAZZURL, help=f"jazz server url (without the /jts!) default {JAZZURL} - Default can be set using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
    parser.add_argument('-L', '--loglevel', default=None,help=f'Set logging to file and (by adding a "," and a second level) to console to one of DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    parser.add_argument('-N', '--noprogressbar', action="store_false", help="Don't show progress bar during query")
    parser.add_argument("-P", "--password", default=PASSWORD, help=f"user password, default {PASSWORD} - Default can be set using environment variable QUERY_PASSWORD - set to PROMPT to be asked for password at runtime")
    parser.add_argument('-Q', '--alwayscache', action="store_true", help="Always cache everything (useful to speed up testing)")
    parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    parser.add_argument("-U", "--username", default=USER, help=f"user id, default {USER} - Default can be set using environment variable QUERY_USER")
    parser.add_argument('-V', '--verbose', action="store_true", help="Show verbose info")
    parser.add_argument('-W', '--cachecontrol', action='count', default=0, help="Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and disables caching. Otherwise caching is continued from previous run(s).")
    parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')

    # other options
    parser.add_argument('--cachedays', default=7,type=int, help="The number of days for caching received data, default 7. To disable caching use -WW. To keep using a non-default cache period you must specify this value every time" )

    # saved credentials
    parser.add_argument('-0', '--savecreds', default=None, help="Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, appstring, username and password")
    parser.add_argument('-1', '--readcreds', default=None, help="Read obfuscated credentials from file - completely overrides commandline/environment values for jazzurl, jts, appstring, username and password" )
    parser.add_argument('-2', '--erasecreds', default=None, help="Wipe and delete obfuscated credentials file" )
    parser.add_argument('-3', '--secret', default="N0tSeCret-", help="SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater security) - only affects if using -0 or -1" )
    parser.add_argument('-4', '--credspassword', action="store_true", help="Prompt user for a password to save/read obfuscated credentials (make this longer for greater security)" )

    args = parser.parse_args(inputargs)

    if args.erasecreds:
        # read the file to work out length
        contentlen = len(open(args.erasecreds,"rb").read())
        # create same-length random data to overwrite
        for i in range(5):
            randomcontent = os.urandom(contentlen)
            open(args.erasecreds,"w+b").write(randomcontent)
        # and delete the file
        os.remove(args.erasecreds)

        print( f"Credentials file {args.erasecreds} overwritten then removed" )
        return 0

    if args.credspassword:
        if args.readcreds is None and args.savecreds is None:
            raise Exception( "When using -4 you must use -0 to specify a file to save credentials into, and/or -1 to specify a credentials file to read" )
        #make sure the user enters at least one character
        credspassword = ""
        while len(credspassword)<1:
            credspassword = getpass.getpass( "Password (>0 chars, longer is more secure)?" )
    else:
        credspassword = "N0tSecretAtAll"

    if args.readcreds:
#        if args.secret is None:
#            raise Exception( "You MUST specify a secret using -3 or --secret if using -0/--readcreads" )
        try:
            args.username,args.password,args.jazzurl,apps = json.loads( utils.fernet_decrypt(open(args.readcreds,"rb").read(),"=-=".join([socket.getfqdn(),os.path.abspath(args.readcreds),getpass.getuser(),args.secret,credspassword])) )
            # allow overriding appstrings stored in creads with option on commandline
            args.appstrings = args.appstrings or apps
        except (cryptography.exceptions.InvalidSignature,cryptography.fernet.InvalidToken, TypeError):
            raise Exception( f"Unable to decrypt credentials from {args.readcreds}" )
        print( f"Credentials file {args.readcreds} read" )

    # if no appstring yet specified use the default
    args.appstrings = args.appstrings or APPSTRINGS

    if args.savecreds:
        if args.secret is None:
            raise Exception( "You MUST specify a secret using -3 or --secret if using -1/--savecreads" )
        open(args.savecreds,"wb").write(utils.fernet_encrypt(json.dumps([args.username,args.password,args.jazzurl,args.appstrings]).encode(),"=-=".join([socket.getfqdn(),os.path.abspath(args.savecreds),getpass.getuser(),args.secret,credspassword]),utils.ITERATIONS))
        print( f"Credentials file {args.savecreds} created" )
        return 0

    # do a basic check that the target server is in fact running, this way we can give a clear error message
    # to do this we have to get the host and port number from args.jazzurl
    urlparts = urllib.parse.urlsplit(args.jazzurl)
    if ':' in urlparts.netloc:
        serverhost,serverport = urlparts.netloc.rsplit(":",1)
        serverport = int(serverport)
    else:
        serverhost = urlparts.netloc
        if urlparts.scheme=='https':
            serverport=443
        elif urlparts.scheme=='http':
            serverport=80
        else:
            raise Exception( "Unknown scheme in jazzurl {args.jazzurl}" )

    # now try to connect
    if not server.tcp_can_connect_to_url(serverhost, serverport, timeout=2.0):
        raise Exception( f"Server not contactable {args.jazzurl}" )

    # setup logging
    if args.loglevel is not None:
        levels = [utils.loglevels.get(l,-1) for l in args.loglevel.split(",",1)]
        if len(levels)<2:
            # if only one log level specified this is for file loggin - set console to None
            levels.append(None)
        if -1 in levels:
            raise Exception( f'Logging level {args.loglevel} not valid - should be comma-separated one or two values from DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF' )
        utils.setup_logging( filelevel=levels[0], consolelevel=levels[1] )

    logger = logging.getLogger(__name__)

    utils.log_commandline( os.path.basename(sys.argv[0]),inputargs )

    if args.password is None:
        args.password = getpass.getpass(prompt=f'Password for user {args.username}: ')

    # request proxy config if appropriate
    if args.proxyport != 0:
        server.setupproxy(args.jazzurl,proxyport=args.proxyport)

    if args.cachedays <1:
        raise Exception( "--cachedays must be >=1" )
    # monkey-patch the cache duration
    server.CACHEDAYS = args.cachedays

    # approots has keys of the domain and values of the context root
    approots = {}
    allapps = {} #keyed by domain
    themainappstring = args.appstrings.split(",")[0]
    themaindomain = server.JazzTeamServer.get_appstring_details(themainappstring)[0]

    for appstring in args.appstrings.split(","):
        domain,contextroot = server.JazzTeamServer.get_appstring_details(appstring)
        if domain in approots:
            raise Exception( f"Domain {domain} must not appear twice in {args.appstrings}" )
        approots[domain]=contextroot

    # assert the jts default context root if not already specified in args.appstring
    if 'jts' not in approots:
        approots['jts']='jts'

    # setup for caching
    cachefolder = ".web_cache"

    # create our "server"
    theserver = server.JazzTeamServer(args.jazzurl, args.username, args.password, verifysslcerts=args.certs, jtsappstring=f"jts:{approots['jts']}", cachingcontrol=args.cachecontrol, cachefolder=cachefolder, alwayscache=args.alwayscache )

    # create all our apps (there will be a main app which is specified by the first appstrings value, the main reason for allowing more than one is when gc is needed)
    for appdom,approot in approots.items():
        allapps[appdom] = theserver.find_app( f"{appdom}:{approot}", ok_to_create=True )

    # get the main app - it's the one we're going to query - it was first in args.appstring
    app = allapps[themaindomain]

    #######################################################################################
    # process the specified TRSs
    # any keypress aborts the processing (don't use ^c it will leave things in unknown state)
    
    trsnames = args.trsname.split(",")

    while True:
        if args.forever and utils.kbhit():
            break
        for trsname in trsnames:
            if args.verbose:
                print( f"\nReading {trsname}" )
            readtrs( trsname, args, app )
        if not args.forever:
            break
        if utils.kbhit():
            break
        if args.verbose:
            print( f"\nPausing" )
        timedwait( args.pollinterval, allow_escape=True )

if __name__ == "__main__":
    main()
