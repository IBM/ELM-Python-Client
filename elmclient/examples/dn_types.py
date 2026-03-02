##
## © Copyright 2025- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


#
# demonstrator for the DN Types API https://jazz.net/wiki/bin/view/Main/DNGTypeAPI
#
# allows creating artifact types, attribute definitions, attribute types, and link types
#
# Updating a type definition (i.e. using PUT) not possible in 7.1 because it isn't available yet!
#

#
# dn_simple_create_attribute_type_simple project/component/config typename -u rdfuri valuetype(int/float/date/string/NOT enumeration)
# dn_simple_create_attribute_type_enumeration project/component/config typename -u rdfuri (integervalue:enumname:rdfuri|integervalue:enumname|enumname)* 
# dn_simple_create_attribute_type_bounded project/component/config typename -u rdfuri valuetype(date/string?/integer/float) min max
# because PUT not supported yet, the referenced types must all already exist
#
# dn_simple_create_attribute_definition_simple project/component/config typename -u rdfuri valuetype
# dn_simple_create_attribute_definition_enum project/component/config typename -u rdfuri valuetype_enum multivalued defaultvalue
# because PUT not supported yet, the referenced types must all already exist
#
# dn_simple_create_artifact_type project/component/config typename -u rdfuri command label attributes* preferredartifacttypes*
# dn_simple_create_module_type project/component/config typename -u rdfuri command label attributes* preferredartifacttypes*
# because PUT not supported yet, the referenced types must all already exist
#
# dn_simple_create_linktype project/component/config typename -o outlinkname -i inlinkname -u rdfuri comment
#
# single command with subcommands: (a bit like represt or reqif_io):
#
# dn_types -J jazzurel -A adminuser -P password project -C component -F config create/update/delete artifactType/attributeDefinition/attributeType/linkType ...
#   attributeType typename -u rdfuri simple/enumeration/bounded
#     simple -u rdfuri valuetype(int/float/date/string/NOT enumeration)
#     enumeration -u rdfuri (integervalue:enumname:rdfuri|enumname:rdfuri|enumname)* 
#     bounded -u rdfuri valuetype(date/string?/integer/float) min max
#   attributeDefinition typename -u rdfuri simple/enum
#     simple
#     enum
#   artifactType typename -u rdfuri -c comment label format(module/text) attributes*
#     module attributes* preferredartifacttypes*
#     text   attributes*
#   linkType typename -o outlinkname -i inlinkname -u rdfuri -c comment

# dn_types_create -J jazzurel -A adminuser -P password project -C component -F config artifactType/attributeDefinition/attributeType/linkType ...
#   attributeType typename -u rdfuri simple/enumeration/bounded
#     simple -u rdfuri valuetype(int/float/date/string/NOT enumeration)
#     enumeration -u rdfuri (integervalue:enumname:rdfuri|enumname:rdfuri|enumname)* 
#     bounded -u rdfuri valuetype(date/string?/integer/float) min max
#   attributeDefinition typename -u rdfuri simple/enum
#     simple
#     enum
#   artifactType typename -u rdfuri -c comment label format(module/text) attributes*
#     module attributes* preferredartifacttypes*
#     text   attributes*
#   linkType typename -o outlinkname -i inlinkname -u rdfuri -c comment

# dntypes_update

# dn_types_delete



import os
import argparse
import collections
import datetime
import logging
import re
import socket
import time
import webbrowser

import lxml.etree as ET
import requests
import requests_toolbelt

import elmclient.rdfxml as rdfxml
import elmclient.server as server
import elmclient._app as _app
import elmclient.utils as utils

# disable caching completely
cachecontrol=2

############################################################################

def types_main():

    datetimestamp = '{:%Y%m%d-%H%M%S}'.format(datetime.datetime.now())

    # get some defaults which can be overridden in the environment
    JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
    USER        = os.environ.get("QUERY_USER"       ,"ibm" )
    PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
    JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
    APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
    LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,"TRACE,OFF" )

    parser = argparse.ArgumentParser(description="Example of using the DN Types API")
    parser.add_argument('projectname', help='Name of project')

    # general settings
    parser.add_argument('-A', '--appstrings', default=None,help=f'Defaults to "rm,jts" - Must be comma-separated list of used domains or domain:contextroot, the FIRST one must be rm. If using nonstandard context roots for just rm like /rrc then specify "rm:rrc,jts" NOTE if jts is not on /jts then e.g. for /myjts use e.g. "rm:rn1,jts:myjts". Default can be set using environment variable QUERY_APPSTRINGS')
    parser.add_argument('-C', '--component', help='The local component (optional, if used you *have* to specify the local configuration using -F)')
