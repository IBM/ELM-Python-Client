##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import argparse
import csv
import getpass
import io
import json
import logging
import os
import os.path
import pprint as pp
import re
import socket
import sys
import time
import urllib3
import webbrowser
import concurrent.futures
import zipfile

import cryptography
import cryptography.fernet
import lxml.etree as ET
import requests
import urllib.parse

from elmclient import __meta__
from elmclient import rdfxml
from elmclient import server
from elmclient import utils

############################################################################

# ensure that all strings in requireds are in select, adding them if not
# (assumes no entry in requireds is a subset of a longer string already in select)
def ensure_select(select,requireds):
    if '*' in requireds:
        return '*'
    # if select is empty, return the new entries (assumes no duplicates!)
    if not select:
        return ",".join(requireds)
    selects = select.split(",")
    # a * means no point adding anything
    if '*' in selects:
        return '*'
    # check each of the requireds
    for required in requireds:
        if required not in selects:
            selects.append(required)
    return ",".join(selects)

############################################################################

def do_oslc_query(inputargs=None):
    print( f"Version {__meta__.version}" )
    inputargs = inputargs or sys.argv[1:]
    
    # get some defaults from the environment (which can be overridden on the commandline or the saved obfuscated credentials)
    JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
    USER        = os.environ.get("QUERY_USER"       ,"ibm" )
    PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
    JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
    APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
    LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,None )

    # setup arghandler
    parser = argparse.ArgumentParser(description="Perform OSLC query on a Jazz application, with results output to CSV (and other) formats - use -h to get some basic help")

    parser.add_argument('-f', '--searchterms', action='append', default=[], help='**APPS MAY NOT FULLY SUPPORT THIS** A word or phrase to search, returning ranked results - use once for each term and oslcquery will insert the quotes and commas"')
    parser.add_argument('-n', '--null', action='append', default=[], help='Post-filter: A property that must be null (empty) for the resource to be included in the results - you can specify this option more than once')
    parser.add_argument('-o', '--orderby', default='', help='**APPS MAY NOT FULLY SUPPORT THIS** A comma-separated list of properties to sort by - prefix with "+" for ascending, "-" for descending- if -f/--searchterms is specified this orders items with the same oslc:score - to speciy a leading -, use = e.g. -o=-dcterms:title')
    parser.add_argument('-p', '--projectname', default=None, help='Name of the project - omit to run a query on the application')
    parser.add_argument('-q', '--query', default='', help='Enhanced OSLC query (defaults to empty string which returns all resources)')
    parser.add_argument('-r', '--resourcetype', default=None, help='The app-specific type being searched, e.g. Requirement for RM, Configuration for GC - this can be the full URI from the query capability resource type,, a prefixed uri, or the unqiue last part of the query URL - also used for resolving ambiguous attribute names in -q/-s/-v/-n')
    parser.add_argument('-s', '--select', default='', help='A comma-separate list of properties that should be included in the results - NOTE the app may include additional properties, and may not include the requested properties')
    parser.add_argument('-u', '--unique', action="store_true", help="Post-filter: Remove results with an rm_nav:parent value which are not-unique in the results on dcterms:identifier - this keeps module artifacts (which don't have rm_nav:parent) and artifacts for modules (which don't have a module artifact)) - RELEVANT ONLY FOR DOORS Next!")
    parser.add_argument('-v', '--value', action='append', default=[], help='Post-filter: A property name that must have a value for the resource to be included in the results - you can specify this option more than once')
    parser.add_argument('-A', '--appstrings', default=None, help=f'A comma-seperated list of apps, the query goes to the first entry, default "{APPSTRINGS}". Each entry must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using environemnt variable QUERY_APPSTRINGS')
    parser.add_argument('-B', '--browser', default=None, help='Save results in HTML file and open in a browser')
    parser.add_argument('-C', '--component', help='The local component (optional, you *have* to specify the local configuration using -F)')
    parser.add_argument('-D', '--delaybetweenpages', type=float,default=0.0, help="Delay in seconds between each page of results - use this to reduce overall server load particularly for large result sets or when retrieving many properties")
    parser.add_argument('-E', '--globalproject', default=None, help="The global configuration project - optional if the globalconfiguration is unique in the gcm app")
    parser.add_argument('-F', '--configuration', default=None, help='The local configuration name')
    parser.add_argument('-G', '--globalconfiguration', default=None, help='The global configuration (you must not specify local config as well!) - you can specify the id, the full URI, or the config name')
    parser.add_argument('-H', '--saveconfigs', default=None, help='Name of CSV file to save details of the local project components and configurations')
    parser.add_argument('-I', '--totalize', action="store_true", help="For any column with multiple results, put in the total instead of the results")
    parser.add_argument("-J", "--jazzurl", default=JAZZURL, help=f"jazz server url (without the /jts!) default {JAZZURL} - Default can be set using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
    parser.add_argument('-L', '--loglevel', default=None,help=f'Set logging to file and (by adding a "," and a second level) to console to one of DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    parser.add_argument('-M', '--maxresults', default=None, type=int, help='Max number of results to retrieve a pagesize at a time, then the query is terminated. default is no limit')
    parser.add_argument('-N', '--noprogressbar', action="store_false", help="Don't show progress bar during query")
    parser.add_argument('-O', '--outputfile', default=None, help='Name of file to save the CSV to')
    parser.add_argument("-P", "--password", default=PASSWORD, help=f"user password, default {PASSWORD} - Default can be set using environment variable QUERY_PASSWORD - set to PROMPT to be asked for password at runtime")
    parser.add_argument('-Q', '--resolvenames', action="store_false", help="toggle name resolving off (default on) - can greatly speed up postprocessing but you'll get URIs rather than names")
    parser.add_argument('-R', '--nodefaultselects', action="store_true", help="Suppress adding default select like for rm rm_nav:folder and dcterms:identifier - can speed up postprocessing because e.g. no need to look up folder name")
    parser.add_argument('-S', '--sort', action="store_false", help="Don't sort results by increasing dcterms:identifier, as is done by default - specifying -o (orderby) disables automatic sorting by dcterms:identifier")
    parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    parser.add_argument("-U", "--username", default=USER, help=f"user id, default {USER} - Default can be set using environment variable QUERY_USER")
    parser.add_argument('-V', '--verbose', action="store_true", help="Show verbose info")
    parser.add_argument('-W', '--cachecontrol', action='count', default=0, help="Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and disables caching. Otherwise caching is continued from previous run(s).")
    parser.add_argument('-X', '--xmloutputfile', default=None, help='For each query result, GET the artifact and save to file with this base name plus the identifier (if present) - PROBABLY RELEVANT ONLY TO RM!')
    parser.add_argument('-Y', '--debugprint', action="store_true", help="Print the raw results")
    parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')

    # various options
    parser.add_argument('--nresults', default=-1, type=int, help="Number of results expected - used for regression testing - use `--nresults -1` to disable checking")
    parser.add_argument('--compareresults', default=None, help="TESTING UNFINISHED: saved CSV file to compare results with")
    parser.add_argument('--pagesize', default=0, type=int, help="Page size for OSLC query (default 0) use 0 to suppress paging (server may still page)")
    parser.add_argument('--typesystemreport', default=None, help="Load the specified project/configuration and then produce a simple HTML type system report of resource shapes/properties/enumerations to this file" )
    parser.add_argument('--cachedays', default=7,type=int, help="The number of days for caching received data, default 7. To disable caching use -WW. To keep using a non-default cache period you must specify this value every time" )
    parser.add_argument('--saverawresults', default=None, help="Save the raw results as XML to this path/file prefix - pages are numbered starting from 0000" )
    parser.add_argument('--saveprocessedresults', default=None, help="Save the processed results as JSON to this path/file" )
    parser.add_argument('--percontribution', action="store_true", help="When querying a GC, query once for each app-domain contribution in the GC tree, with added component and configuration columns in the result")
    parser.add_argument('--cacheable', action="store_true", help="Query results can be cached - use when you know the data isn't changing and you need faster re-run")
    parser.add_argument('--crossproject', action="store_true", help="For --percontribution GC queries follow gc contributions to other projects and query those too (requires access permission of course)")
    parser.add_argument('--threading', action="store_true", help="For --percontriubtion GC queries, use threading to parallelize queries with processing results UNTESTED")

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

    # make sure selects are clean - in particular, if * anywhere then make select just * - also ensures no duplicates
    args.select = ensure_select(args.select,args.select.split(","))

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

    if args.password is None or args.password=="PROMPT":
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
    theserver = server.JazzTeamServer(args.jazzurl, args.username, args.password, verifysslcerts=args.certs, jtsappstring=f"jts:{approots['jts']}", cachingcontrol=args.cachecontrol, cachefolder=cachefolder )

    # create all our apps (there will be a main app, the main reason for allowing more than one is when gc is needed)
    for appdom,approot in approots.items():
        allapps[appdom] = theserver.find_app( f"{appdom}:{approot}", ok_to_create=True )

    # get the main app - it's the one we're going to query - it was first in args.appstring
    app = allapps[themaindomain]
    config = None

    # decide if this is a project query or an application query
    if args.projectname:
        # project query
        if args.globalproject:
            if not args.globalconfiguration:
                raise Exception( "If you specify -E you _must_ specify -G" )
        else:
            if args.globalconfiguration:
                raise Exception( "If you don't specify -E you _must not_ specify -G" )

        # work out the global configuration
        gcproj = None
        gcconfiguri = None
        gcapp = allapps.get('gc',None)
        if not gcapp:
            if args.globalconfiguration:
                raise Exception( "gc app must be specified (usually second) in APPSTRINGS/-A to use a global configuration" )
        else:
            if args.globalconfiguration:
                # now find the configuration config
                # user can specify just an id
                if utils.isint(args.globalconfiguration):
                    # create GC URI using the id
                    gcconfiguri = gcapp.reluri( f"configuration/{args.globalconfiguration}" )
                else:
                    if args.globalconfiguration.startswith( 'http://') or args.globalconfiguration.startswith( 'https://' ):
                        if args.globalconfiguration.startswith( gcapp.reluri( "configuration" ) ):
                            # assume user specified a URI
                            gcconfiguri = args.globalconfiguration
                        else:
                            raise Exception( f"The -G globalconfiguration {args.globalconfiguration} isn't an integer id and doesn't start with the server gc path {gcapp.reluri( 'configuration' )}" )
                    else:
                        # do an OSLC query on either the GC app or the GC project
                        if args.globalproject:
                            # find the gc project to query in
                            gc_query_on = gcapp.find_project(args.globalproject)
                            if gc_query_on is None:
                                raise Exception( f"Project '{args.globalproject}' not found")
                        else:
                            gc_query_on = gcapp

                        # get the query capability base URL
                        qcbase = gc_query_on.get_query_capability_uri("oslc_config:Configuration")
                        # query for a configuration with title
                        print( f"querying for gc config {args.globalconfiguration}" )
                        conf = gc_query_on.execute_oslc_query( qcbase, whereterms=[['dcterms:title','=',f'"{args.globalconfiguration}"']], select=['*'], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'})
                        if len( conf.keys() ) == 0:
                            raise Exception( f"No GC configuration matches {args.globalconfiguration}" )
                        elif len( conf.keys() ) > 1:
                            raise Exception( f"Multiple matches for GC configuration {args.globalconfiguration}" )
                        gcconfiguri = list(conf.keys())[0]
                        logger.info( f"{gcconfiguri=}" )
                # check the gc config uri exists - a GET from it shouldn't fail!
                if not gcapp.check_valid_config_uri(gcconfiguri,raise_exception=False):
                    raise Exception( f"GC configuration URI {gcconfiguri} not valid!" )

        # find the project
        p = app.find_project(args.projectname)
        if p is None:
            print( f"Project '{args.projectname}' not found! Available projects are:" )
            projlist = app.list_projects()
            for p in projlist:
                print( f"  '{p}'" )
            raise Exception( f"Project '{args.projectname}' not found")
        
        # assert default for the component name to be the same as the project name
        # this might need to be done more intelligently, to handle e.g. when the default component has been archived
        # for GC the query might be to find a component, so don't override if a component hasn't been specified!
        if themaindomain != "gc" or args.resourcetype != 'Component':
            if args.component is None:
                if p.is_optin:
                    if args.globalconfiguration is None:
                        print( f"Warning - project '{args.projectname}' is opt-in but you didn't specify a component or a global configuration - using default component '{args.projectname}' - if this component name doesn't exist you'll get an error message" )
                        args.component = args.projectname
        # not all apps support components, and even if the app does this project may not be opt-in
        if app.supports_components and not ( themaindomain == "gc" and args.resourcetype == 'Component'):
            if not p.singlemode and args.component is None and args.globalconfiguration is None:
                # neither GC nor component provided, assume component name is same as project name
                args.component = args.projectname
#                print( f"Warning - project '{args.projectname}' is opt-out, assuming the component has the same name as the project" )
#                raise Exception( f"Project {args.projectname} supports components so you must provide a component name or use a global configuration" )
            if p.singlemode and args.globalconfiguration is None:
                # opt-out, the "component" name is the same as the project name
                args.component = args.projectname
            if args.saveconfigs:
                comps = p.report_components_and_configurations()
                logger.debug( f"{comps=}" )
                rows = []
                for compk,compv in comps.items():
                    row = {}
                    row['componentname'] = compv['name']
                    row['componenturi'] = compk
                    # keep a reference copy of this row to use as the base of the row for each config
                    rowbase = dict(row)
                    logger.debug( f"{compv['configurations']=}" )
                    for confk,confv in compv['configurations'].items():
                        row['config_name'] = confv['name']
                        row['config_uri'] = confk
                        row['conftype'] = confv['conftype']
                        row['created'] = confv.get('created','' )
                        rows.append(row)
                        # restart from the rowbase for the next config
                        row = dict(rowbase)

                with open(args.saveconfigs,"w",newline='') as csvoutfile:
                    fieldnames = list(rows[0].keys())
                    logger.debug( f"{fieldnames=}" )
                    csvwriter = csv.DictWriter(csvoutfile,fieldnames)
                    csvwriter.writeheader()
                    csvwriter.writerows(rows)
            if args.component:
                c = p.find_local_component(args.component)
                if not c:
                    print( f"Component '{args.component}' not found in project {args.projectname} - Available components are:" )
                    complist = p.list_components()
                    for c in complist:
                        print( f"  '{c}'" )
                    raise Exception( f"Component '{args.component}' not found in project {args.projectname}" )
            else:
                c = None
            # assert the default configuration for this component if none is specified
            if args.configuration is None and args.globalconfiguration is None:
                args.configuration = c.initial_stream_name()
                if not p.singlemode:
                    # only warn that config not provided/assumed to be Initial Stream for an opt-in project
                    print( f"Warning - project '{args.projectname}' is opt-in but for component '{args.component}' you didn't specify a local configuration - using default stream '{c.initial_stream_name()}'" )
            logger.info( f"{args.configuration=}" )
            if p.is_optin:
                if ( args.configuration or p.singlemode ) and args.globalconfiguration is None:
                    if p.singlemode:
                        if args.configuration is None:
                            # default to the stream
                            args.configuration = c.get_default_stream_name()
                    config = c.get_local_config(args.configuration)
                    if config is None:
                        print( f"Configuration '{args.configuration}' not found in component {args.component} - available configs are:" )
                        for c in c.list_configs():
                            print( f"  '{c}'" )
                        raise Exception( f"Configuration '{args.configuration}' not found in component {args.component}" )
                    
                    queryon = c

                elif gcconfiguri:
                    # we're doing a GC-based query on the project - UNLESS a local config is also specified in which case the GC can be used to find the local config
                    # using the GC contributions tree
                    # and then the query is done on the local config and NOT using the gc config
                    if args.component:
                        print( f"{c=}" )
                        if c:
                            config = c.get_local_config(args.configuration,gcconfiguri)
                            print( f"Selected local config contributing this component {config}" )
                            queryon = c
                        else:
                            config = p.get_local_config(args.configuration)
                            queryon = p
                        if config is None:
                            raise Exception( "Local config {args.configuration} not found!" )
                        gcconfiguri = None
                    else:
                        config = None
                        queryon = p
                else:
                    raise Exception( f"Project {args.projectname} is opt-in so you must provide a local or global configuration" )

            else:
                queryon = p
            queryon.set_local_config(config,gcconfiguri)
            logger.debug( f"setting {config=} {gcconfiguri=}" )
            if args.verbose:
                if config:
                    print( f"Local config {config}" )
                if gcconfiguri:
                    print( f"Global config {gcconfiguri}" )
                
            # we're querying the component
        else:
            if args.saveconfigs:
                raise Exception( "You specified --saveconfigs but project doesn't support components so can't have configurations - nothing saved" )
            # doesn't support components - we're querying the project
            queryon = p
        # setup the select
        if args.value or args.null:
            args.select = ensure_select(args.select,args.value+args.null)

        if args.sort:
            # ensure identifier is in select if sorting is requested
            args.select = ensure_select(args.select,[app.identifier_uri])

        # handle returning unique results (for RM)
        if args.unique:
            if themaindomain != "rm":
                raise Exception( "Only use --unique with rm" )
            # ensure that identifier and parent are in the results
            args.select = ensure_select(args.select,[app.identifier_uri,'rm_nav:parent'])

        # ensure some important attributes are always in the output
        # ensure that identifier and parent are always in the results
        if themaindomain == 'rm':
            if not args.nodefaultselects:
                args.select = ensure_select(args.select,[app.identifier_uri,'rm_nav:parent'])
        elif themaindomain == 'ccm':
            args.select = ensure_select(args.select,[app.identifier_uri])
        elif themaindomain == 'gc' or themaindomain == 'qm':
            args.select = ensure_select(args.select,[app.identifier_uri])

        # get the resource type being queried - this is needed to find the correct query capability
        args.resourcetype = args.resourcetype or queryon.default_query_resource

    else:
        # app-level query
        queryon = app
        if not app.has_typesystem:
            raise Exception( f"The {app.domain} application does not support application-level OSLC Queries - perhaps you meant to provide a project name using -p" )

    #ensure type system is loaded, even if it won't be used
    queryon.load_types()
                                    
    if args.typesystemreport:
        # ensure output folder exists
        args.typesystemreport = os.path.abspath(args.typesystemreport)
        outputpath = os.path.split(args.typesystemreport)[0]
#        print( f"{outputpath=}" )
        if not os.path.isdir( outputpath ):
#            print( f"creating {outputpath=}" )
            os.makedirs( outputpath, exist_ok=True)
        
        open( args.typesystemreport, "wt").write( queryon.report_type_system() )
        # display the report
        url = f'file://{os.path.abspath(args.typesystemreport)}'
        webbrowser.open(url, new=2)  # open in new tab

    # ensure csv output folder exists
    if args.outputfile:
        # ensure the output folder exists
        args.outputfile = os.path.abspath(args.outputfile)
        outputpath = os.path.split(args.outputfile)[0]
#        print( f"{outputpath=}" )
        if not os.path.isdir( outputpath ):
#            print( f"creating {outputpath=}" )
            os.makedirs( outputpath, exist_ok=True)
            
    # erase the output file (also checks that it isn't open in Excel) before doing a possibly lengthy query :-)
    if args.outputfile and os.path.isfile(args.outputfile):
        os.remove(args.outputfile)

    if args.percontribution:
        results = {}
        futureresults = []
        workers = 4 if args.threading else 1
        def thread_fn(i,queryon,configuri):
            print( f"Thread start {i}" )
            queryon.set_local_config(configuri)
            try:
                thisresults = queryon.do_complex_query( args.resourcetype, querystring=args.query, searchterms=args.searchterms, select=args.select, isnulls=args.null, isnotnulls=args.value
                            ,orderby=args.orderby
                            ,show_progress=args.noprogressbar
                            ,verbose=args.verbose
                            ,maxresults=args.maxresults
                            ,delaybetweenpages=args.delaybetweenpages
                            ,pagesize=args.pagesize
                            ,resolvenames = args.resolvenames
                            ,totalize=args.totalize
                            ,saverawresults=args.saverawresults
                            ,addcolumns={'$contriburi':contriburi,'$compuri':compuri}
                            ,cacheable=args.cacheable
                            )
            except KeyboardInterrupt:
                raise Exception( "Control-c" )
            print( f"Thread finish {i=}" )
            return thisresults
        with concurrent.futures.ThreadPoolExecutor(max_workers = workers) as executor:
            # get all the contributions in this domain, and the component they're in - these will be added to the results
            contribs = p.get_our_contributions(gcconfiguri)
            for i,(contriburi,compuri) in enumerate(sorted(contribs,key=lambda v:v[0])):
                print( f"{i+1}/{len(contribs)} {contriburi=} {compuri=}" )
                # find the component in teh config
                queryon = p.find_local_component(compuri)
                if queryon is None:
                    print( f"Component not found from {compuri}" )
                    if args.crossproject:
                        # this component isn't in our current project
                        # try to create a component for it and add to current project
                        queryon = p.add_external_component(compuri)
                        if queryon is None:
                            raise Exception( f"Can't add external component for {compuri}" )
                        else:
                            print( f"Added external component {queryon=} for {compuri}" )
                    else:
                        raise Exception( "Component {compuri} not found in current project - maybe you need to use --crossproject?" )
                # check the comonent is accessible (may have been archived!)
                if not app.is_accessible( compuri ):
                    print( f"**** Archived component {compuri} !")
                    continue
                # check if the config is accessible (may have been archived!)
                if not app.is_accessible( contriburi ):
                    print( f"**** Archived configuration {contriburi} !")
                    continue
                if not args.threading:
                    # work synchronously
                    results.update(thread_fn(i,queryon,contriburi))
                else:
                    # get the results later
                    futureresults.append(executor.submit(thread_fn,i,queryon,contriburi))
            # now if working asynchronously retrieve the results
            for res in futureresults:
                results.update(res.result())
        if False:
            # set the config ready to do the query
            queryon.set_local_config(contriburi)
            # now do a query for each contribution
            thisresults = queryon.do_complex_query( args.resourcetype, querystring=args.query, searchterms=args.searchterms, select=args.select, isnulls=args.null, isnotnulls=args.value
                        ,orderby=args.orderby
                        ,show_progress=args.noprogressbar
                        ,verbose=args.verbose
                        ,maxresults=args.maxresults
                        ,delaybetweenpages=args.delaybetweenpages
                        ,pagesize=args.pagesize
                        ,resolvenames = args.resolvenames
                        ,totalize=args.totalize
                        ,saverawresults=args.saverawresults
                        ,addcolumns={'$contriburi':contriburi,'$compuri':compuri}
                        ,cacheable=args.cacheable
                        )
            results.update(thisresults)
    else:    
        # do the actual OSLC query
        results = queryon.do_complex_query( args.resourcetype, querystring=args.query, searchterms=args.searchterms, select=args.select, isnulls=args.null, isnotnulls=args.value
                        ,orderby=args.orderby
                        ,show_progress=args.noprogressbar
                        ,verbose=args.verbose
                        ,maxresults=args.maxresults
                        ,delaybetweenpages=args.delaybetweenpages
                        ,pagesize=args.pagesize
                        ,resolvenames = args.resolvenames
                        ,totalize=args.totalize
                        ,saverawresults=args.saverawresults
                        ,cacheable=args.cacheable
                        )

    if args.debugprint:
        pp.pprint(results)

    # try to get a key as an integers - no exception if the string isn't an integer
    def safeint(s,nonereturns=0):
        try:
            return int(s)
        except:
            return nonereturns

    if args.sort and not args.orderby and len(results)>0 and ( app.identifier_uri in args.select or '*' in args.select):
        results =  {k: results[k] for k in sorted(list(results.keys()), key=lambda k: safeint(results[k].get(app.identifier_name)) or safeint(results[k].get(app.identifier_uri)))}

    # now process post-filters
    if args.unique:
        # remove ones with rm_nav:parent which don't have a unique ID
        todeletes = []
        seenids = {}
        # first scan
        for kuri, valuedict in results.items():
            id = valuedict.get(app.identifier_name) or valuedict.get(app.identifier_uri)
            if id is None:
                todeletes.append(kuri)
            if valuedict.get('rm_nav:parent') is not None:
                # this is a core artifact
                # save the ID and uri so we can delete it later
                if id in seenids.keys():
                    # add THIS uri to the list to delete
                    seenids[id] = kuri
                    todeletes.append(kuri)
                else:
                    seenids[id] = kuri
            else:
                # this is a module artifact
                # no parent - but this might be seen before the core artifact
                # check if already seen as a core artifact
                if id in seenids.keys():
                    todeletes.append(seenids[id])
                else:
                    # not seen before - but there must be a core artifact but we don't know its uri
                    # that will be known when the core artifact is seen
                    # put a rubbish value in which should never be used!
                    seenids[id] = id
        for todelete in todeletes:
            if todelete in results.keys():
                del results[todelete]
            else:
                pass

    resultsentries = "entries" if len(results.keys())!=1 else "entry"

    if args.saveprocessedresults:
        open(args.saveprocessedresults+"_before.json","wt").write(json.dumps(results))
        
    print( f"Query result has {len(results.keys())} {resultsentries}" )

    # COMPARE IS UNTESTED!
    if args.outputfile or args.browser or args.compareresults:
        # write to CSV and/or compare with CSV
        # FIRST merge columns with same name - this merges types across components based on name
        # which is only need for queries in a GC. NOTE this doesn't attempt to use RDF URIs which it probably should :-o
        # but having different (as in totally different) types with same name is not exactly human-friendly!
        # build a list of all properties - these will be column headings for the CSV
        headings = []
        rawheadings = [] # this is used so headings are only resolved once - the raw headings are remembered in this list
        actualheadings = {}
        for k, v in list(results.items()):
            # add the URI to the value so it will be exported (first char is $ so the uri will always be in first column after the column titles are sorted)
            v["$uri"] = k
            for sk in list(v.keys()):
                # try to resolve heading names
                sk1 = queryon.resolve_uri_to_name(sk) if args.resolvenames else sk
                if sk not in rawheadings:
                    rawheadings.append(sk)
                    if args.resolvenames and sk1 == sk: # if heading name hasn't been resolved before
                        sk1 = queryon.resolve_uri_to_name(sk) # always resolve - only for headings
                    if sk1 not in headings:
                        headings.append(sk1)
                    actualheadings[sk] = sk1
#                    # also store the reverse actual->raw
#                    actualheadings[sk1] = sk
                    logger.info( f"Mapping {sk} to {sk1}" )
                else:
                    sk1 = actualheadings[sk]
                if sk!=sk1:
                    logger.debug(f"renaming {sk=} {sk1=}" )
                    # if ernaming need to merge column content!
                    existing = v[sk]
                    otherexisting = v.get(sk1)
                    del v[sk]
                    if existing and otherexisting:
                        if existing != otherexisting:
                            logger.info( f"MERGE {existing=} {otherexisting=}" )
                    v[sk1] = otherexisting if otherexisting else existing

        fieldnames = sorted(headings)
        
        if args.outputfile:
            # produce a CSV file
            with open(args.outputfile, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, restval='')
                writer.writeheader()
                for k, v in results.items():
                    writer.writerow(v)
                    
        if args.browser:
            # produce an html file and also open it in your browser
            with open(args.browser, 'w', newline='', encoding='utf-8-sig') as htmlfile:
                htmlfile.write( "<html><body><table><tr>")
                for fieldname in fieldnames:
                    htmlfile.write( f"<th>{fieldname}</th>" )
                htmlfile.write( "</tr>" )
                for k, v in results.items():
                    htmlfile.write( "<tr>" )
                    for fieldname in fieldnames:
                        htmlfile.write( f"<td>{v.get( fieldname,'' )}</td>" )
                    htmlfile.write( "</tr>" )
                htmlfile.write( "</table>" )
                htmlfile.write( "</body></html>" )
            # display the report
            url = f'file://{os.path.abspath(args.browser)}'
            webbrowser.open(url, new=2)  # open in new tab
            
        if args.saveprocessedresults:
            open(args.saveprocessedresults+"_after.json","wt").write(json.dumps(results))

        if args.compareresults:
            # a simple test by comparing the received results with a saved CSV from a previous run
            # load the saved CSV
            with open(args.compareresults, newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                savedheadings = list(reader.fieldnames)
                savedrows = []
                for row in reader:
                    savedrows.append(row)
            # compare the headings
            testfailed=False
            for h in fieldnames:
                if h not in savedheadings:
                    logger.error( f"Result heading {h} not in saved headings {savedheadings}" )
                    testfailed=True
                else:
                    savedheadings.remove(h)
            if len(savedheadings)!=0:
                logger.error( f"Saved headings {savedheadings} not in results!" )
                testfailed=True
            if testfailed:
                raise Exception( "Headings different - test failed" )
            else:
                logger.info( "Test headers matched" )

            # compare the results
            testfailed=False
            i = 1
            for k,savedrow in zip(results.keys(),savedrows):
                row = results[k]
                for h in fieldnames:
                    if h not in row:
                        continue
                    # check for a datetime valuem if it is then don't compare the results
                    if row[h] is not None:
                        if not re.match(r'\d\d\d\d-\d\d-\d\d(T\d\d:\d\d:\d\d((\.|,)\d\d\d)?(Z|[+-]\d\d:\d\d)?)?',str(row[h])):
                            if str(row[h]) != str(savedrow[h]):
                                logger.error(f"Row {i} column {h} result {row[h]} is different from saved result {savedrow[h]}!")
                                testfailed=True
                        else:
                            logger.debug( f"Skipped comparison row {i} field {h} because it looks like a datetime" )
                    else:
                        if savedrow[h] is None or savedrow[h]=='':
                            pass
                        else:
                            raise Exception( f"Difference found field {h}: {row[h]} with {savedrow[h]}"  )

                i += 1
            if testfailed:
                raise Exception( "Result contents different - test failed" )
            else:
                logger.info( "Test contents matched" )

    if args.nresults >= 0:
        if len(results.keys()) != args.nresults:
#            print( f"There are {len(results.keys())} results but {args.nresults} expected - Failed :-(" )
            raise Exception( f"There are {len(results.keys())} results but {args.nresults} expected - Failed :-(" )
        else:
            print( f"{len(results.keys())} results and {args.nresults} expected - Passed :-)" )

    if args.xmloutputfile is not None:
        # retrieve all resources in the results to XML
        # ensure output folder exists
        args.xmloutputfile = os.path.abspath(args.xmloutputfile)
        outputpath = os.path.split(args.xmloutputfile)[0]
#        print( f"{outputpath=}" )
        if not os.path.isdir( outputpath ):
#            print( f"creating {outputpath=}" )
            os.makedirs( outputpath, exist_ok=True)
    
        # intended for RM (not sure what it will do for the other apps): retrieve all the result resources (as RDF-XML) and store to one file per resource
        unknownid = 1
        retrieved = {}
        for k in results.keys():
            if k in retrieved:
                logger.info( f"Already retrieved {k}" )
                continue
            logger.info( f"Retrieving XML for {k}" )
            retrieved[k]=True
            # get the resource from uri k
            params = {}
            try:
                xml1 = queryon.execute_get_rdf_xml( k, params=params, intent="Retrieve resource RDF-XML" )
            except requests.HTTPError:
                # this happens for e.g. Attribute Type  http://www.w3.org/2001/XMLSchema#dateTime
                print( f"Cannot retrieve URL {k} - skipped" )
                continue
            except AttributeError:
                try:
                    xml1 = queryon.execute_get_rdf_xml( k, params=params, intent="Retrieve resource RDF-XML" )
                except:
                    raise
            # save to filename based on identifier
            if app.identifier_name in results[k] or app.identifier_uri in results[k]:
                fname = args.xmloutputfile + "_" + str((results[k].get(app.identifier_name) or results[k].get(app.identifier_uri)))
                logger.info(f"Writing XML for id {results[k].get(app.identifier_uri)} or {results[k].get(app.identifier_name)} to {fname}" )
            else:
                fname = args.xmloutputfile + "_unknownid_" + str(unknownid)
                logger.info(f"Writing XML for UNKNOWN id to {fname}")
                unknownid += 1
            inc = ""
            while os.path.isfile(fname + inc + ".xml"):
                fullfname = fname + inc + ".xml"
                logger.info( f"Warning file {fullfname} already exists (did you delete existing files? Otherwise it's a core and Module artifact) - adding an _" )
                inc += "_"
            fname += inc
            open(fname + ".xml", "wb").write(ET.tostring(xml1.getroot()))
            isuri = rdfxml.xml_find_element(xml1, ".//oslc:instanceShape")
            if isuri is not None:
                logger.info( f"Retrieving instanceshape {isuri}" )
                isuri = isuri.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX['rdf'])
                # now download it
                try:
                    xml2 = queryon.execute_get_rdf_xml(isuri, params=params, intent="Retrieve RDF-XML for a resource (1)" )
                except AttributeError:
                    try:
                        xml2 = queryon.execute_get_rdf_xml(isuri, params=params, intent="Retrieve RDF-XML for a resource (2)" )
                    except:
                        raise
                open(fname + "_shape.xml", "wb").write(ET.tostring(xml2.getroot()))
    return 0

def main():
    runstarttime = time.perf_counter()
    do_oslc_query(sys.argv[1:])
    elapsedsecs = time.perf_counter() - runstarttime
    print( f"Runtime was {int(elapsedsecs/60)}m {int(elapsedsecs%60):02d}s" )

if __name__ == '__main__':
    main()
