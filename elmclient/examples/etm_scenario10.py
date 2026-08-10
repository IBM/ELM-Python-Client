##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario10: Get the Test Case with shortIdentifier = 7
#                -> Display its title and description
#                -> Get all TCERs attached to that Test Case
#                -> For each TCER display: title, last result (status), last modified date
#
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

# The shortIdentifier of the Test Case to look up
TC_SHORT_ID = "7"

#### DO NOT TOUCH elmclient initializing####### Go to scenario10
import sys
import os
import logging

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml
from elmclient.testcase import TestCase
from elmclient.testexecutionrecord import TestExecutionRecord
from elmclient.testresult import TestResult

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

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delete folder .web_cache
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

# find the component
c = p.find_local_component( comp )
if not c:
    raise Exception( f"Component {comp} not found !!!" )

# find the config
local_config_u = c.get_local_config( conf )
if not local_config_u:
    raise Exception( f"Configuration {conf} not found !!!" )

# select the configuration - from now on use c for all operations in the local config
c.set_local_config(local_config_u)

#####################################################################################################
# SCENARIO 10

# ---------------------------------------------------------------------------
# STEP 1 - Find the Test Case with shortIdentifier = 7
# ---------------------------------------------------------------------------

tcquerybase = c.get_query_capability_uri("oslc_qm:TestCaseQuery")
if not tcquerybase:
    raise Exception( "TestCaseQuery capability URI not found !!!" )

# Query by shortIdentifier — this is the human-readable ID visible in the ETM UI
tcs = c.execute_oslc_query(
    tcquerybase,
    whereterms=[['rqm_qm:shortIdentifier', '=', f'"{TC_SHORT_ID}"']],
    select=['dcterms:title', 'dcterms:description', 'rqm_qm:shortIdentifier'],
    prefixes={
        rdfxml.RDF_DEFAULT_PREFIX["dcterms"]: 'dcterms',
        rdfxml.RDF_DEFAULT_PREFIX["rqm_qm"]:  'rqm_qm',
    },
)

if len(tcs) == 0:
    raise Exception( f"No Test Case found with shortIdentifier = {TC_SHORT_ID}" )
if len(tcs) > 1:
    raise Exception( f"More than one Test Case found with shortIdentifier = {TC_SHORT_ID} (unexpected)" )

tc_url = list(tcs.keys())[0]

# GET the full Test Case resource to access all fields including description
tc_xml = c.execute_get_rdf_xml(tc_url, cacheable=False)
tcObject = TestCase.from_etree(tc_xml)

print("==========================================================")
print(f"TEST CASE  (id = {TC_SHORT_ID})")
print("==========================================================")
print(f"  URL        : {tcObject.uri}")
print(f"  Title      : {tcObject.title or '(no title)'}")
print(f"  Description: {tcObject.description or '(no description)'}")
print("----------------------------------------------------------")

# ---------------------------------------------------------------------------
# STEP 2 - Find all TCERs that reference this Test Case
#
# TCERs are NOT embedded in the TestCase XML — the link lives on the TCER side
# (oslc_qm:runsTestCase).  We use tc.tcer_query_terms() to build the correct
# OSLC whereterms automatically.
# ---------------------------------------------------------------------------

terquerybase = c.get_query_capability_uri("oslc_qm:TestExecutionRecordQuery")
if not terquerybase:
    raise Exception( "TestExecutionRecordQuery capability URI not found !!!" )

tcers = c.execute_oslc_query(
    terquerybase,
    whereterms=tcObject.tcer_query_terms(),
    select=['dcterms:title', 'dcterms:modified', 'rqm_qm:currentTestResult'],
    prefixes={
        rdfxml.RDF_DEFAULT_PREFIX["dcterms"]: 'dcterms',
        rdfxml.RDF_DEFAULT_PREFIX["rqm_qm"]:  'rqm_qm',
    },
)

nb_tcers = len(tcers)
print(f"  {nb_tcers} Test Case Execution Record(s) found")
print("==========================================================")

if nb_tcers == 0:
    print( "  (No TCERs attached to this Test Case)")
    print( "Finished" )
    sys.exit(0)

# ---------------------------------------------------------------------------
# STEP 3 - For each TCER: display title, last result (status), last modified
# ---------------------------------------------------------------------------

for tcer_count, tcer_url in enumerate(tcers, start=1):

    # GET the full TCER resource to access current_test_result and other fields
    tcer_xml = c.execute_get_rdf_xml(tcer_url, cacheable=False)
    tcerObject = TestExecutionRecord.from_etree(tcer_xml)

    # Resolve the last result status by GETting the currentTestResult if present
    last_result_status = "(no result yet)"
    if tcerObject.current_test_result:
        tr_xml = c.execute_get_rdf_xml(tcerObject.current_test_result, cacheable=False)
        trObject = TestResult.from_etree(tr_xml)
        if trObject.status:
            # Strip the long ETM prefix to keep the display readable
            # e.g. "com.ibm.rqm.execution.common.state.passed" -> "passed"
            last_result_status = trObject.status.rsplit('.', 1)[-1]

    print(f"  TCER #{tcer_count}")
    print(f"    Title         : {tcerObject.title or '(no title)'}")
    print(f"    Last modified : {tcerObject.modified or '(unknown)'}")
    print(f"    Last result   : {last_result_status}")
    print("----------------------------------------------------------")

#####################################################################################################

print( "Finished" )
