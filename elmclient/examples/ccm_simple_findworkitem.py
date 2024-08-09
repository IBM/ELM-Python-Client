##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of using the elmclient package to find a work item using OSLC Query for the id, then getting the RDF XML for it
# use log2seq to get a sequence diagram of the interactions with EWM from the logs produced

import csv
import logging

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

jazzhost = 'https://jazz.ibm.com:9443'
username = 'ibm'
password = 'ibm'

jtscontext = 'jts' # specifies /jts change to e.g. jts:jts23 if your jts is on a different context root such as /jts23
ccmcontext  = 'ccm' # specifies /ccm change to e.g. ccm:ccm2 if your ccm is on a different context root such as /ccm2

proj = "SGC Planning and Tasks"

workitemid=38

outfile = "ccm_simple_findworkitem_output.csv"

# caching control
# 0=fully cached (but code below specifies queries aren't cached)
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 0

# create our "server" which is how we connect to EWM
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

# create the CMM application interface
ccmapp = theserver.find_app( f"ccm:{ccmcontext}", ok_to_create=True )

p = ccmapp.find_project( proj )

qcbase = p.get_query_capability_uri("oslc_cm1:ChangeRequest")

# query
results = p.execute_oslc_query(
    qcbase,
    whereterms=[['dcterms:identifier','=',f'"{workitemid}"']],
    select=['*'],
#    prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
    )

workitem_u = list(results.keys())[0]

print( f"Work item {workitemid} uri is {workitem_u}" )

# now retrieve it
workitem_x = p.execute_get_xml( workitem_u, intent="Retrieve the workitem content" )

print( ET.tostring( workitem_x ) )

print( "Finished" )
