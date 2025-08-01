##
## © Copyright 2025- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# API to start/stop/report on custom scenarios
#
# See https://jazz.net/wiki/bin/view/Deployment/CreateCustomScenarios
#
# NOTE you MUST enable the Scenario Details and Scenario Metrics MBeans in your app to be able to see the information about scenario execution
#

import os
import sys
import argparse
import logging
import urllib.parse
import json
import pprint

pp = pprint.PrettyPrinter(indent=4)

from elmclient import server
from elmclient import utils
from elmclient import httpops

SCENARIOSERVICE = 'service/com.ibm.team.repository.service.serviceability.IScenarioRestService/scenarios'
STARTSCENARIO = '/startscenario'
STOPSCENARIO = '/stopscenario'

CUSTOMSCENARIO_SAVE_PREFIX = ".customerscenario_"

class ScenarioDetails:
    def __init__( self, scenarioDetails ):
        pass
    
class CustomScenarios_Mixin():
    def startScenario( self, scenarioName, *, addDateToName=False, persistToFile=None, autosave=True ):
        # {"scenarioName":"MyCustomExpensiveScenario"}
        # This generates an rm.log entry like: 2025-06-17T08:00:13,771-0700 [TID: 7A90ADD8][][Default Executor-thread-434 @@ 08:00 ibm <python-requests/2.32.3@9.111.37.111> /rm/service/com.ibm.team.repository.service.serviceability.IScenarioRestService/scenarios/startscenario]  INFO ry.service.internal.serviceability.ScenarioService - A new instance of the scenario: asd5 has started:_xbChsEuLEfCule9gtHkh_Q
        
        # make sure we're authenticated, to get JSESSIONID
        me = self.execute_get( "whoami", cacheable=False, intent="Login to get JSESSIONID" )
#        print( f"{me=}" )
        jsessionid = httpops.getcookievalue( self.server._session.cookies, 'JSESSIONID',None)
        if not jsessionid:
            raise Exception( "JSESSIONID not found!" )
#        print( f"{jsessionid=}" )
        # POST to start the scenario
        start_scenario_header = {'Content-type':'application/json','Accept':'application/json','X-Jazz-CSRF-Prevent':jsessionid }
        start_scenarioname_json = {'scenarioName': scenarioName}
        starturl = self.reluri( SCENARIOSERVICE + STARTSCENARIO )
        details = self.execute_post_json( starturl, headers=start_scenario_header, data=json.dumps(start_scenarioname_json), cacheable=False, intent=f"Start secenario {scenarioName}" )
#        print( f"{details.json()=}" )
        
#        pp.pprint( details )
        if not persistToFile and autosave:
            persistToFile = CUSTOMSCENARIO_SAVE_PREFIX+scenarioName
            print( f"Autosaved to {persistToFile}" )
        if persistToFile:
            open( persistToFile,"wt" ).write( details.text )
            print( "Written to file" )
        return details.text
        
#    def saveScenarioDetails( self, scenarioName, details ):
#        pass
        
#    def recoverScenario( self, scenarioName ):
#        return details
        
    # provide either the details as returned by the start or autosaved=True or a detailsFilename to load them from
    def stopScenario( self, scenarioName, *, addDateToName=False, fromFilename=None, details=None, autosaved=True ):
        # {"scenarioName":"MyCustomExpensiveScenario", "scenarioInstanceId":"_Jbe94DaQEempFf7xSdsBAQ", "scenarioHeaderKey":"x-com-ibm-team-scenario", "scenarioHeaderValue":"_Jbe94DaQEempFf7xSdsBAQ%3Bname%3DMyCustomExpensiveScenario"}
        # This generates an rm.log entry like: 2025-06-17T08:01:12,538-0700 [TID: 3FF889C5][][Default Executor-thread-107 @@ 08:01 ibm <python-requests/2.32.3@9.111.37.111> /rm/service/com.ibm.team.repository.service.serviceability.IScenarioRestService/scenarios/stopscenario]  INFO ry.service.internal.serviceability.ScenarioService - An instance of the scenario: asd5 has ended:_xbChsEuLEfCule9gtHkh_Q
        if not fromFilename and not details and not autosaved:
            raise Exception( "You must provide either details or fromFilename to read the details from" )
        if not fromFilename and autosaved:
            fromFilename = CUSTOMSCENARIO_SAVE_PREFIX+scenarioName
            print( f"Autosaved from {fromFilename}" )
        if fromFilename:
            details = json.loads( open( fromFilename, "rt" ).read() )

        # make sure we're authenticated, to get JSESSIONID
        me = self.execute_get( "whoami", cacheable=False, intent="Login to get JSESSIONID" )
#        print( f"{me=}" )
        jsessionid = httpops.getcookievalue( self.server._session.cookies, 'JSESSIONID',None)
        if not jsessionid:
            raise Exception( "JSESSIONID not found!" )
