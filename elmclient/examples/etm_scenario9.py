##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario9: Create a Test Script with 3 steps
#               -> Create a Test Case and add the Test Script to it
#               -> Create a Test Plan and add the Test Case to it
#
# WORKFLOW
# --------
# Step 1 - POST the new Test Script        → Location header → script URL
# Step 2 - GET the script                  → captures execution_instructions_url
# Step 3 - PUT steps via put_steps()       → ETM creates 3 ExecutionElement2 resources
# Step 4 - POST the new Test Case          → Location header → test case URL
# Step 5 - GET the Test Case with ETag     → add usesTestScript link → PUT
# Step 6 - POST the new Test Plan          → Location header → test plan URL
# Step 7 - GET the Test Plan with ETag     → add usesTestCase link  → PUT
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
conf = "SGC MTM Production stream" #conf="" if project is optout

#### DO NOT TOUCH elmclient initializing####### Go to scenario9
import sys
import os
import logging

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.httpops as httpops
from elmclient.testscript import TestScript, TestScriptStep, TestScriptStepDefinition
from elmclient.testcase import TestCase, TestCaseLink
from elmclient.testplan import TestPlan, TestPlanLink

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
#SCENARIO 9
#
# Step 1 - Create a Test Script with 3 steps
# Step 2 - Create a Test Case and add the Test Script to it
# Step 3 - Create a Test Plan and add the Test Case to it

# Get the JSESSIONID cookie required for POST/PUT requests
jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID', None)
if not jsessionid:
    raise Exception( "JSESSIONID not found!" )

post_headers = {'Referer': jazzhost + '/qm', 'X-Jazz-CSRF-Prevent': jsessionid}

# ---------------------------------------------------------------------------
# STEP 1 - Create the Test Script (POST + PUT steps)
# ---------------------------------------------------------------------------

print("--- Step 1: Creating the Test Script ---")

#define the 3 steps (title, description, expected result)
step_definitions = [
    TestScriptStepDefinition(
        title           = "Step 1 - Login",
        description     = "Open the application and log in with valid credentials",
        expected_result = "The user is logged in and the dashboard is displayed",
    ),
    TestScriptStepDefinition(
        title           = "Step 2 - Navigate to settings",
        description     = "Click on the Settings menu item",
        expected_result = "The Settings page is displayed",
    ),
    TestScriptStepDefinition(
        title           = "Step 3 - Logout",
        description     = "Click on the Logout button",
        expected_result = "The user is logged out and the login page is displayed",
    ),
]

#get the Test Script factory URI and POST the new script
ts_factory_u = c.get_factory_uri(resource_type='TestScript', context=None, return_shapes=False)
if not ts_factory_u:
    raise Exception( "TestScript factory URI not found" )

newTS = TestScript.create_minimal(
    "New TS created by Python ELMclient (scenario 9)",
    description="Test Script created by Python ELMclient (scenario 9)",
)

response = c.execute_post_rdf_xml(
    ts_factory_u,
    data=newTS.to_etree(),
    intent="Create a test script",
    headers=post_headers,
    remove_parameters=['oslc_config.context']
)
if response.status_code != 201:
    raise Exception( f"Failed to create Test Script: HTTP {response.status_code}" )

ts_url = response.headers.get('Location')
if not ts_url:
    raise Exception( "No Location header in the Test Script creation response!" )
print(f"Test Script created: {ts_url}")

#GET the script to populate execution_instructions_url, then PUT the 3 steps
tsObject = TestScript.from_etree( c.execute_get_rdf_xml(ts_url, cacheable=False) )
if not tsObject.execution_instructions_url:
    raise Exception( "No oslc_qm:executionInstructions found — script may not be fully initialised." )

tsObject.put_steps(
    session      = p.app.server._session,
    steps        = step_definitions,
    post_headers = post_headers,
)
print("3 steps created successfully")

# ---------------------------------------------------------------------------
# STEP 2 - Create the Test Case and add the Test Script to it
# ---------------------------------------------------------------------------

print("\n--- Step 2: Creating the Test Case ---")

#create a minimal Test Case object
tc_title       = "New TC created by Python ELMclient (scenario 9)"
tc_description = "Test Case created by Python ELMclient (scenario 9)"

newTC = TestCase.create_minimal(tc_title)
newTC.description = tc_description

#get the Test Case factory URI and POST the new test case
tc_factory_u = c.get_factory_uri(resource_type='TestCase', context=None, return_shapes=False)

response = c.execute_post_rdf_xml(
    tc_factory_u,
    data=newTC.to_etree(),
    intent="Create a test case",
    headers=post_headers,
    remove_parameters=['oslc_config.context']
)
if response.status_code != 201:
    raise Exception( f"Failed to create Test Case: HTTP {response.status_code}" )

tc_url = response.headers.get('Location')
if not tc_url:
    raise Exception( "No Location header in the Test Case creation response!" )
print(f"Test Case created: {tc_url}")

#GET the Test Case with ETag, add the usesTestScript link, then PUT
xml_data, etag = c.execute_get_rdf_xml(tc_url, return_etag=True, cacheable=False)
tcObject = TestCase.from_etree(xml_data)

tcObject.add_usesTestScript(ts_url)
print(f"Added usesTestScript link -> {ts_url}")

response = c.execute_post_rdf_xml(
    tc_url,
    data=tcObject.to_etree(),
    put=True,
    cacheable=False,
    headers={'If-Match': etag, 'Content-Type': 'application/rdf+xml'},
    intent="Update the Test Case"
)
if response.status_code == 200:
    print("Test Case updated successfully")
else:
    print(f"Test Case update failed: HTTP {response.status_code}")

# ---------------------------------------------------------------------------
# STEP 3 - Create the Test Plan and add the Test Case to it
# ---------------------------------------------------------------------------

print("\n--- Step 3: Creating the Test Plan ---")

#create a minimal Test Plan object
tp_title       = "New TP created by Python ELMclient (scenario 9)"
tp_description = "Test Plan created by Python ELMclient (scenario 9)"

newTP = TestPlan.create_minimal(tp_title)
newTP.description = tp_description

#get the Test Plan factory URI and POST the new test plan
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

tp_url = response.headers.get('Location')
if not tp_url:
    raise Exception( "No Location header in the Test Plan creation response!" )
print(f"Test Plan created: {tp_url}")

#GET the Test Plan with ETag, add the usesTestCase link, then PUT
xml_data, etag = c.execute_get_rdf_xml(tp_url, return_etag=True, cacheable=False)
tpObject = TestPlan.from_etree(xml_data)

tpObject.add_usesTestCase(tc_url)
print(f"Added usesTestCase link -> {tc_url}")

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
    print("----------------------------------------------------------")
    print(f"Test Script URL: {ts_url}")
    print(f"Test Case URL:   {tc_url}")
    print(f"Test Plan URL:   {tp_url}")
    print("----------------------------------------------------------")
else:
    print(f"Test Plan update failed: HTTP {response.status_code}")

#####################################################################################################

print( "Finished" )
