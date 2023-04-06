##
## © Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of creating a folder and creating an artifact in it
# provide on the commandline (each surrounded by " if it contains a space):
#  The name of the artifact type - case sensitive!
#  Some initial text to put in the artifact
#  The name of the folder where the artifact will be created - this is the path starting with / - case sensitive!
#  The name of the new folder

# For info about folder create API see https://rhnaranjo.wordpress.com/2012/06/25/folder-support-added-to-rrc-4-0-oslc-rm-api-implementation/

# Also see section 2 of https://jazz.net/library/article/1197

# to create an artifact you have to find the creation factory
# and find the 'instanceShape' for the type of artifact you want to create
# then you POST some basic content compliant with the shape to the factory URL
# this must also specify the folder where you want the artifact to be created - which means you need to find the folder URL
# folders are found using a OSLC Query capability for folders - this returns one level at a time
# sowill likely need a series of ueries to find an existing folder

import logging
import os.path
import sys
import time

import lxml.etree as ET

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml

# setup logging - see levels in utils.py
#loglevel = "INFO,INFO"
loglevel = "TRACE,OFF"
levels = [utils.loglevels.get(l,-1) for l in loglevel.split(",",1)]
if len(levels)<2:
    # assert console logging level OFF if not provided
    levels.append(None)
if -1 in levels:
    raise Exception( f'Logging level {loglevel} not valid - should be comma-separated one or two values from DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF' )
utils.setup_logging( filelevel=levels[0], consolelevel=levels[1] )

logger = logging.getLogger(__name__)

utils.log_commandline( os.path.basename(sys.argv[0]) )

jazzhost = 'https://jazz.ibm.com:9443'
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

# the project+compontent+config that will be updated
proj = "rm_optout_p1"
comp = proj
conf =  f"{comp} Initial Stream"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2
    
