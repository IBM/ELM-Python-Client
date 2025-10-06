##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# use the validate API
# NOTE this doesn't have the capabilities of the 7.0.2 ifix025+ TRS validation UI!
#

import argparse
import csv
import getpass
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

def isintstring(s):
    try:
        int(s.strip())
        return True
    except:
        pass
    return False


############################################################################

def do_validate(inputargs=None):
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
    parser = argparse.ArgumentParser(description="Use the Validate APU to list feed, validate a feed, get validaiton results")

    # the holder for sub-parsers
    subparsers = parser.add_subparsers(help='sub-commands',dest='subparser_name')

    # main arguments
    parser.add_argument('-A', '--appstrings', default=None, help=f'A comma-seperated list of apps, the validate API calls go to the first entry, default "{APPSTRINGS}". Each entry must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using environemnt variable QUERY_APPSTRINGS')
    parser.add_argument("-J", "--jazzurl", default=JAZZURL, help=f"jazz server url (without the /jts!) default {JAZZURL} - Default can be set using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
    parser.add_argument('-L', '--loglevel', default=None,help=f'Set logging to file and (by adding a "," and a second level) to console to one of DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    parser.add_argument('-N', '--noprogressbar', action="store_false", help="Don't show progress bar during query")
    parser.add_argument("-P", "--password", default=PASSWORD, help=f"user password, default {PASSWORD} - Default can be set using environment variable QUERY_PASSWORD - set to PROMPT to be asked for password at runtime")
    parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    parser.add_argument("-U", "--username", default=USER, help=f"user id, default {USER} - Default can be set using environment variable QUERY_USER")
    parser.add_argument('-V', '--verbose', action="store_true", help="Show verbose info")
    parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy, default is 8888 - used if found to be active - set to 0 to disable')

    # saved credentials
    parser.add_argument('-0', '--savecreds', default=None, help="Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, appstring, username and password")
    parser.add_argument('-1', '--readcreds', default=None, help="Read obfuscated credentials from file - completely overrides commandline/environment values for jazzurl, jts, appstring, username and password" )
    parser.add_argument('-2', '--erasecreds', default=None, help="Wipe and delete obfuscated credentials file" )
    parser.add_argument('-3', '--secret', default="N0tSeCret-", help="SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater security) - only affects if using -0 or -1" )
    parser.add_argument('-4', '--credspassword', action="store_true", help="Prompt user for a password to save/read obfuscated credentials (make this longer for greater security)" )

    # sub parsers for the validate actions
    parser_list = subparsers.add_parser('list', help='List feeds on this app' )
    parser_validate = subparsers.add_parser('validate', help='Validate a feed on this app' )

    parser_validate.add_argument( 'feedid', help='The feed id - this can be an integer corresponding to the index in the list of feeds, or a unique string (case-sensitive!) which matches part of or all of exactly one feed ID or name')
    parser_validate.add_argument('-f', '--full', action="store_true", help="Same as the web UI option. If true the entire TRS feed will be checked, which takes much longer. This may return more accurate results. This does not discard past validation results, so future validations can still be incremental. If this option consistently returns different results then you may need to also reset the incremental data")
    parser_validate.add_argument('-i', '--resetIncrementalData', action="store_true", help="Same the web UI option. If true the system will discard past validation results and recheck the entire feed again. Otherwise, only changes since last time will be validated. This option is normally only needed if indicated so by IBM support.")
    parser_validate.add_argument('-r', '--repair', action="store_true", help="Use to automatically resolve problems encountered in the feed. Ignored if not supported by the feed.")

    args = parser.parse_args(inputargs)
    
#    print( f"{args=}" )

    # common code with oslcquery to do credentials etc.
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

    # first work out the hostname and port
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

    # create our "server"
    theserver = server.JazzTeamServer(args.jazzurl, args.username, args.password, verifysslcerts=args.certs, jtsappstring=f"jts:{approots['jts']}" )

    # create all our apps (there will be a main app, the main reason for allowing more than one is when gc is needed)
    for appdom,approot in approots.items():
        allapps[appdom] = theserver.find_app( f"{appdom}:{approot}", ok_to_create=True )

    # get the main app - it's the one we're going to query - it was first in args.appstring
    print( f"Working with the Validate API for {themaindomain}" )
    app = allapps[themaindomain]
    config = None

    # now take whatever action
    if args.subparser_name == 'list':
        # https://jazz.net/rm/doc/scenario?id=GetTrsFeeds
        jsonresults = app.listTRSFeeds()
#        print( f"{jsonresults=}" )
        for i,feed in enumerate(jsonresults):
#            print( f"{feed=}" )
            print( f"Feed index {i} Id: '{feed['id']}' name: '{feed['name']}' Description: '{feed['description']}' URL: '{feed['url']}' Supports repair: '{feed['supportsRepair']}'" )
        pass
    elif args.subparser_name == 'validate':
        # https://jazz.net/rm/doc/scenario?id=InitiateTrsValidation
        
        # get the list of feeds from the validate API :-)
        feeds = app.listTRSFeeds()
        
        # work out what the feedid matches
        # an integer is the number in the list (0-based)
        if isintstring( args.feedid ):
            feedid = int( args.feedid )
            if feedid < 0 or feedid > len(feeds):
                raise Exception( f"Invalid feed number {feedid}" )
            theid = feeds[feedid]['id']
            name = feeds[feedid]['name']
            print( f"Using list entry {feedid} which has {theid=} and {name=}" )
#            print( f"Validating feed '{theid}' '{feeds[feedid]['name']}'" )
#            theid = feeds[id]['id']
        # or try to match a string against the feed IDs or names - zero or >1 match is an error!
        else:
            matches = 0
            firstid = -1
            for id,f in enumerate( feeds ):
                if args.feedid in f['id']:
                    matches += 1
                    firstid = id
                if args.feedid in f['name']:
                    matches += 1
                    firstid = id
                    
            # now check for 0 or >1 matches
            if matches == 0:
                raise Exception( f"No id or name contains '{args.feedid}'" )
            if matches > 1:
                raise Exception( f"id '{args.feedid}' matches more than one id or name" )
            theid = feeds[firstid]['id']
            print( f"Validating feed '{theid}' '{feeds[firstid]['name']}'" )
        
        result = app.validateTRSFeed( theid, repair=args.repair, resetIncrementalData=args.resetIncrementalData, full=args.full )
#        print( f"{result=}" )
        summary = result.get('summary',{})
        additionalCount = summary.get('additionalCount',-1)
        missingCount = summary.get('missingCount',-1)
        repairCount = summary.get('repairCount',-1)
        
        print( f"Results: {additionalCount=} {missingCount=} {repairCount=}" )
    else:
        raise Exception( f"Action {args.subparser_name} not recognized" )

    return 0

def main():
    runstarttime = time.perf_counter()
    do_validate(sys.argv[1:])
    elapsedsecs = time.perf_counter() - runstarttime
    print( f"Runtime was {int(elapsedsecs/60)}m {int(elapsedsecs%60):02d}s" )

if __name__ == '__main__':
    main()
