##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# extended example of using the type system import API, creating an automatically-named changeset, importing, delivering the CS
# also see https://jazz.net/wiki/bin/view/Main/DNGTypeImport

# the names for project/component/configs involved are hard-coded for simplicity


import csv
import datetime
import logging
import os.path
import sys
import time

import lxml.etree as ET
import tqdm

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml


# setup logging - see levels in utils.py - TRACE means you can use log2seq to get a html sequence diagram
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
src_comp = "rm_optin_p1_comp3"
src_config = "rm_optin_p1_comp3 Initial Stream"
tgt_config = "rm_optin_p1_comp3 Child Stream"

cs_name = "Edit reqt title"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2

##################################################################################
if __name__=="__main__":

    # first file handler:
    datetimestamp = '{:%Y%m%d-%H%M%S}'.format(datetime.datetime.now())
    csname = f"{cs_name} {datetimestamp}"
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

    # select the source configuration
    src_config_u = src_c.get_local_config(src_config)
    print( f"{src_config_u=}" )
    src_c.set_local_config(src_config_u)


    # create the changeset in the target config
    cs_u = src_c.create_changeset( name=csname )
    print( f"{cs_u=}" )

    # switch to the changeset config for the import
    src_c.set_local_config(cs_u)

    # find the reqt we're going to edit, as a resource
    reqt = src_c.queryResourcesByIDs( [2237] )[0]
    
    print( f"BEFORE {reqt=}" )
    
    # edit its title
    reqt.Title += " EDITED"
    print( f"AFTER {reqt=}" )
    print( f"{reqt._modifieds=}" )
    # save the updated reqt
    reqt.put()
    # deliver the changeset in the stream it was created in
    
    # now deliver the changeset
#    src_c.deliver(policy="http://jazz.net/ns/rm/dng/config#sourceWinsPolicy")
    src_c.deliver(policy=["http://jazz.net/ns/rm/dng/config#sourceWinsPolicy","http://jazz.net/ns/rm/dng/config#mergeIndependentAttributes"])
    
    # deliver stream->stream
    burp
    
    # select the target configuration for stream->stream delivery
    tgt_config_u = src_c.get_local_config(tgt_config)
    print( f"{tgt_config_u=}" )
    if tgt_config_u is None:
        # create the stream
        tgt_config_u = src_c.create_stream( streamname=tgt_config )
        
    if tgt_config_u is None or src_config_u is None:
        raise Exception( "Source or target config not found!" )
    
    src_c.set_local_config(src_config_u)
    src_c.deliver(tgt_config_u)
    