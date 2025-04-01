##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# Test for authentication timeout
# retrieve a protected resource with login, then
# sits retreiving it every minute with login disabled, i.e. until login fails
# due to authentication timeout

#import csv
import logging

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

POLLINTERVAL=10

jazzhost = 'https://jazz.ibm.com:9443'
username = 'ibm'
password = 'ibm'
#username = 'tokenuser'
#password = 'tokenuser'

protected_u = jazzhost+"/rm/process/project-areas"

jtscontext = 'jts' # specifies /jts change to e.g. jts:jts23 if your jts is on a different context root such as /jts23
rmcontext  = 'rm' # specifies /ccm change to e.g. ccm:ccm2 if your ccm is on a different context root such as /ccm2

#proj = "SGC Planning and Tasks"

#workitemid=38

#outfile = "ccm_simple_findworkitem_output.csv"

# caching control
# 0=fully cached (but code below specifies queries aren't cached)
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2

# create our "server" which is how we connect to EWM
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
#theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", cachingcontrol=caching)

# create the RM application interface
#rmapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )

#p = ccmapp.find_project( proj )

starttime = time.perf_counter()
nextendtime = starttime
autologin = True

while True:
	# now retrieve the protected resource
    elapsedsecs = time.perf_counter() - starttime
    print( f"Runtime {int(elapsedsecs/60)}m {int(elapsedsecs%60):02d}s" )

    resource_x = theserver.execute_get_xml( protected_u, intent="Retrieve protected resource", automaticlogin=autologin, close=True )

    autologin = False
    
    while nextendtime < time.perf_counter():
        nextendtime += POLLINTERVAL
        
    time.sleep( nextendtime - time.perf_counter() )
    
    if utils.kbhit():
        ch = utils.getch()
        print( f"{ch=}" )
        if ch == b'\x1b':
            break

print( "Finished" )
