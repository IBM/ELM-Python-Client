##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


# DN/DNG Reqif export/import
# also can list the defintitions in a project/component
# consider adding ability to create a definition, e.g. by adding modules/artifacts to it

# DNG Reqif API https://jazz.net/wiki/bin/view/Main/DNGReqIF

# reqif factory and query capabilities resource types:
#  http://jazz.net/ns/rm/dng/reqif#ReqIFExport      dng_reqif:ReqIFExport
#  http://jazz.net/ns/rm/dng/reqif#ReqIFPackage     dng_reqif:ReqIFPackage
#  http://jazz.net/ns/rm/dng/reqif#ReqIFImport      dng_reqif:ReqIFImport
#  http://jazz.net/ns/rm/dng/reqif#ReqIFDefinition  dng_reqif:ReqIFDefinition
#

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

def reqif_main():

    datetimestamp = '{:%Y%m%d-%H%M%S}'.format(datetime.datetime.now())

    # get some defaults which can be overridden in the environment
    JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
    USER        = os.environ.get("QUERY_USER"       ,"ibm" )
    PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
    JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
    APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
    LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,"TRACE,OFF" )

    allformats = []
    for app in _app._App.__subclasses__():
        if app.artifact_formats:
            allformats.append(f"{app.domain}: "+",".join( app.artifact_formats )+ "." )
    del app
    
    allformats = " ".join(allformats)

    parser = argparse.ArgumentParser(description="Perform Reportable REST query on an application, with results output to CSV and/or XML - use -h to get some basic help")
    parser.add_argument('projectname', help='Name of project')

    # general settings
    parser.add_argument('-A', '--appstrings', default=None,help=f'Defaults to "rm,jts" - Must be comma-separated list of used domains or domain:contextroot, the FIRST one must be rm. If using nonstandard context roots for just rm like /rrc then specify "rm:rrc,jts" NOTE if jts is not on /jts then e.g. for /myjts use e.g. "rm:rn1,jts:myjts". Default can be set using environment variable QUERY_APPSTRINGS')
    parser.add_argument('-C', '--component', help='The local component (optional, if used you *have* to specify the local configuration using -F)')
    parser.add_argument('-D', '--delaybetween', type=float,default=0.0, help="Delay in seconds between each import/export - use this to reduce overall server load")
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

    subparsers = parser.add_subparsers(help='sub-commands',dest='subparser_name')

    parser_create = subparsers.add_parser('create', help='Create a new/update an existing reqif definition in a project/component, adding module(s) or artifact(s)')
    parser_delete = subparsers.add_parser('delete', help='Delete an existing reqif definition in a project/component')
    parser_export = subparsers.add_parser('export', help='Export one or more definitions from a project/component and download the reqifz file')
    parser_import = subparsers.add_parser('import', help='Import one or more reqifz files into a project/component')
    parser_list = subparsers.add_parser('list', help='List the definitions in a project/component')

    parser_export.add_argument('definitionnames',nargs='*',default=[],help='name of export definition- this can be a regex where . matches any character, etc. If you want the regex to match a complete name put ^ at the start and $ at the end - where multiuple names match, these will be exported in alphabetical order')
    parser_export.add_argument('-t', '--timestamp', action='store_true', help='Add a timestamp to all exported file names (both reqif and html)')
    parser_export.add_argument('-O', '--outputdirectory',default=None,help='Output directory for all exported files')

    parser_list.add_argument('definitionnames',nargs='*',default=[],help='name of export definition- this can be a regex where . matches any character, etc. If you want the regex to match a complete name put ^ at the start and $ at the end - where multiuple names match, these will be exported in alphabetical order')
    parser_list.add_argument('-O', '--outputdirectory',default=None,help='Output directory for all exported files')

    parser_import.add_argument( 'ifiles',nargs="*", default=[], help='one or more reqif files or file patterns (e.g. *.reqifz) to import')
    parser_import.add_argument('-I', '--inputdirectory',default='',help='Input directory for all imported files')
    parser_import.add_argument('-O', '--outputdirectory',default=None,help='Output directory for all exported files')

    parser_create.add_argument('definitionname',help='The reqif definition name to create')
    parser_create.add_argument('-a', '--allcores', action="store_true", help="Add all core artifacts (not modules/collections) from the project/component")
    parser_create.add_argument('-f', '--folders', action="store_false", help="Don't include folders in the reqif (defaults to including) - if you need this off, specify it on the last update or on the create")
    parser_create.add_argument('-i', '--identifiers', nargs='*', default=[], help='Use * for all core artifacts or comma-separated list of requirement IDs to add - can specify this option more than once')
    parser_create.add_argument('-l', '--links', action="store_false", help="Don't include links in the reqif (defaults to including) - if you need this off, specify it on the last update or on the create")
    parser_create.add_argument('-m', '--modules', nargs='*', default=[], help='Use * or comma-separated list of module IDs or names of the module to add - for name you can use a regex - can specify this option more than once')
    parser_create.add_argument('-r', '--removeallartifacts', action="store_true", help="When updating, first remove all artifacts/modules/views")
    parser_create.add_argument('-s', '--description', default="-", help="Description for the definition")
    parser_create.add_argument('-t', '--tags', action="store_false", help="Don't include tags in the reqif (defaults to including) - if you need this off, specify it on the last update or on the create")
    parser_create.add_argument('-u', '--update', action="store_true", help="Update the named definition by adding things - it must already exist!")
