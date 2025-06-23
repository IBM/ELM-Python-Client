##
## © Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of updating a core artifact

# provide on the commandline the id of an artifact in the  project/component/configuration
# also provide on the commandline a string (surrounded in " if it includes space) and this will be put on the front of the existing text of the artifact

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
proj = "rm_optin_p1"
comp = proj
conf =  f"{comp} Initial Stream"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 0

##################################################################################
if __name__=="__main__":
    if len(sys.argv) != 3:
        raise Exception( 'You must provide an identifier and a string (surrounded by " if including spaces)' )

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
    for artifact in artifacts.keys():
#        print( f"Testing parent on {artifact=}" )
        if artifacts[artifact].get("rm_nav:parent") is not None:
            theartifact_u = artifact
            break

    if not theartifact_u:
        raise Exception( "Artifact with rm_nav:parent not found!" )

    print( f"Found core artifact {theartifact_u=}" )

    art = c.retrieveResource( theartifact_u )
    
    print( f"{art=}" )
    print( vars( art ) )
    
    burp
    # now get the artifact content and its etag
    theartifact_x, etag = c.execute_get_rdf_xml( theartifact_u, return_etag=True, intent="Retrieve the artifact" )
    print( f"{ET.tostring(theartifact_x)=}\n" )

    # update the text - this is always xhtml in a div below jazz_rm:primaryText
    # NOTE the xml primary text div is a tag hierarchy so setting the text below it just updates the top-level tag, i.e. doesn't remove
    # any subtags - if you want to replace the entire context then you need to remove those other tags!
    thetext = rdfxml.xml_find_element( theartifact_x, ".//jazz_rm:primaryText/xhtml:div" )
    thetext.text = sys.argv[2] + thetext.text
    
    # PUT it back to update the artifact
    response = c.execute_post_rdf_xml( theartifact_u, data=theartifact_x, put=True, cacheable=False, headers={'If-Match':etag}, intent="Update the artifact"  )
    print( f"{response.status_code}" )
    location = response.headers.get('Location')
    if response.status_code != 200:
        raise Exception( "PUT failed!" )
                    
    # get the content again
    theartifact_x, etag = c.execute_get_rdf_xml( theartifact_u, return_etag=True, intent="Retrieve the artifact" )
    thetext = rdfxml.xml_find_element( theartifact_x, ".//jazz_rm:primaryText/xhtml:div" )
    print( f"{ET.tostring(thetext)=}" )

