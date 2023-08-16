##
## Licensed Material - Property of IBM
## (c) Copyright IBM Corp. 2019, 2020, 2021.  All Rights Reserved.
##

# elmclient\examples\represt.py -A rm text -a -C aa.csv -S -L 10 -g 2 -p rm_gc_p1

# DN/DNG Reportable REST API https://jazz.net/wiki/bin/view/Main/DNGReportableRestAPI
#   DN/DNG FAQ on reportable rest https://jazz.net/wiki/bin/view/Main/RRCReportServiceFAQ
# ETM/RQM Reportable REST API https://jazz.net/wiki/bin/view/Main/RqmApi#Resources_and_their_Supported_Op
# EWM/RTC Reportable REST API https://jazz.net/wiki/bin/view/Main/ReportsRESTAPI

import os

import argparse
import csv
import datetime
import getpass
import json
import logging
import socket
import statistics
import time
import traceback
import urllib
import urllib3

import cryptography
import cryptography.fernet
import requests
import lxml.etree as ET

import elmclient.rdfxml as rdfxml
import elmclient.server as server
import elmclient._app as _app
import elmclient.utils as utils

############################################################################

def represt_main():

    # get some defaults which can be overridden in the environment
    JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
    USER        = os.environ.get("QUERY_USER"       ,"ibm" )
    PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
    JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
    APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
    LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,"ERROR,DEBUG" )

    allformats = []
    
    #collect all the artifact formats
    for appcls in _app._App.__subclasses__():
        if appcls.artifact_formats:
            allformats.append(f"{appcls.domain}: "+",".join( appcls.artifact_formats )+ "." )
    allformats = " ".join(allformats)
    
    # for arguments common to all sub-parsers
    common_args = argparse.ArgumentParser(description="Perform Reportable REST query on an application, with results output to CSV and/or XML - use -h to get some basic help. NOTE only rm queries are allowed at the moment.", add_help=False)
    
    # the main arguments parser
    parser = argparse.ArgumentParser(description="Perform Reportable REST query on an application, with results output to CSV and/or XML - use -h to get some basic help. NOTE only rm queries are allowed at the moment.")

    # the holder for sub-parsers
    subparsers = parser.add_subparsers(help='sub-commands',dest='subparser_name')

    # general settings which are common acrosss all reportable rest apps
    common_args.add_argument('-A', '--appstrings', default=None,help=f'Must be comma-separated list of used domains or domain:contextroot, the FIRST one is where the reportable rest query goes, default {APPSTRINGS} If using nonstandard context roots for just rm and gc like /rrc and /thegc then specify "rm:rrc,gc:thegc" NOTE if jts is not on /jts but is on /myjts then add jts: and its context route without leading / e.g. "rm,jts:myjts" to the end of this string. Default can be set using environment variable QUERY_APPSTRINGS')
    common_args.add_argument('-C', '--csvoutputfile', default=None, help='Name of file to save the CSV results to')
    common_args.add_argument('-D', '--delaybetweenpages', type=float,default=0.0, help="Delay in seconds between each page of results - use this to reduce overall server load particularly for large result sets or when retrieving many attributes")
    common_args.add_argument('-E', '--cacheexpiry', type=int, default=7, help="Days to keep cached results from the server (NOTE query results are never cached) - set to 0 to erase current cache and suppress new caching - set to e.g. -7 to erase current cache and then cache for 7 days, set to 7 to maintain the current cache and keep new entries for 7 days")