# TODO: NIY    parser_create.add_argument('-p', '--publicviews', nargs='*', default=[], help='* or CSL of public view names')
# TODO: NIY    parser_create.add_argument('-v', '--moduleviews', nargs='*', default=[], help='* or CSL of module view names')

    parser_delete.add_argument('definitionnames',nargs='*',default=[],help='One or more names of export definitions to delete - this can be a regex where . matches any character, etc. If you want the regex to match a complete name put ^ at the start and $ at the end')
    parser_delete.add_argument('-n', '--noconfirm', action='store_true', help="Don't prompt to confirm each delete (DANGEROUS!)")
    parser_delete.add_argument('-x', '--exception', action='store_true', help="Don't raise an exception if definition doesn't exist")
    

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
        raise Exception( "First appstring must be rm (only rm provides reqif import/export!)" )

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

    if theproj is None:
        raise Exception( f"Project '{args.projectname}' not found")

    # assert default for the component name to be the same as the project name
    if args.component is None:
        if theproj.is_optin:
            print( f"Warning - project '{args.projectname}' is opt-in but you didn't specify a component - using default component '{args.projectname}'" )
        args.component = args.projectname
    print( f"{mainapp=}" )
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
        print( f"{config=}" )

        queryon = thecomp
    else:
        queryon = theproj
        
    ######################################################
    # return True if string contains any of the characters that might be used in a regex
    def isregexp( s ):
        if any([c in s for c in r"^$?*[].+()"]):
            return True
        return False

    ######################################################
    # return a list of dictionaries - one for each entry in definitionnames
    def getmatchingdefs(alldefs,definitionnames):
        results = []
        # look for matches
        matches = {}
        for exportdef in definitionnames:
            if isregexp(exportdef):
                def_re = re.compile( exportdef, re.IGNORECASE )
            else:
                def_re = re.compile( f"^{exportdef}$", re.IGNORECASE )

            for k,v in alldefs.items():
                title = v['dcterms:title']
                if re.search(def_re,title ):
                    matches[k]=dict(v)
                    matches[k]['exportdef']=exportdef
            results.append(dict(matches))
        return results

    if args.subparser_name=='list':
        #################################################################################
        # List the reqif definitions
        # get the reqif definition query URL
        defn_query_u = queryon.get_query_capability_uri("dng_reqif:ReqIFDefinition")
        queryon.record_action( "Use the Reqif query capability" )
        # query for the definitions
        alldefs = queryon.execute_oslc_query( defn_query_u, select=['*'])
        
