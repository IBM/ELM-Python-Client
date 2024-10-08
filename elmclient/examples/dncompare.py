##
## © Copyright 2024- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# use the DN Compare API https://jazz.net/wiki/bin/view/Main/DNGReportableRestAPI#Comparison_schema_and_API
#

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
from elmclient import _rm

import tqdm

############################################################################

def do_compare(inputargs=None):
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

    parser.add_argument('projectname', default=None, help='Name of the project')
    parser.add_argument('config1', default=None, help='Source configuration')
    parser.add_argument('config2', default=None, help='Target configuration')
    parser.add_argument('-A', '--appstrings', default=None, help=f'A comma-seperated list of apps, the query goes to the first entry, default "{APPSTRINGS}". Each entry must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using environemnt variable QUERY_APPSTRINGS')
    parser.add_argument('-C', '--component', help='The local component - required if component name is different from the project')
    parser.add_argument("-I", "--include", default=None, help="Specify includeItems as a comma-separated list from: changeSets,types,folders,artifacts" )
    parser.add_argument("-J", "--jazzurl", default=JAZZURL, help=f"jazz server url (without the /jts!) default {JAZZURL} - Default can be set using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
    parser.add_argument('-L', '--loglevel', default=None,help=f'Set logging to file and (by adding a "," and a second level) to console to one of DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    parser.add_argument('-N', '--progressbar', action="store_false", help="Don't show progress bar during query")
    parser.add_argument("-P", "--password", default=PASSWORD, help=f"user password, default {PASSWORD} - Default can be set using environment variable QUERY_PASSWORD - set to PROMPT to be asked for password at runtime")
    parser.add_argument('-Q', '--alwayscache', action="store_true", help="Always cache everything (useful to speed up testing)")
    parser.add_argument('-S', '--schemafile', default=None, help='Name of file to save the schema to')
    parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    parser.add_argument("-U", "--username", default=USER, help=f"user id, default {USER} - Default can be set using environment variable QUERY_USER")
    parser.add_argument('-V', '--verbose', action="store_true", help="Show verbose info")
    parser.add_argument('-W', '--cachecontrol', action='count', default=0, help="Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and disables caching. Otherwise caching is continued from previous run(s).")
    parser.add_argument('-X', '--xmloutputfile', default=None, help='Name of the file to save the complete XML results to')
    parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')
    
    # other options
    parser.add_argument('--cachedays', default=7,type=int, help="The number of days for caching received data, default 7. To disable caching use -WW. To keep using a non-default cache period you must specify this value every time" )
    parser.add_argument('--cacheable', action="store_true", help="Query results can be cached - use when you know the data isn't changing and you need faster re-run")

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
    config = None

    if not app.supports_components:
        raise Exception( f"App {app} doesn't support components!" )
        
    # find the project
    p = app.find_project(args.projectname)
    if p is None:
        print( f"Project '{args.projectname}' not found! Available projects are:" )
        projlist = app.list_projects()
        for p in projlist:
            print( f"  '{p}'" )
        raise Exception( f"Project '{args.projectname}' not found")
        
    if not p.is_optin and not p.singlemode:
        raise Exception( "Project must be opt-in!" )
        
    # assert default for the component name to be the same as the project name
    # this might need to be done more intelligently, to handle e.g. when the default component has been archived
    if args.component is None:
        args.component = args.projectname
                    
    p.load_components_and_configurations()
        
    if args.component:
        c = p.find_local_component(args.component)
        if not c:
            print( f"Component '{args.component}' not found in project {args.projectname} - Available components are:" )
            complist = p.list_components()
            for c in complist:
                print( f"  '{c}'" )
            raise Exception( f"Component '{args.component}' not found in project {args.projectname}" )
    else:
        raise Exception( "NO COMPONENT" )

    ########################################################
    # use the comparison API
    # need to find the source and target urls, and the includeItems
    
    c.load_configs()

    # find src and dest configs
    config_s = c.get_local_config( args.config1 )
    if not config_s:
        raise Exception( f"Source config {args.config1} not found!" )
        
    config_d = c.get_local_config( args.config2 )
    if not config_d:
        raise Exception( f"Target config {args.config2} not found!" )
        
    if config_d == config_s:
        raise Exception( "Both configurations are the same!" )

    # call the compare API
    # https://server.ip:9443/rdm/publish/diff?sourceConfigUri=XXX&targetConfigUri=YYYY
    compurl = p.reluri( "publish/diff" )
    params={'sourceConfigUri': config_s, 'targetConfigUri': config_d }
    
    # check the includeItems
    includeItems = [ "changeSets", "types", "folders", "artifacts" ]
    if args.include:
        items = args.include.split( "," )
        for item in items:
            if item not in includeItems:
                raise Exception( f"include value {item} isn't in {includeItems}" )
        # add includeItems to the query parameters
        params["includeItems"] = args.include
        
    allresults_x = None
    nread = 0

    if args.progressbar:
        pbar =  tqdm.tqdm(total=100)
        pbarcreated=True
    else:
        pbar = contextlib.nullcontext()
        pbarcreated=False

    with pbar:
        # repeat until no more pages
        while compurl:
            results = p.execute_get_rdf_xml( compurl, params=params, headers=None, return_etag = False, return_headers=False)
            # show the results
            tree = results.getroot()
            # get the link for the next page (if present)
            if tree.get( "rel","" ) == "next":
                compurl = tree.get("href",None)
            else:
                compurl = None
            # and ensure we don't provide params when fetching the next page - everything necessary is included in the href
            params = None
            # find the total count
            total = int(tree.get("{http://www.ibm.com/xmlns/rrm/1.0/}totalCount", 0 ))
            if allresults_x is None:
                allresults_x = tree
                nread += total
            else:
                for child in tree:
                    allresults_x.append( child )
                    nread += 1
                # update the totalcount
                allresults_x.set( "{http://www.ibm.com/xmlns/rrm/1.0/}totalCount",str(nread) )
            if pbarcreated is None:
                pbar = tqdm.tqdm(initial=nread, total=total,smoothing=1,unit=" results",desc="Artifacts changed")
                pbarcreated = True
            else:
                pbar.update(total)
        if pbarcreated:
            pbar.close()
            
    if args.xmloutputfile:
        print( f"Saving results to {args.xmloutputfile}" )
        open( args.xmloutputfile, "wb" ).write( ET.tostring( allresults_x ) )

    if args.schemafile:
        print( f"Retrieving schema to {args.schemafile}" )
        # get the schema
        schema_x = p.execute_get_rdf_xml( p.reluri( "publish/comparisons?metadata=schema"))
        # save to file
        open( args.schemafile, "wb" ).write( ET.tostring( schema_x ) )

def main():
    runstarttime = time.perf_counter()
    do_compare(sys.argv[1:])
    elapsedsecs = time.perf_counter() - runstarttime
    print( f"Runtime was {int(elapsedsecs/60)}m {int(elapsedsecs%60):02d}s" )

if __name__ == '__main__':
    main()
