##
## © Copyright 2025- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient DN Resources sample
#
# DN scenario 4: Create a Stakeholder Requirement and a System Requirement, and link them System Requirement->Satisifed By->Stakeholder Requirement
#, set the primaryText of it to some "Hellow, World" html
#

#parameters

jazzhost = 'https://jazz.ibm.com:9443'
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

# the project+compontent+config that will be updated
proj = "rm_optin_p2"
comp = proj
conf =  f"{comp} Initial Stream"

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

# setup logging - see levels in utils.py - TRACE,OFF means that a log of all http communication is put in the logs folder below wherever this example is run
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

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2

##################################################################################
if __name__=="__main__":
    
    #####################################################################################################
    # create our "server" which is how we connect to DOORS Next
    # first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
    elmserver.setupproxy(jazzhost,proxyport=8888)
    theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

    #####################################################################################################
    # create the RM application interface
    dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )

    #####################################################################################################
    # open the project
    p = dnapp.find_project(proj)

    #####################################################################################################
    # find the component
    c = p.find_local_component(comp)
    print( f"{c=}" )
    comp_u = c.project_uri
    print( f"{comp_u=}" )

    #####################################################################################################
    # select the configuration
    config_u = c.get_local_config(conf)
    print( f"{config_u=}" )
    c.set_local_config(config_u)
    
## find an example with a pre-created link so you can see the format
#    coresys=c.resourceQuery( "Identifier=4770",returnBindings=False )
#    print( f"{coresys=}" )

    #####################################################################################################
    # create a stakeholder requirement
    reqt1 = c.createCoreResource( "Stakeholder Requirement" )
    
    print( f"Stakeholder Requirement artifact ID is {reqt1.Identifier}" )

#    print( f"{reqt1}" )

    reqt1.Primary_Text = '<div xmlns="http://www.w3.org/1999/xhtml">I am what a Stakeholder wants!</div>'
    
    reqt1.put()
    
    print( f"With the updated primaryText your Stakeholder Requirement is:\n{reqt1}" )
    
    #####################################################################################################
    # create a system requirement
    reqt2 = c.createCoreResource( "System Requirement" )
    
    print( f"System Requirement artifact ID is {reqt2.Identifier}" )

#    print( f"{reqt2}" )

    reqt2.Primary_Text = '<div xmlns="http://www.w3.org/1999/xhtml">I am what a Systems Engineer wants!</div>'
    
    reqt2.put()
    
    print( f"With the updated primaryText your System Requirement is:\n{reqt2}" )

    #####################################################################################################
    # create Satisfies link from the System Requirement to the Stakeholder Requirement
    reqt2.Questions="There is a question"
    reqt2.Test_Criteria="There are some criteria"
    
    reqt2.put()
    
    print( f"With the Questions set your System Requirement is: {reqt2}" )
    
    # create the link to the reqt1 id
    reqt2.Satisfies=reqt1.Identifier
    
    reqt2.put()
    
    print( f"With the Satisfies link your System Requirement is: {reqt2}" )
