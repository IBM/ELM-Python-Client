##
## © Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of updating a core artifact

# provide on the commandline the id of an artifact in the  project/component/configuration to delete
# this code finds the core artifact and all its bindings, delees each binding individually then deletes the core artifact
# will delete whole modules with deleting the bindings in it

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
proj = "rm_optout_p2"
comp = proj
conf =  f"{comp} Initial Stream"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2
    
##################################################################################
if __name__=="__main__":
    if len(sys.argv) != 2:
        raise Exception( 'You must provide an identifier for the artifact to delete' )

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

    # find the artifact - using OSLC Query

    # get the query capability base URL for requirements
    qcbase = c.get_query_capability_uri("oslc_rm:Requirement")

    # query for a title and for format=module
    artifacts = c.execute_oslc_query(
        qcbase,
        whereterms=[['dcterms:identifier','=',f'"{sys.argv[1]}"']],
        select=['*'],
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
        )
        
#    print( f"{artifacts=}" )

    if len(artifacts)==0:
        raise Exception( f"No artifact with identifier '{sys.argv[1]}' found in project {proj} component {comp} configuration {conf}" )
    elif len(artifacts)>2:
        for k,v in artifacts.items():
            print( f'{k} ID {v.get("dcterms:identifier","???")} Title {v.get("dcterms:title","")}' )
        raise Exception( "More than one artifcact with that id in project {proj} component {comp} configuraition {conf}" )
    
    # find the core artifact - it has a value for rm_nav:parent
    theartifact_u = None
    bindings=[]
    for artifact in artifacts.keys():
#        print( f"Testing parent on {artifact=}" )
        if artifacts[artifact].get("rm_nav:parent") is not None:
            if theartifact_u:
                barf
            theartifact_u = artifact
        else:
            bindings.append(artifact)
    
    if bindings:
        # delete the bindings one by one
        for binding_u in bindings:
            print( f"Deleting binding {binding_u}" )
            # now get the artifact content and its etag
            theartifact_x, etag = c.execute_get_rdf_xml( binding_u, return_etag=True, intent="Retrieve the artifact" )
            print( f"{ET.tostring(theartifact_x)=}\n" )

            # get the text - this is always xhtml in a div below jazz_rm:primaryText
            thetext = rdfxml.xml_find_element( theartifact_x, ".//jazz_rm:primaryText/xhtml:div" )
            print( f"Binding {sys.argv[1]} text='{thetext}'" )
            
            # DELETE to remove the binding
            response = c.execute_delete( binding_u, headers={'If-Match':etag}, intent="Update the artifact"  )
            print( f"{response.status_code}" )
            location = response.headers.get('Location')
            if response.status_code != 200:
                raise Exception( "Binding DELETE failed!" )
            else:
                print( f"Binding delete succeeded!" )
            
    else:
        print( f"No bindings!" )

    if not theartifact_u:
        raise Exception( "Artifact with rm_nav:parent (i.e. the core artifact) not found!" )

    print( f"Found core artifact {theartifact_u=}" )

    # now get the artifact content and its etag
    theartifact_x, etag = c.execute_get_rdf_xml( theartifact_u, return_etag=True, intent="Retrieve the artifact" )
    print( f"{ET.tostring(theartifact_x)=}\n" )

    # find the text - this is always xhtml in a div below jazz_rm:primaryText
    thetext = rdfxml.xml_find_element( theartifact_x, ".//jazz_rm:primaryText/xhtml:div" )
    print( f"Artifact {sys.argv[1]} text='{thetext}'" )
    
    # DELETE it to remove the core artifact
    response = c.execute_delete( theartifact_u, headers={'If-Match':etag}, intent="Delete the artifact"  )
    print( f"{response.status_code}" )
    location = response.headers.get('Location')
    if response.status_code != 200:
        raise Exception( "DELETE failed!" )
        
                    
