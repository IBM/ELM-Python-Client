##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of using the type system import API
# also see https://jazz.net/wiki/bin/view/Main/DNGTypeImport

# the names for project/component/configs involved are hard-coded for simplicity


import csv
import logging
import os.path
import sys
import time

import lxml.etree as ET
import tqdm

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

src_proj = "rm_optin_p1"
src_comp = "rm_optin_p1"
src_config = "rm_optin_p1 Initial Stream"
tgt_proj = "rm_optin_p2"
tgt_comp = "rm_optin_p2"
tgt_config = "changeset for typesystem import"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2


##################################################################################
if __name__=="__main__":

    # create our "server" which is how we connect to DOORS Next
    # first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
    elmserver.setupproxy(jazzhost,proxyport=8888)
    theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

    # create the RM application interface
    dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )

    # open the source project
    src_p = dnapp.find_project(src_proj)

    # find the component
    src_c = src_p.find_local_component(src_comp)
    src_comp_u = src_c.project_uri
    print( f"{src_comp_u=}" )

    # select the configuration
    src_config_u = src_c.get_local_config(src_config)
    print( f"{src_config_u=}" )
    src_c.set_local_config(src_config_u)


    # open the target project
    tgt_p = dnapp.find_project(tgt_proj)

    # find the component
    tgt_c = tgt_p.find_local_component(tgt_comp)
    tgt_comp_u = tgt_c.project_uri
    print( f"{tgt_comp_u=}" )

    # select the configuration
    tgt_config_u = tgt_c.get_local_config(tgt_config)
    print( f"{tgt_config_u=}" )
    tgt_c.set_local_config(tgt_config_u)

    if tgt_config_u is None or src_config_u is None:
        raise Exception( "Source or target config not found!" )
        
    # find the CreationFactory URI for type-delivery session
    typeimport_u = tgt_c.get_factory_uri( resource_type="http://www.ibm.com/xmlns/rdm/types/TypeImportSession" )

    # create the RDF body with the source and target configurations
    content = f"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:types="http://www.ibm.com/xmlns/rdm/types/">
    <types:TypeSystemCopySession>
        <types:target rdf:resource="{tgt_config_u}"/>
        <types:source rdf:resource="{src_config_u}"/>
    </types:TypeSystemCopySession>
</rdf:RDF>"""

    # initiate the delivery session - if successful will return 202 with a task tracker location
    response = tgt_c.execute_post_rdf_xml( reluri=typeimport_u, data=content, cacheable=False, intent="Initiate typesystem import",action='start following task tracker' )
    logger.debug( f" {response.status_code=} {response=}" )
    
    # get the location
    location = response.headers.get('Location')
    
    # check for 202 and location
    if response.status_code == 202 and location is not None:
        # wait for the tracker to finished
        result = tgt_c.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Importing typesystem")
        # TODO: success result is now the xml of the verdict       
        # result None is a success!
        if result is not None and type(result) is not string:
            print( f"Failed Result={result}" )
        else:
            print( f"Success! {result=}" )
    else:
        raise Exception( "Typesystem import failed!" )

