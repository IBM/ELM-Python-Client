##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario6: Create a new Test Plan
#               -> Create 3 new Test Cases
#               -> Add the 3 Test Cases to the Test Plan
#               -> Add a ValidatesRequirementCollection link to the Test Plan:
#                  https://jazz.ibm.com:9443/rm/resources/CO_cqyhzqUjEfCyB8IKcgJhMA
#                  with title "Release 1 Planning"
#
#parameters
jazzhost = 'https://jazz.ibm.com:9443'

username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
qmappdomain  = 'qm'

# the project+component+config that will be used
proj = "SGC Quality Management"
comp = "SGC MTM"
conf = "SGC MTM Production stream"

#### DO NOT TOUCH elmclient initializing####### Go to scenario6
import sys
import os
import logging

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.httpops as httpops
from elmclient.testplan import TestPlan, TestPlanLink
from elmclient.testcase import TestCase, TestCaseLink

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
#SCENARIO 6
#
# Step 1 - Create a new Test Plan
# Step 2 - Create 3 new Test Cases
# Step 3 - Add the 3 Test Cases to the Test Plan
# Step 4 - Add a ValidatesRequirementCollection link to the Test Plan
# Step 5 - Save (PUT) the Test Plan

# Get the JSESSIONID cookie required for POST requests
jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID', None)
if not jsessionid:
    raise Exception( "JSESSIONID not found!" )

post_headers = {'Referer': jazzhost + '/qm', 'X-Jazz-CSRF-Prevent': jsessionid}

# ---------------------------------------------------------------------------
# STEP 1 - Create a new Test Plan
# ---------------------------------------------------------------------------

print("--- Step 1: Creating a new Test Plan ---")

tp_title       = "New TP created by Python ELMclient (scenario 6)"
tp_description = "Test Plan created by Python ELMclient (scenario 6)"

newTP = TestPlan.create_minimal(tp_title)
newTP.description = tp_description

tp_factory_u = c.get_factory_uri(resource_type='TestPlan', context=None, return_shapes=False)

response = c.execute_post_rdf_xml(
    tp_factory_u,
    data=newTP.to_etree(),
    intent="Create a test plan",
    headers=post_headers,
    remove_parameters=['oslc_config.context']
)

if response.status_code != 201:
    raise Exception( f"Failed to create Test Plan: HTTP {response.status_code}" )

print("Test Plan created successfully")

# The Location header in the 201 response directly gives the new Test Plan URL
tp_url = response.headers.get('Location')
if not tp_url:
    raise Exception( "No Location header in the Test Plan creation response!" )
print(f"New Test Plan URL: {tp_url}")

# GET the full Test Plan resource (with ETag for the subsequent PUT)
print("Doing a GET on the Test Plan URL...")
xml_data_tp, etag = c.execute_get_rdf_xml(tp_url, return_etag=True, cacheable=False)
print(f"ETag: {etag}")

tpObject = TestPlan.from_etree(xml_data_tp)

# ---------------------------------------------------------------------------
# STEP 2 - Create 3 new Test Cases
# ---------------------------------------------------------------------------

print("\n--- Step 2: Creating 3 new Test Cases ---")

tc_factory_u = c.get_factory_uri(resource_type='TestCase', context=None, return_shapes=False)

tc_definitions = [
    ("TC1 created by Python ELMclient (scenario 6)", "Test Case 1 created by Python ELMclient (scenario 6)"),
    ("TC2 created by Python ELMclient (scenario 6)", "Test Case 2 created by Python ELMclient (scenario 6)"),
    ("TC3 created by Python ELMclient (scenario 6)", "Test Case 3 created by Python ELMclient (scenario 6)"),
]

tc_urls = []

for i, (tc_title, tc_description) in enumerate(tc_definitions, start=1):
    print(f"  Creating Test Case {i}: '{tc_title}'")
    newTC = TestCase.create_minimal(tc_title)
    newTC.description = tc_description

    response = c.execute_post_rdf_xml(
        tc_factory_u,
        data=newTC.to_etree(),
        intent=f"Create test case {i}",
        headers=post_headers,
        remove_parameters=['oslc_config.context']
    )

    if response.status_code != 201:
        raise Exception( f"Failed to create Test Case {i}: HTTP {response.status_code}" )

    tc_url = response.headers.get('Location')
    if not tc_url:
        raise Exception( f"No Location header in Test Case {i} creation response!" )

    tc_urls.append(tc_url)
    print(f"  Test Case {i} URL: {tc_url}")

# ---------------------------------------------------------------------------
# STEP 3 - Add the 3 Test Cases to the Test Plan
# ---------------------------------------------------------------------------

print("\n--- Step 3: Adding the 3 Test Cases to the Test Plan ---")

for tc_url in tc_urls:
    tpObject.add_usesTestCase(tc_url)
    print(f"  Added usesTestCase link -> {tc_url}")

# ---------------------------------------------------------------------------
# STEP 4 - Add a ValidatesRequirementCollection link to the Test Plan
# ---------------------------------------------------------------------------

print("\n--- Step 4: Adding a ValidatesRequirementCollection link to the Test Plan ---")

req_collection_url   = "https://jazz.ibm.com:9443/rm/resources/CO_cqyhzqUjEfCyB8IKcgJhMA"
req_collection_title = "Release 1 Planning"

tpObject.add_validatesRequirementCollectionLink(req_collection_url, req_collection_title)
print(f"Added validatesRequirementCollection link -> {req_collection_url} (title: '{req_collection_title}')")

# ---------------------------------------------------------------------------
# STEP 5 - PUT the updated Test Plan (3 TCs + requirement collection link)
# ---------------------------------------------------------------------------

print("\n--- Step 5: Saving the Test Plan (PUT) ---")

response = c.execute_post_rdf_xml(
    tp_url,
    data=tpObject.to_etree(),
    put=True,
    cacheable=False,
    headers={'If-Match': etag, 'Content-Type': 'application/rdf+xml'},
    intent="Update the Test Plan"
)

if response.status_code == 200:
    print("Test Plan updated successfully")
    print(f"  - Title: '{tp_title}'")
    print(f"  - Description: '{tp_description}'")
    for i, tc_url in enumerate(tc_urls, start=1):
        print(f"  - usesTestCase {i}: {tc_url}")
    print(f"  - validatesRequirementCollection: {req_collection_url} (title: '{req_collection_title}')")
else:
    print(f"Test Plan update failed: HTTP {response.status_code}")

#####################################################################################################

print("\nFinished")
