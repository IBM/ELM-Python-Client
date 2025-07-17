##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario1: Run a query for all Test Case modified since 01/01/2025 -> Display their URLs, identifier and title
#

import sys
import os
import csv
import logging
import urllib.parse

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml
import elmclient.httpops as httpops

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

#parameters
jazzhost = 'https://jazz.ibm.com:9443'

username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
qmappdomain  = 'qm'

# the project+component+config that will be queried
proj = "SGC Quality Management"
comp = "SGC MTM"
conf = "SGC MTM Production stream"


# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2
    
#####################################################################################################
# create our "server" which is how we connect to ETM
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring=qmappdomain, cachingcontrol=caching)

#####################################################################################################
# create the ETM application interface
qmapp = theserver.find_app( qmappdomain, ok_to_create=True )
if not qmapp:
    raise Exception( "Problem while creating the ETM application interface" )

#####################################################################################################
# find the project
p = qmapp.find_project( proj )
if not p:
    raise Exception( f"Project {proj} not found !!!" )
pa_u = p.project_uri
#print( f"{pa_u=}" )
#print( f"{p.get_alias()=}" )

# find the component
c = p.find_local_component( comp )
if not c:
    raise Exception( f"Component {comp} not found !!!" )

comp_u = c.project_uri
#print( f"{comp_u=}" )
    
# find the config
local_config_u = c.get_local_config( conf )
if not local_config_u:
    raise Exception( f"Configuration {conf} not found !!!" )
    
# select the configuration - from now on use c for all operations in the local config
c.set_local_config(local_config_u)

#####################################################################################################
#SCENARIO 1 
# find the test cases with dcterms modified > 2025-01-01
tcquerybase = c.get_query_capability_uri("oslc_qm:TestCaseQuery")
if not tcquerybase:
    raise Exception( "TestCaseQueryBase not found !!!" )

tcs = c.execute_oslc_query(
        tcquerybase,
        whereterms=[['dcterms:modified','>','"2025-01-01T00:00:00.000Z"^^xsd:dateTime']],
        select=['dcterms:identifier,dcterms:title,rqm_qm:shortIdentifier'],
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rqm_qm"]:'rqm_qm'} # note this is reversed - url to prefix
        )

nbTC = len(tcs) #count the number of Test case returned by the query
print(f"The query returned {nbTC} Test Cases")
print("----------------------------------------------------------")
count = 0
for TCurl in tcs:
    count+=1
    print(f"Test case #{count}")
    print(TCurl)
    print("Title: " + tcs[TCurl]['dcterms:title'])
    print("Identifier: " + tcs[TCurl]['rqm_qm:shortIdentifier'])
    print("----------------------------------------------------------")

#####################################################################################################


print( "Finished" )