##################################################################################
if __name__=="__main__":
    if len(sys.argv) != 5:
        print( 'A typical commandline might be: dn_simple_createfolderandartifact.py "Stakeholder Requirement" "My first stakefilder requirement" / newfoldername' )
        raise Exception( 'You must provide: The artifact type, the artifact text, and the folder path to create the artifact in - each surrounded by " if including spaces' )

    newfoldername = sys.argv[4]
    
    print( f"Attempting to create a '{sys.argv[1]}' in project '{proj}' in configuration {conf} in folder '{sys.argv[3]}'" )
    print( f"Using credentials user '{username}' password '{password}'")

    # create our "server" which is how we connect to DOORS Next
    # first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
    elmserver.setupproxy(jazzhost,proxyport=8888)
    theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

    # create the RM application interface
    dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )

    # open the project
    p = dnapp.find_project(proj)

    # find the component
    c = p.find_local_component(comp)
    comp_u = c.project_uri
    print( f"{comp_u=}" )

    # select the configuration
    config_u = c.get_local_config(conf)
    print( f"{config_u=}" )
    c.set_local_config(config_u)

    # load the folder (using folder query capability)
    # NOTE this returns as soon as it finds a matching folder - i.e. doesn't load them all!
    # build the full new folder name so we can check if it already exists
    fullnewfoldername = sys.argv[3]
    if not fullnewfoldername.endswith( "/" ):
        fullnewfoldername += "/"
    fullnewfoldername += sys.argv[4]
    thefolder = c.load_folders(fullnewfoldername)
    
    # check if the folder doesn't exist
    if thefolder is None:
        # have to create it!
        # get the parent
        thefolder = c.load_folders(sys.argv[3])
        if not thefolder:
            raise Exception( f"Parent folder '{sys.argv[3]}' doesn't exist!" )
    
        # create the new folder
        folderfactory_u = c.reluri( "folders" )
        # this is a pretty nasty way of creating XML; would be much better to build it and let ET do the namespaces!
        # NOTE the rdf:about must be an empty string!
        newfolder_t = f"""<rdf:RDF
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns:dcterms="http://purl.org/dc/terms/"
xmlns:oslc="http://open-services.net/ns/core"
xmlns:oslc_config="http://open-services.net/ns/config#"
xmlns:nav="http://jazz.net/ns/rm/navigation#"
xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/"
>
<nav:folder rdf:about="">
  <dcterms:title>{newfoldername}</dcterms:title>
  <dcterms:description>The description is optional.</dcterms:description>
  <nav:parent rdf:resource="{thefolder.folderuri}"/>
</nav:folder>
</rdf:RDF>"""

        print( f"{newfolder_t=}" )
        newfolder_x = ET.fromstring( newfolder_t )

        response = c.execute_post_rdf_xml( folderfactory_u, data=newfolder_x, params={'projectURL': p.reluri(f'process/project-areas/{p.iid}')}, headers={'vvc.configuration': config_u, 'Configuration-Context': None, }, intent=f"Create the new folder '{newfoldername}' in folder '{sys.argv[3]}'"  )

        thefolder_u = response.headers.get('Location')
    else:
        print( f"Folder URL = {thefolder.folderuri}" )
        thefolder_u = thefolder.folderuri
    # now the folder exists we can put the new artifact in it
    
    # find the requirement creation factory    
    factory_u, shapes = c.get_factory_uri("oslc_rm:Requirement", return_shapes=True)
    print( f"Factory URL = {factory_u}" )
    print( f"Shapes for this factory: {shapes}" )
    
    # Find the type - read the shapes until find one matching the type name on the commandline
    # If you have two or more shapes with the same name this will only return the last matching one - the order is determined by the server and can vary - i.e. different shapes with the same name is a BAD idea!
    # Also shows all the shape names :-)
    theshape_u = None
    for shape_u in shapes:
        # retrieve the type
        shape_x = c.execute_get_rdf_xml( shape_u )
        # check its name
        shape_title = rdfxml.xmlrdf_get_resource_text( shape_x, ".//oslc:ResourceShape/dcterms:title" )
        print( f"{shape_title=}" )
        if shape_title == sys.argv[1]:
            theshape_u = shape_u
            print( f"Found!" )
    if theshape_u is None:
        raise Exception( f"Shape '{sys.argv[1]}' not found!" )
 
    # text of the XML with basic content provided (this is based on example in section 2 of https://jazz.net/library/article/1197
    # If you want more complex and general purpose data such as custom attributes you probably need to use the instanceShape
    # this is a pretty nasty way of creating XML; would be much better to build it and let ET do the namespaces!
    thexml_t = f"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:dc="http://purl.org/dc/terms/"
         xmlns:public_rm_10="http://www.ibm.com/xmlns/rm/public/1.0/"
         xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/"
         xmlns:rm="http://www.ibm.com/xmlns/rdm/rdf/"
         xmlns:acp="http://jazz.net/ns/acp#"
         xmlns:rm_property="https://grarrc.ibm.com:9443/rm/types/"
         xmlns:oslc="http://open-services.net/ns/core#"
         xmlns:nav="http://jazz.net/ns/rm/navigation#"
         xmlns:oslc_rm="http://open-services.net/ns/rm#">
    <rdf:Description rdf:about="">
        <rdf:type rdf:resource="http://open-services.net/ns/rm#Requirement"/>
        <dc:description rdf:parseType="Literal">OSLC Creation Example</dc:description>
        <dc:title rdf:parseType="Literal">{sys.argv[2]}</dc:title>
        <oslc:instanceShape rdf:resource="{theshape_u}"/>
        <nav:parent rdf:resource="{thefolder_u}"/>
    </rdf:Description>
</rdf:RDF>  
 """
    thexml_x = ET.fromstring( thexml_t )
    
    # POST it to create the artifact
    response = c.execute_post_rdf_xml( factory_u, data=thexml_x, intent="Create the artifact"  )
    print( f"POST result = {response.status_code}" )
    location = response.headers.get('Location')
    if response.status_code != 201:
        raise Exception( "POST failed!" )
    theartifact_u = location
    
    # get the artifact so we can show its id
    theartifact_x = c.execute_get_rdf_xml( theartifact_u, intent="Retrieve the artifact so we can show its identifier" )
    
    # show its ID
    theid = rdfxml.xml_find_element( theartifact_x, ".//dcterms:identifier" )
    print( f"Your new artifact has identifier {theid.text} URL {theartifact_u}" )