#    parser.add_argument("-F", "--forcequery", default=None, help="Force use of this exact query - all scope/filter settings are ignored! - this string is added to the reportable rest publish base for your app - e.g. use '/text/*' to do query /publish/text/* - NOTE you need to put the & and ? for any query parameters and include URL escapes in the parameters!")
    common_args.add_argument( '-G', '--pagesize', default=0, type=int, help="Page size for results paging (default is whatever the server does, e.g. 100)")    
    common_args.add_argument('-H', '--forceheader', action='append', default=[], help="Force adding header with value to the query - you must provide the header name=value. NOTE these override headers from the application. If you want to force deleting a header give it the value DELETE. There is no way of forcing a header to have the value DELETE")
    common_args.add_argument("-J", "--jazzurl", default=JAZZURL, help="jazz server url (without the /jts!) default {JAZZURL} Default can be set using environment variable QUERY_JAZZURL")
    common_args.add_argument('-K', '--collapsetags', action="store_true", help="In CSV output rather than naming column for the tag hierarchy, just use the leaf tag name")
    common_args.add_argument('-L','--loglevel', default=LOGLEVEL,help=f'Set logging on console and (if providing a , and a second level) to file to one of DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    common_args.add_argument('-M', '--maxresults', default=0, type=int, help="Limit on number of results - may be exceeded by up to one page of results")
    common_args.add_argument('-N', '--again', type=int, default=1, help="Number of times to repeat the REST API call sequence, must be >1 to get statistics fotr REST call duration")
#    parser.add_argument('-N', '--noprogressbar', action="store_false", help="Don't show progress bar during query")
    common_args.add_argument("-P", "--password", default=PASSWORD, help="User password - can be set using env variable OUERY_PASSWORD - set to PROMPT to be prompted at runtime")
    common_args.add_argument('-R', '--forceparameter', action='append', default=[], help="Force adding query name and value to the query URL - you must provide the name=value, the value will be correctly encoded for you. NOTE these override parameters from the application. If you want to force deleting a parameter give it the value DELETE. There is no way of forcing a parameter to have the value DELETE")
    common_args.add_argument('-S', '--sortidentifier', action="store_true", help="If identifier is in results, sort into ascending numeric order of identifier")
    common_args.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    common_args.add_argument("-U", "--username", default=USER, help="User id - can be set using environment variable QUERY_USER")
    common_args.add_argument('-V', '--verbose', action="store_true", help="Show verbose info during query, including the query URL")
    common_args.add_argument('-W', '--cachecontrol', action='count', default=0, help="Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and disables caching. Otherwise caching is continued from previous run(s).")
    common_args.add_argument('-X', '--xmloutputfile', default=None, help='Name of file to save the XML results to')
    common_args.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')

    # various options
#    common_args.add_argument('--nresults', default=-1, type=int, help="TESTING UNFINISHED: Number of results expected (used for regression testing against stored data, doesn't need the target server - use -1 to disable checking")

    # saved credentials
    common_args.add_argument('-0', '--savecreds', default=None, help="Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, appstring, username and password")
    common_args.add_argument('-1', '--readcreds', default=None, help="Read obfuscated credentials from file - completely overrides commandline/environment values for jazzurl, jts, appstring, username and password" )
    common_args.add_argument('-2', '--erasecreds', default=None, help="Wipe and delete obfuscated credentials file" )
    common_args.add_argument('-3', '--secret', default="N0tSecret-", help="SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater security)" )
    common_args.add_argument('-4', '--credspassword', action="store_true", help="Prompt user for a password to save/read obfuscated credentials (make this longer for greater security)" )

    # add subcommand for each app that supports reportable rest
    for appcls in _app._App.__subclasses__():
        if appcls.supports_reportable_rest:
            appcls.add_represt_arguments( subparsers, common_args )
            
    args = parser.parse_args()
    
    # if no appstring specified use the default
    args.appstrings = args.appstrings or APPSTRINGS

    if not args.appstrings.split(",")[0].startswith(args.subparser_name):
        args.appstrings=f"{args.subparser_name}:{args.subparser_name},{args.appstrings}"
        print( f"{args.subparser_name} added to front of appstrings - using {args.appstrings} if you need a different context root from /{args.subparser_name} use -A to specify it" )

    # setup logging
    levels = [utils.loglevels.get(l,-1) for l in args.loglevel.split(",",1)]
    if len(levels)<2:
        # if only one log level specified, set both the same
        levels.append(None)
    if -1 in levels:
        raise Exception( f'Logging level {args.loglevel} not valid - should be comma-separated one or two values from DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF' )
    utils.setup_logging( filelevel=levels[0], consolelevel=levels[1] )
    
    logger = logging.getLogger(__name__)

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
        open(args.savecreds,"wb").write(utils.fernet_encrypt(json.dumps([args.username,args.password,args.jazzurl,args.appstrings]).encode(),"=-=".join([socket.getfqdn(),os.path.abspath(args.savecreds),os.getcwd(),getpass.getuser(),args.secret,credspassword]),utils.ITERATIONS))
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

    # request proxy config if appropriate
    if args.proxyport != 0:
        server.setupproxy(args.jazzurl,proxyport=args.proxyport)

    # approots has keys of the domain and values of the context root
    approots = {}
    allapps = {} #keyed by domain
    themainappstring = args.appstrings.split(",")[0]
    themaindomain = server.JazzTeamServer.get_appstring_details(themainappstring)[0]
#    print( f"MAIN {themainappstring} {themaindomain}" )
    
    for appstring in args.appstrings.split(","):        
        domain,contextroot = server.JazzTeamServer.get_appstring_details(appstring)
#        print( f"Registering {appstring} {domain} {contextroot}" )
        if domain in approots:
            raise Exception( f"Domain {domain} must not appear twice in {args.appstrings}" )
        approots[domain]=contextroot
    # assert the jts default context root if not already specified in args.appstring
    if 'jts' not in approots:
        approots['jts']='jts'
#    print( f"{approots=}" )    

    # create our "server"
    theserver = server.JazzTeamServer(args.jazzurl, args.username, args.password, verifysslcerts=args.certs,appstring=f"jts:{approots['jts']}",cachingcontrol=args.cachecontrol)

    # create all our apps
    for appdom,approot in approots.items():
        allapps[appdom] = theserver.find_app( f"{appdom}:{approot}", ok_to_create=True )
#        print( f"looking for {appdom}:{approot} {allapps[appdom]}" )

    # get the main app - it's the one we're going to query - it was first in args.appstring
    mainapp = allapps[themaindomain]
    if not mainapp.supports_reportable_rest:
        raise Exception( f"App {themaindomain} {themainappstring} doesn't provide a reportable rest API '{mainapp.reportable_rest_status}'" )

    queryurl,queryparams,queryheaders = mainapp.process_represt_arguments( args, allapps )

    if args.pagesize:
        queryparams['size'] = args.pagesize

    if args.forceparameter:
        for p in args.forceparameter:
            pname, pvalue = p.split("=",1)
            if pvalue=="DELETE":
                if pname in queryparams:
                    del queryparams[pname]
            else:
                queryparams[pname] = pvalue

    resultsxmls=[]
    nresults = 0
    
    headers = {
            'OSLC-Core-Version': None # this one seems to be required - it prevents the app from asserting OSLC-Core-Version when making Reportable REST API calls - this seems to affect paged results when the first query required a login :-o
        }
    headers.update(queryheaders) 
    
    if args.forceheader:
        for h in args.forceheader:
            hname, hvalue = h.split("=",1)
            if hvalue=="DELETE":
                if hname in headers:
                    headers[hname] = None
            else:
                headers[hname] = hvalue
    
    # create the full URL with parameters
    # NOTE doing this now allows the next page link to be used unmodified (headers are provided every time)
    parts = list(urllib.parse.urlparse(queryurl))
    parts[4] = urllib.parse.urlencode(queryparams)
    queryurl = urllib.parse.urlunparse(parts)

    if args.verbose:
        print( f"Retrieving {queryurl}" )

    # collect times for each call
    call_durations = []
    
    # save the url for 'again' repeated calls
    theurl = queryurl
    if args.again<1:
        raise Exception( "--again must be >=1")
    for againcounter in range(args.again):
        queryurl = theurl
        npages = 0
        nresults = 0
        while True:
            # retrieve results from this URL
            timer_start = time.perf_counter()
            
            # call the REST API
            result = mainapp.execute_get_xml(reluri=queryurl, headers=headers, cacheable=False, intent=f"Retrieve Reportable REST content page {npages+1}"  )
            
            # calculate and record the duration
            duration = time.perf_counter()-timer_start
            call_durations.append(duration)
            npages += 1
            
            # process the data
            for art in list(result.getroot()):
                print( ".",end='' )
                if againcounter == 0:
                    resultsxmls.append(art)
                    if args.maxresults>0 and len(resultsxmls)>=args.maxresults:
                        logger.info( "Results truncated to {args.maxresults}" )
                        break
                    
            print()
            
            nextlink = result.getroot().get("href",None)
            nresults += int(result.getroot().get(f"{{{rdfxml.RDF_DEFAULT_PREFIX['rrm']}}}totalCount",0))
            if args.maxresults>0 and nresults>=args.maxresults:
                print( f"Hit results limit {args.maxresults=} with {nresults} results" )
                break
                
            if result.getroot().get("rel",'') != "next" or nextlink is None:
                print( "Finished!")
                break
                
            # go round the loop for the next page
            queryurl = nextlink
            
            # if specified by the user, do a delay between pages
            if args.delaybetweenpages > 0.0:
                print( f"Pausing for {args.delaybetweenpages}s" )
                time.sleep(args.delaybetweenpages)
    
    # assemble the complete results into a single XMl file
    results = []
    resultroot= ET.Element('datasource')
    for resultxml in resultsxmls:
        resultroot.append(resultxml)
        
    print( f"Retrieved {len(resultsxmls)} results" )
        
    if args.xmloutputfile is not None:
        open( args.xmloutputfile,"wb").write(ET.tostring(resultroot))

    if args.csvoutputfile is not None:
        headings = []
        rows=[]
        # now walk the XML to produce the output rows
        # go to each result (one row)
#        print( f"{len(list(resultroot))=}" )
        headingsmapping = {}
        for res in list(resultroot):
            row = {}
            # def getcontentrow( node, thisrowdict, allcolumns, level, path, remove_ns=True ):
            row = utils.getcontentrow( res )
            for k in row.keys():
                if args.collapsetags and '/' in k:
                    k1 = k.rsplit("/",1)
                    if k in headingsmapping and headingsmapping[k] != k1:
                        headingsmapping[k1] = k
                else:
                    k1 = k
                if k1 not in headings:
                    headings.append(k1)                
            rows.append(row)
        if not args.collapsetags:
            headings.sort()
        
        if args.sortidentifier:
            if 'identifier' in headings:
                # put identifier in first column!
                headings.remove('identifier')
                headings = ['identifier']+headings
                # and sort the rows by identifier
                rows.sort(key=lambda x: int(x['identifier']))
            else:
                print( "Can't sort - identifier not in headings" )
                
        # write to CSV
        with open(args.csvoutputfile, 'w', newline='') as csvfile:
#            fieldnames = sorted(headings)
            fieldnames = headings
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, restval='')
            writer.writeheader()
            for row in rows:
                #            print( "k,v",k,v)
                writer.writerow(row)
    else:
        print("results=", results)

    if args.again > 1:
        # print some stats
        if int( len( call_durations ) / npages ) != len( call_durations ) / npages:
            raise( "Odd number of call durations so at least one set of queries was shorter than the others - can't calculate stats!" )
        if npages > 1:
            # multiple pages - combine the times
            print( f"{npages=} {len(call_durations)=} {call_durations=}" )
            samples = [sum(call_durations[i:i+npages]) for i in range(0,len(call_durations),npages)]
            print( f"{samples=}" )
        else:
            print( f"{len(call_durations)=} {call_durations=}" )
            samples = call_durations
        ncalls = len(call_durations)
        call_mean = statistics.mean(samples)/npages
        call_median = statistics.median(samples)/npages
        call_variance = statistics.pvariance(samples)/npages
        print( f"{call_mean=} {call_median=} {call_variance=}" )

def main():
    runstarttime = time.perf_counter()
    represt_main()
    elapsedsecs = time.perf_counter() - runstarttime
    print( f"Runtime was {int(elapsedsecs/60)}m {int(elapsedsecs%60):02d}s" )

if __name__ == '__main__':
    main()