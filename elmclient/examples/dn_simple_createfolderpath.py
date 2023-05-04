##
## © Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of creating a folder path
# provide on the commandline (each surrounded by " if it contains a space) the apths of folders you want to create - paths MUST start with /

# For info about folder create API see https://rhnaranjo.wordpress.com/2012/06/25/folder-support-added-to-rrc-4-0-oslc-rm-api-implementation/

# Also see section 2 of https://jazz.net/library/article/1197

#
# folders are found using a OSLC Query capability for folders - this returns one level at a time
# so will likely need a series of queries to find an existing folder
# this is all implemented in load_fodlers()
# new create_folders() will create a folder path and update the loaded folders so a full reload isn't needed
#

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
    if len(sys.argv) < 2:
        raise Exception( 'Provide one or more space-separated paths on the commandline' )


    print( f"Attempting to create paths '{sys.argv[1:]}' in project '{proj}' in configuration {conf}" )
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

    for path in sys.argv[1:]:

        thefolder = c.find_folder(path)
        
        # check if the path doesn't exist
        if thefolder is None:
            # have to create it!
            # get the parent
            thefolder = c.create_folder( path )
            print( f"Folder '{path}' created uri is {thefolder.folderuri}" )
        else:
            print( f"Folder '{path}' already exists" )
    