#        print( f"{jsessionid=}" )

        # POST to stop the scenario
        stop_scenario_header = {'Content-Type':'application/json','Accept':'application/json','X-Jazz-CSRF-Prevent':jsessionid }
        stopurl = self.reluri( SCENARIOSERVICE + STOPSCENARIO )
        result = self.execute_post_json( stopurl, headers=stop_scenario_header,  data=details, cacheable=False, intent=f"Stop scenario {scenarioName}" )

        return result.text
        
    def getStatisticsURL( self ):
        return self.reluri( "repodebug/mxBeans" )
        
    def getRunningScenarios( self ):
        # make sure we're authenticated, to get JSESSIONID
        me = self.execute_get( "whoami", cacheable=False, intent="Login to get JSESSIONID" )
#        print( f"{me=}" )
        jsessionid = httpops.getcookievalue( self.server._session.cookies, 'JSESSIONID',None)
        if not jsessionid:
            raise Exception( "JSESSIONID not found!" )
#        print( f"{jsessionid=}" )
        # POST to stop the scenario
        status_scenario_header = {'Content-type':'application/json','Accept':'application/json','X-Jazz-CSRF-Prevent':jsessionid }
        statusurl = self.reluri( SCENARIOSERVICE )
        result = self.execute_get_json( statusurl, headers=status_scenario_header, cacheable=False, intent=f"Get status of secenarios" )
#        print( f"{result=}" )
        return result

if __name__ == "__main__":
    
    # simple test harness
    # options: app, action (start/stop/status)
    
    # get some defaults from the environment (which can be overridden on the commandline or the saved obfuscated credentials)
    JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
    USER        = os.environ.get("QUERY_USER"       ,"ibm" )
    PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
    JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
    APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
    LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,None )

    # setup arghandler
    parser = argparse.ArgumentParser(description="Test harness for CusgtomScenarios")

    parser.add_argument('action', choices=['start','stop','status'], help=f'start/stop/status')
    parser.add_argument('name', default=None, nargs='?', help=f'The anme of the scenario - only relevant for the start and stop actions')
    parser.add_argument('-A', '--appstrings', default=None, help=f'A comma-seperated list of apps, the action goes to the first entry, default "{APPSTRINGS}". Each entry must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using environemnt variable QUERY_APPSTRINGS')
    parser.add_argument('-D', '--date', action="store_true", help="Add the date to the scenario name")
    parser.add_argument('-F', '--file', help='File to save the scenario details in after you start it - you must specify this same file when you stop the scenario!' )
    parser.add_argument("-J", "--jazzurl", default=JAZZURL, help=f"jazz server url (without the /jts!) default {JAZZURL} - Default can be set using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
    parser.add_argument('-L', '--loglevel', default=None,help=f'Set logging to file and (by adding a "," and a second level) to console to one of DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    parser.add_argument("-P", "--password", default=PASSWORD, help=f"user password, default {PASSWORD} - Default can be set using environment variable QUERY_PASSWORD - set to PROMPT to be asked for password at runtime")
    parser.add_argument('-S', '--save', action="store_true", help="On a start, save details to an automatically generated file, on stop read the details from an automatically generated file")
    parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    parser.add_argument("-U", "--username", default=USER, help=f"user id, default {USER} - Default can be set using environment variable QUERY_USER")
    parser.add_argument('-V', '--verbose', action="store_true", help="Show verbose info")
    parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')
    
    # saved credentials
    parser.add_argument('-0', '--savecreds', default=None, help="Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, appstring, username and password")
    parser.add_argument('-1', '--readcreds', default=None, help="Read obfuscated credentials from file - completely overrides commandline/environment values for jazzurl, jts, appstring, username and password" )
    parser.add_argument('-2', '--erasecreds', default=None, help="Wipe and delete obfuscated credentials file" )
    parser.add_argument('-3', '--secret', default="N0tSeCret-", help="SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater security) - only affects if using -0 or -1" )
    parser.add_argument('-4', '--credspassword', action="store_true", help="Prompt user for a password to save/read obfuscated credentials (make this longer for greater security)" )

    args = parser.parse_args()

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
        exit(0)

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
        exit(0)

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

    utils.log_commandline( os.path.basename(sys.argv[0]),sys.argv[1:] )

    if args.password is None or args.password=="PROMPT":
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

    # create all our apps (there will be a main app which is specified by the first appstrings value, the main reason for allowing more than one is when gc is needed
    for appdom,approot in approots.items():
        allapps[appdom] = theserver.find_app( f"{appdom}:{approot}", ok_to_create=True )

    # get the main app - it's the one we're going to query - it was first in args.appstring
    app = allapps[themaindomain]
    config = None

    if args.action=="start":
        if not args.name:
            raise Exception( "You must provide the name of the scenario to start!" )
        if args.date:
            pass
        print( f"Starting {args.name}" )
        result = app.startScenario( args.name )
        print( f"{result=}" )
        pass
    elif args.action=="stop":
        if not args.name:
            raise Exception( "You must provide the name of the scenario to stop!" )
        if args.date:
            pass
        print( f"Stopping {args.name}" )
        result = app.stopScenario( args.name )
        print( f"{result=}" )
        pass
    elif args.action=="status":
        if args.name:
            raise Exception( "Don't provide a name!" )
        result = app.getRunningScenarios()
        print( f"{pp.pprint( result )}" )
        pass
        