#    parser.add_argument('-D', '--delaybetween', type=float,default=0.0, help="Delay in seconds between each import/export - use this to reduce overall server load")
    parser.add_argument('-F', '--configuration', default=None, help='Scope: Name of local config - you need to provide the project - defaults to the "Initial Stream" or "Initial Development" +same name as the project')
    parser.add_argument("-J", "--jazzurl", default=JAZZURL, help="jazz server url (without the /jts!) default {JAZZURL} Default can be set using environment variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
    parser.add_argument('-L', '--loglevel', default=LOGLEVEL,help=f'Set logging on console and (if providing a , and a second level) to file to one of DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    parser.add_argument("-P", "--password", default=PASSWORD, help=f"User password default '{PASSWORD}' - can be set using env variable OUERY_PASSWORD - set to PROMPT to be prompted at runtime")
    parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    parser.add_argument("-U", "--username", default=USER, help="User id - can be set using environment variable QUERY_USER")
#    parser.add_argument('-W', '--cachecontrol', action='count', default=0, help="Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and disables caching. Otherwise caching is continued from previous run(s).")
    parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')

    # saved credentials
    parser.add_argument('-0', '--savecreds', default=None, help="Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, appstring, username and password")
    parser.add_argument('-1', '--readcreds', default=None, help="Read obfuscated credentials from file - completely overrides commandline/environment values for jazzurl, jts, appstring, username and password" )
    parser.add_argument('-2', '--erasecreds', default=None, help="Wipe and delete obfuscated credentials file" )
    parser.add_argument('-3', '--secret', default="N0tSecret-", help="SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater security)" )
    parser.add_argument('-4', '--credspassword', action="store_true", help="Prompt user for a password to save/read obfuscated credentials (make this longer for greater security) - NOTE this is by far the best way to secure saved credentials - they're no longer just obfuscated when you use a runtime password!" )

    # add subparsers and subsubparsers
    # see https://dnmtechs.com/parsing-multiple-nested-sub-commands-with-python-argparse/
    subparsers = parser.add_subparsers(help='sub-commands',dest='command',required=True)

    create_parser = subparsers.add_parser( "create" )
    create_subparsers = create_parser.add_subparsers(dest="create_command",required=True)
    create_attrtype_parser = create_subparsers.add_parser("attributeType" )
    create_attrdef_parser = create_subparsers.add_parser("attributeDefinition" )
    create_arttype_parser = create_subparsers.add_parser("artifactType" )
    
#    update_parser = subparsers.add_parser( "update" )
#    delete_parser = subparsers.add_parser( "delete" )

 
#   attributeType typename -u rdfuri simple/enumeration/bounded
#     simple -u rdfuri valuetype(int/float/date/string/NOT enumeration) -b min max
#     enumeration -u rdfuri (integervalue:enumname:rdfuri|enumname:rdfuri|enumname)* 
    
    create_attrtype_parser.add_argument('definitionname',help='The attributeType definition name to create')
    create_attrtype_parser.add_argument('-u','--uri',default=None,type=str,help='The rdf uri')
    create_attrtype_parser.add_argument('-c','--comment',default=None,type=str,help='Description')
    
    create_attrtype_subparsers = create_attrtype_parser.add_subparsers(dest='create_attrtype_command',required=True)
    create_attrtype_simple_parser = create_attrtype_subparsers.add_parser('simple')
    create_attrtype_enum_parser = create_attrtype_subparsers.add_parser('enum')
    
    create_attrtype_simple_parser.add_argument('basetype',choices=['boolean','date','datetime','float','integer','string','time'],help='The base type')
    create_attrtype_simple_parser.add_argument('-b','--bounds',nargs=2,help='The lower and upper value (only for integer and float!)')
    
    create_attrtype_enum_parser.add_argument('enumvaluedef',nargs="+",default=[],help="an enumeration value def in the form integervalue:name:uri (if you want to put a : in an enum value name then double it)")
    
#    create_attrtype_bounded_parser.add_argument()
    
    args = parser.parse_args()

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

    # prompt for password
    if args.password is None or args.password=="PROMPT":
        args.password = getpass.getpass(prompt=f'Password for user {args.username}? :')

    ######################################################
    # request proxy config if appropriate
    if args.proxyport != 0:
        server.setupproxy(args.jazzurl,proxyport=args.proxyport)

    ######################################################
    # setup connection to the server and app(s)
    # approots has keys of the domain and values of the context root
    approots = {}
    allapps = {} #keyed by domain
    themainappstring = args.appstrings.split(",")[0]
    themaindomain = server.JazzTeamServer.get_appstring_details(themainappstring)[0]

    if themaindomain != "rm":
        raise Exception( "First appstring must be rm - only rm provides the dn types API!" )

    for appstring in args.appstrings.split(","):
        domain,contextroot = server.JazzTeamServer.get_appstring_details(appstring)
        if domain in approots:
            raise Exception( f"Domain {domain} must not appear twice in {args.appstrings}" )
        approots[domain]=contextroot

    # assert the jts default context root if not already specified in args.appstring
    if 'jts' not in approots:
        approots['jts']='jts'

    # create our "server"
    theserver = server.JazzTeamServer(args.jazzurl, args.username, args.password, verifysslcerts=args.certs,appstring=f"jts:{approots['jts']}",cachingcontrol=cachecontrol)

    # create all our apps
    for appdom,approot in approots.items():
        allapps[appdom] = theserver.find_app( f"{appdom}:{approot}", ok_to_create=True )

    # get the main app - it's the one we're going to query - it was first in args.appstring
    mainapp = allapps[themaindomain]
    if not mainapp.supports_reportable_rest:
        raise Exception( f"App {themaindomain} {themainappstring} doesn't provide a reportable rest API" )

    ######################################################
    # find the project and if using components find the component and configuration
    theproj = mainapp.find_project(args.projectname)
    
    if not theproj.providesTypeAPI():
        raise Exception( "Your RM server version doesn't provide the Types API - this is only available from 7.1" )

    if theproj is None:
        raise Exception( f"Project '{args.projectname}' not found")

    # assert default for the component name to be the same as the project name
    if args.component is None:
        if theproj.is_optin:
            print( f"Warning - project '{args.projectname}' is opt-in but you didn't specify a component - using default component '{args.projectname}'" )
        args.component = args.projectname

    # not all apps support components, and even if the app does this project may not be opt-in
    if mainapp.supports_components:
        if not theproj.singlemode and not args.component:
            raise Exception( f"Project {args.projectname} supports components so you must provide a component name" )
        if theproj.singlemode:
            args.component = args.projectname
        thecomp = theproj.find_local_component(args.component)
        if not thecomp:
            raise Exception( f"Component '{args.component}' not found in project {args.projectname}" )
        # assert the default configuration for this component if none is specified
        if args.configuration is None:
            args.configuration = thecomp.initial_stream_name()
            print( f"Warning - project '{args.projectname}' is opt-in but for component '{args.component}' you didn't specify a local configuration - using default stream '{thecomp.initial_stream_name()}'" )
        logger.info( f"{args.configuration=}" )
        if theproj.is_optin:
            if args.configuration or theproj.singlemode:
                if theproj.singlemode:
                    if args.configuration is None:
                        # default to the stream
                        args.configuration = thecomp.get_default_stream_name()
                config = thecomp.get_local_config(args.configuration)
                if config is None:
                    raise Exception( f"Configuration '{args.configuration}' not found in component {args.component}" )

                thecomp.set_local_config(config)
                logger.debug( f"LOCAL {config=}" )
            else:
                raise Exception( f"Project {args.projectname} is opt-in so you must provide a local configuration" )
        else:
            if args.configuration is None:
                # default to the stream
                args.configuration = thecomp.get_default_stream_name()
            config = thecomp.get_local_config(args.configuration)
            if config is None:
                raise Exception( f"Configuration '{args.configuration}' not found in component {args.component}" )

        thecomp.set_local_config(config)

        queryon = thecomp
    else:
        queryon = theproj
        
    if args.command=='create':
        if args.create_command=='attributeType':
            if args.create_attrtype_command=='simple':
                # check if the type exists
                if thecomp.hasAttributeType( args.definitionname ):
                    raise Exception( f"An attribute type called {args.definitionname} already exists!" )
                thecomp.createSimpleAttributeType( args.definitionname, args.basetype, uri=args.uri, comment=args.comment )
                burp
            burp
    burp
    
def main():
    runstarttime = time.perf_counter()
    types_main()
    elapsedsecs = time.perf_counter() - runstarttime
    print( f"Runtime was {int(elapsedsecs/60)}m {int(elapsedsecs%60):02d}s" )

if __name__ == '__main__':
    main()