#        alldefs = queryon.do_complex_query( "dng_reqif:ReqIFDefinition", select='*' )
        
        logger.debug( f"{alldefs=}" )
        if args.definitionnames:
            rawmatches = getmatchingdefs(alldefs,args.definitionnames )
            # merge all the matches so only get reported once
            matches = {}
            for match in rawmatches:
                matches.update(match)
        else:
            matches = alldefs

        for k in sorted(matches.keys(),key= lambda k: matches[k]['dcterms:title']):
            print( f"{matches[k]['dcterms:title']} {k}" )
            for k1 in sorted(alldefs[k].keys()):
                print( f"    {k1} {alldefs[k][k1]}" )
            print()
                
    elif args.subparser_name=='export':
        #################################################################################
        # Export a reqif definition
        # first find the matching export definitions
        # then export each one sequentially

        # get the reqif definition query URL
        defn_query_u = queryon.get_query_capability_uri("dng_reqif:ReqIFDefinition")
        # query for the definitions
        queryon.record_action( "Use the Reqif query capability" )
        alldefs = queryon.execute_oslc_query( defn_query_u, select=['*'])
        logger.debug( f"{alldefs=}" )
        # see if specs are specified
        if args.definitionnames:
            rawmatches = getmatchingdefs(alldefs,args.definitionnames )
            # merge all the matches so only get exported once
            matches = {}
            for match in rawmatches:
                matches.update(match)
            matches = [matches]
        else:
            matches = [alldefs]

        # get the export factory
        export_factory_u = queryon.get_factory_uri("dng_reqif:ReqIFExport")

        for match in matches:
            logger.info( f"\n=============================\n{match=}" )
            for reqif_def in match.keys():
                logger.info( f"\n-----------------------------------\n{reqif_def=}" )
                ed = match[reqif_def].get('exportdef','')
                logger.debug( f"Exporting {ed=} {reqif_def} {match=}" )
                content = f"""<rdf:RDF
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:dng_reqif="http://jazz.net/ns/rm/dng/reqif#">
<dng_reqif:ReqIFExport>
<dng_reqif:definition rdf:resource="{reqif_def}"/>
</dng_reqif:ReqIFExport>
</rdf:RDF>
"""
                logger.debug( f"{content=}" )
                response = queryon.execute_post_rdf_xml( export_factory_u, data=content, cacheable=False, intent="Initiate reqif export" )
                logger.debug( f" {response.status_code=} {response=}" )
                location = response.headers.get('Location')
                if response.status_code == 202 and location is not None:
                    # wait for the tracker to finished
                    result = queryon.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Exporting {match[reqif_def]['dcterms:title']}")
                    time.sleep( 1.0 )
                    if result is not None:
                        pkg = rdfxml.xmlrdf_get_resource_uri( result, ".//dcterms:references" )
                        logger.debug( f"{pkg=}" )
                        pkg_x = queryon.execute_get_rdf_xml( pkg, intent="Retrieve reqif export completed tracker result details" )
                        logger.debug( f"{pkg_x=}" )
                        # get the content and its filename
                        content_u =  rdfxml.xmlrdf_get_resource_uri( pkg_x, ".//dng_reqif:content" )
                        response = queryon.execute_get_binary( content_u, intent="Retrieve reqif export completed tracker content" )
                        fname = response.headers.get('Content-Disposition').split( '"', 2 )[1]
                        if fname is None:
                            raise Exception( "No content-disposition!" )
                        if args.timestamp:
                            fname = os.path.splitext(fname)[0]+f".{datetimestamp}.reqifz"
                        if args.outputdirectory:
                            fname = os.path.join( os.getcwd(), args.outputdirectory, fname )
                        print( f"Reqif saved to {fname}" )
                        open( fname, "wb" ).write( response.content )

                        report_u = rdfxml.xmlrdf_get_resource_uri( pkg_x, ".//dng_reqif:report" )
                        response =  queryon.execute_get_binary( report_u, intent="Retrieve reqif export report" )
                        htmlfile = fname+".html"
                        print( f"Report saved to {htmlfile}" )
                        open( htmlfile, "wb" ).write( response.content )

                        # display the report
                        url = f'file://{os.path.abspath(htmlfile)}'
                        webbrowser.open(url, new=2)  # open in new tab

                else:
                    raise Exception( "Odd response to export command, no Location" )

                if len(matches)>1 and args.delaybetween>0:
                    print( "Delaying between exports" )
                    time.sleep(args.delaybetween)

    elif args.subparser_name=='import':
        #################################################################################
        # import a reqifz file
        # get the package factory base URL
        pkg_factory_u = queryon.get_factory_uri("dng_reqif:ReqIFPackage")
        # get the import factory URL
        import_factory_u = queryon.get_factory_uri("dng_reqif:ReqIFImport")
        # accumulate all the input files
        filenames = []
        for ifile in args.ifiles:
            ifile = os.path.join( os.getcwd(), args.inputdirectory, ifile )
            if '*' in ifile or '?' in ifile or '[' in ifile:
                ifiles = glob.glob(ifile)
            else:
                ifiles = [ifile]
            filenames.extend( ifiles )

        for ifile in filenames:
            print( f"Creating upload package for {ifile}" )
            # construct multi-part body containing the file content
            multipart_form_data = collections.OrderedDict(
                    [('upload', (os.path.basename(ifile), open(os.path.normpath(ifile), 'rb'),'application/octet-stream'))
                    ,('userMimeType','application/zip')]
                )
            multipartencoder = requests_toolbelt.MultipartEncoder(multipart_form_data,boundary='---------------------------1336032510420201357832076537')
            content_type, body = multipartencoder.content_type, multipartencoder.to_string()

            # execute post content
            logger.info('Uploading package {ifile}...')
            response = queryon.execute_post_content(pkg_factory_u, data=body, headers={'Content-Type': content_type, 'userMimeType': 'application/zip', 'filename':os.path.basename(ifile),'Accept': '*/*','X-Requested-With': None,'Origin': 'https://jazz.ibm.com:9443', 'OSLC-Core-Version': None}, intent="Initiate reqif import - upload the reqif file" )

            print( f"Triggering import for {os.path.basename(ifile)}" )

            location = response.headers.get('Location')
            if response.status_code == 201:
                pass
            elif response.status_code == 202 and location is not None:
                # wait for the tracker to finished
                result = queryon.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Exporting {match[reqif_def]['dcterms:title']}")
                time.sleep( 1.0 )
                if result is None:
                    raise Exception( f"No result from tracker!" )
            else:
                raise Exception( f"Unknown response {response.status_code}" )

            content=f"""<rdf:RDF
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns:dng_reqif="http://jazz.net/ns/rm/dng/reqif#">
    <dng_reqif:ReqIFImport>
         <dng_reqif:package rdf:resource="{location}"/>
   </dng_reqif:ReqIFImport>
</rdf:RDF>"""

            logger.debug( f"{content=}" )
            response = queryon.execute_post_rdf_xml( import_factory_u, data=content, cacheable=False, headers={'net.jazz.jfs.owning-context': queryon.project_uri, 'OSLC-Core-Version': None}, intent="Initiate reqif import of the uploaded file" )
            logger.debug( f" {response.status_code=} {response=}" )
            location = response.headers.get('Location')
            if response.status_code == 202 and location is not None:
                # wait for the tracker to finished
                result = queryon.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Importing {os.path.basename(ifile)}")
                time.sleep( 1.0 )
                if result is not None:
                    # get the result
                    report_u = rdfxml.xmlrdf_get_resource_uri( result, ".//dcterms:references" )
                    logger.debug( f"{report_u=}" )
                    response =  queryon.execute_get_binary( report_u, intent="Retrieve reqif import result after tracker completed" )
                    htmlfile = ifile+".html"
                    print( f"Report saved to {htmlfile}" )
                    open( htmlfile, "wb" ).write( response.content )

                    # display the report
                    url = f'file://{os.path.abspath(htmlfile)}'
                    webbrowser.open(url, new=2)  # open in new tab
            else:
                raise Exception( "Odd response to export command, no 202" )
            if args.delaybetween>0:
                print( "Delaying between imports" )
                time.sleep(args.delaybetween)

    elif args.subparser_name=='create':
        #################################################################################
        # Create or update a reqif definition
        # if not updating, make sure the definition doesn't already exist
        # if updating make sure it exists
        # then find the things to be added to the definition

        # get the reqif definition query URL
        defn_query_u = queryon.get_query_capability_uri("dng_reqif:ReqIFDefinition")
        defn_factory_u = queryon.get_factory_uri("dng_reqif:ReqIFDefinition")
        # query for the definitions
        alldefs = queryon.execute_oslc_query( defn_query_u, select=['*'])
        logger.debug( f"{alldefs=}" )
        rawmatches = getmatchingdefs(alldefs,[f"^{args.definitionname}$"] )
        logger.debug( f"{rawmatches=}" )
        if args.update:
            # check it exists
            if len(rawmatches[0])==0:
                raise Exception( f"Reqif definition {args.definitionname} must exist" )
            existingdef = rawmatches[0]
            logger.debug( f"{existingdef=}" )
        else:
            # check it doeesn't exist
            if len(rawmatches[0])>0:
                raise Exception( f"Reqif definition {args.definitionname} must not exist" )

            logger.debug( f"{queryon.services_uri=}" )
            logger.debug( f"{queryon=}" )
            if args.update:
                # get the existing definition XML
                existing_u = list(existingdef.keys())[0]
#                logger.debug( f"{existing_u=}" )
                response,etag = queryon.execute_rdf_xml( existing_u, headers={'Accept': 'application/rdf+xml', 'OSLC-Core-Version': None, 'OSLC-Core-Version': None}, return_etag=True, intent="Retrieve project/component existing reqif definition"  )
                defn_x = ET.ElementTree(ET.fromstring(response.content)).getroot()
                etag = response.headers.get('ETag')
                inctags = rdfxml.xmlrdf_get_resource_text( defn_x, './/dng_reqif:includeTags' )
                incfolders = rdfxml.xmlrdf_get_resource_text( defn_x, './/dng_reqif:includeFolders' )
                inclinks = rdfxml.xmlrdf_get_resource_text( defn_x, './/dng_reqif:includeLinks' )
                logger.debug( f"{inctags=}" )
                logger.debug( f"{incfolders=}" )
                logger.debug( f"{inclinks=}" )
                logger.debug( f"{args.removeallartifacts=}" )
                rootdef = rdfxml.xml_find_element( defn_x, './dng_reqif:ReqIFDefinition' )
                if args.removeallartifacts:
                    # delete all artifacts and views in the definitions
                    artincs = rdfxml.xml_find_elements( rootdef, './dng_reqif:include' )
                    logger.debug( f"{artincs=}" )
                    for artinc in artincs:
                        rootdef.remove(artinc)
            else:
                # create
                defn_x = ET.fromstring(f"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
           xmlns:dng_reqif="http://jazz.net/ns/rm/dng/reqif#"
           xmlns:acp="http://jazz.net/ns/acp#"
           xmlns:oslc="http://open-services.net/ns/core#"
           xmlns:dcterms="http://purl.org/dc/terms/"
           >
    <dng_reqif:ReqIFDefinition rdf:about="">
            <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">{args.definitionname}</dcterms:title>
            <dng_reqif:includeTags>true</dng_reqif:includeTags>
            <dng_reqif:includeFolders>true</dng_reqif:includeFolders>
            <dng_reqif:includeLinks>true</dng_reqif:includeLinks>

            <dcterms:identifier/>

            <oslc:serviceProvider rdf:resource="{queryon.services_uri}"/>
            <acp:accessControl rdf:resource=""/>
            <dcterms:contributor>https://jazz.ibm.com:9443/jts/users/ibm</dcterms:contributor>
            <dcterms:modified />
            <dng_reqif:relatedReqIFPackages rdf:resource=""/>

    </dng_reqif:ReqIFDefinition>
</rdf:RDF>
""" )
                rootdef = rdfxml.xml_find_element( defn_x, './dng_reqif:ReqIFDefinition' )
                logger.debug( f"{rootdef=}" )
            # for each artifact/module

#            artinc="""
#        <dng_reqif:include>
#              <dng_reqif:ArtifactSelection>
#                    <dng_reqif:artifact rdf:resource="https://jazz.ibm.com:9443/rm/resources/MD__y90-kB6Eeuh3Iiax2L3Ow"/>
#                  </dng_reqif:ArtifactSelection>
#            </dng_reqif:include>
#"""
#                # for each view
#                viewinc = """
#            <dng_reqif:include>
#                  <dng_reqif:ViewDefinitionSelection>
#                        <dng_reqif:usedInModule rdf:resource="https://jazz.ibm.com:9443/rm/resources/MD__y90-kB6Eeuh3Iiax2L3Ow"/>
#                        <dng_reqif:view rdf:resource="https://jazz.ibm.com:9443/rm/views/VW__wvAA0B6Eeuh3Iiax2L3Ow"/>
#                      </dng_reqif:ViewDefinitionSelection>
#                </dng_reqif:include>
#"""

#             <acp:accessControl rdf:resource="https://jazz.ibm.com:9443/rm/accessControl/_-_28tkB6Eeuh3Iiax2L3Ow"/>
#            <dcterms:contributor>https://jazz.ibm.com:9443/jts/users/ibm</dcterms:contributor>
#            <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2021-09-03T12:10:25.582Z</dcterms:modified>
#            <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">_8500a38e-4382-46d1-b44b-0b8ab4b301c6</dcterms:identifier>
#            <dng_reqif:relatedReqIFPackages rdf:resource="https://jazz.ibm.com:9443/rm/reqif_oslc/definitions/query?reqIFDefinitionUri=https://jazz.ibm.com:9443/rm/reqif/RD_67rw8gyvEeyENOqNxpyqoQ"/>
#            viewincs = []
#            for viewinc in viewincs:
#                # add elements for view
#                pass
            artincs = []
            rmqbase = queryon.get_query_capability_uri("oslc_rm:Requirement")
            # check moduless
            if args.modules:
                # retrieve all modules
                allmodules = queryon.execute_oslc_query(
                        rmqbase
                        ,whereterms=[['rdm_types:ArtifactFormat','=',f'<{rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]}Module>']]
                        ,select=['*']
                        ,prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rdm_types"]:'rdm_types'}
                        ,intent="OSLC Query for all modules"
                    )

                logger.debug( f"{len(allmodules)=}" )
                logger.debug( f"{allmodules=}" )
                for k, v in allmodules.items():
                    logger.debug( f"{v.get('dcterms:identifier')} {v.get('dcterms:title')}" )
                # now filter

                if '*' in args.modules:
                    for moduri in allmodules.keys():
                        if moduri not in artincs:
                            artincs.append(moduri)
                else:
                    # choose modules to include
                    allrefs = []
                    for modref in args.modules:
                        logger.debug( f"{modref=}" )
                        if re.match( r"^[\d,]+$", modref ):
                            # if just digits and commas assume a CSL of IDs
                            allrefs.extend( modref.split( "," ) )
                        else:
                            # a name or name regex
                            allrefs.append(modref)
                    # now try to match
                    # build lookup from id to uri
                    ids = {}
                    for k in allmodules:
                        id = allmodules[k].get('dcterms:identifier')
                        if id:
                            ids[id]=k
                    reffound = False
                    for ref in allrefs:
                        logger.debug( f"{ref=}" )
                        print( f"{ref=}" )
                        if utils.isint(ref):
                            # search for an id
                            if ref in ids:
                                if ids[ref] not in artincs:
                                    artincs.append(ids[ref])
                                    print( f"Added module {ref}" )
                                    continue
                        else:
                            # search for literal name or a regex match
                            if re.match(r'^[a-zA-Z0-9 _]+$', ref ):
                                # literal match
                                print( f"nre {ref}" )
                                logger.debug( f"nre" )
                                # pure string match
                                # try regex match
                                for k,v in allmodules.items():
                                    if v.get( 'dcterms:title' ) == ref:
                                        if k not in artincs:
                                            artincs.append(k)
                                            print( f"Added module {ref}" )
                                            continue
                            else:
                                logger.debug( f"re" )
                                print( f"re {ref}" )
                                # try regex match
                                for k,v in allmodules.items():
                                    if re.search( ref, v.get( 'dcterms:title' ), re.IGNORECASE ):
                                        if k not in artincs:
                                            artincs.append(k)
                                            print( f"Added module matching {v.get( 'dcterms:title' )} re {ref}" )
                                            continue
                        if not artincs:
                            raise Exception( f"No modules found for {ref}!" )
                    # filter for module id/name
                    logger.debug( f"{artincs=}" )

            if args.allcores:
                # retrieve all the core artifacts (note this includes the artifact for each module)
                allartifacts = queryon.execute_oslc_query(
                        rmqbase
#                        ,whereterms=[['rdm_types:ArtifactFormat','=',f'<{rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]}Module>']]
                        ,select=['dcterms:identifier', 'rm_nav:parent']
                        ,prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rm_nav"]:'rm_nav'}
                        ,intent="Retrieve all core artifacts, including artifacts for modules)"
                    )
                # post-filter for non-empty identifier and incldue them
                for k in list(allartifacts.keys()):
                    logger.debug( f"checking {k=}" )
                    if allartifacts[k].get('dcterms:identifier'):
                        if k not in artincs:
                            artincs.append(k)

            if args.identifiers:
                if '*' in args.identifiers:
                    # all core artifacts excluding modules
                    allids=['*']
                    allartifacts = queryon.execute_oslc_query(
                            rmqbase
                            ,whereterms=[['rdm_types:ArtifactFormat','!=',f'<{rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]}Module>']]
                            ,select=['dcterms:identifier', 'rm_nav:parent']
                            ,prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rm_nav"]:'rm_nav'}
                            ,intent="Retrieve all core artifacts excluding artifacts for modules"
                        )
                else:
                    # this is specifically core artifacts, by identifier
                    allids = []
                    for id in args.identifiers:
                        allids.extend(id.split(","))
                    # check all are integer strings:
                    if not all( [utils.isint(s) for s in allids] ):
                        raise Exception( "Must only use integers for -i" )
                    allartifacts = queryon.execute_oslc_query(
                            rmqbase
                            ,whereterms=[['dcterms:identifier' 'in', allids]]
                            ,select=['dcterms:identifier', 'rm_nav:parent']
                            ,prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rm_nav"]:'rm_nav'}
                            ,intent="retrieve all core artifacts with identifiers"
                        )
                # build lookup from id to uri
                # find artifacts with an id and a aprent - if the id is being sought add to artincs
                for k in allartifacts:
                    id = allartifacts[k].get('dcterms:identifier')
                    parent = allartifacts[k].get('rm_nav:parent')
                    if id and parent:
                        if id in allids or allids[0]=='*':
                            if k not in artincs:
                                artincs.append(k)
                                logger.debug( f"{id=} {parent=}" )
            logger.debug( f" Found {len(artincs)}" )

            # assemble the XML for the artifact references
            #
            #        <dng_reqif:include>
            #              <dng_reqif:ArtifactSelection>
            #                    <dng_reqif:artifact rdf:resource="https://jazz.ibm.com:9443/rm/resources/MD__y90-kB6Eeuh3Iiax2L3Ow"/>
            #                  </dng_reqif:ArtifactSelection>
            #            </dng_reqif:include>
            for artinc in artincs:
                # add an include
                inc = ET.SubElement( rootdef, rdfxml.uri_to_tag('dng_reqif:include') )
                artsel = ET.SubElement( inc, rdfxml.uri_to_tag('dng_reqif:ArtifactSelection') )
                art = ET.SubElement( artsel, rdfxml.uri_to_tag('dng_reqif:artifact'), {rdfxml.uri_to_tag('rdf:resource'): artinc} )
                logger.debug( "===\n",ET.tostring(inc) )
            rdfxml.xml_find_element( rootdef,'./dng_reqif:includeTags').text = "true" if args.tags else "false"
            rdfxml.xml_find_element( rootdef,'./dng_reqif:includeFolders').text = "true" if args.folders else "false"
            rdfxml.xml_find_element( rootdef,'./dng_reqif:includeLinks').text = "true" if args.links else "false"
            headers = {'OSLC-Core-Version': None}
            if args.update:
                headers.update({ 'if-match': etag } )
                response = queryon.execute_post_rdf_xml( existing_u, data=defn_x, cacheable=False, put=True, headers=headers, intent="Update a project/component reqif definition"  )
            else:
                response = queryon.execute_post_rdf_xml( defn_factory_u, data=defn_x, cacheable=False, headers=headers, intent="Create a project/component reqif definition" )
                logger.debug( f" {response.status_code=} {response=}" )

            location = response.headers.get('Location')


            logger.debug( f"{location=}" )
            print( f"Created!" )
    elif args.subparser_name=='delete':
        #################################################################################
        # Delete a reqif definition
        # need to check the definition exists then delete it
        # get the reqif definition query URL
        defn_query_u = queryon.get_query_capability_uri("dng_reqif:ReqIFDefinition")
        # query for the definitions
        alldefs = queryon.execute_oslc_query( defn_query_u, select=['*'], intent="Retrieve all project/component reqif definitions" )
        logger.debug( f"{alldefs=}" )

        if args.definitionnames:
            rawmatches = getmatchingdefs(alldefs,args.definitionnames )
            if not rawmatches[0]:
                if not args.exception:
                    raise Exception( f"Definition {args.definitionnames} not found" )
                print( f"No definitions matching {args.definitionnames} found - exception suppressed so this isn't a failure" )
                return
            # merge all the matches so only get reported once
            matches = {}
            for match in rawmatches:
                matches.update(match)
        else:
            raise Exception( "No definition name provided!" )

        if not matches:
            if not args.exception:
                raise Exception( f"Definitions {args.definitionnames} not found" )
            print( f"No definitions matching {args.definitionnames} found - exception suppressed so this isn't a failure" )
            return

        for k in sorted(matches.keys(),key= lambda k: matches[k]['dcterms:title']):
            print( f"Deleting {matches[k]['dcterms:title']}" )
            if not args.noconfirm:
                # get user to confirm by entering Y or press Q to quit
                oktodelete=False
                resp=input("Press y/Y to confirm delete, or q/Q to quit:").lower()
                if resp.startswith('y'):
                    oktodelete=True
                elif resp.startswith('q'):
                    break
            else:
                oktodelete=True

            if oktodelete:
                # create DELETE request and send to the definition
                result =  queryon.execute_delete(k, intent="Delete project/component reqif definition" )
                print( f"Deleted {matches[k]['dcterms:title']} {k}" )
            else:
                print( "Not deleted!" )

    else:
        raise Exception( f"Unrecognized command {args.subparser_name}" )

def main():
    runstarttime = time.perf_counter()
    reqif_main()
    elapsedsecs = time.perf_counter() - runstarttime
    print( f"Runtime was {int(elapsedsecs/60)}m {int(elapsedsecs%60):02d}s" )

if __name__ == '__main__':
    main()