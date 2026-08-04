##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario8: Create a new Test Script with 3 steps
#               -> Each step has a title, description and expected result
#               -> Each step has a validatesRequirement link
#
# WORKFLOW
# --------
# Step 1 - POST the new Test Script        → Location header → script URL
# Step 2 - GET the script (OSLC RDF/XML)   → captures execution_instructions_url
# Step 3 - PUT steps via put_steps()       → ETM creates 3 ExecutionElement2 resources
# Step 4 - GET the script again            → step_urls now contains the real step URLs
# Step 5 - For each step: put_with_link()  → adds validatesRequirement link
# Step 6 - Verify: fetch steps, print links
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

#### DO NOT TOUCH elmclient initializing####### Go to scenario8
import sys
import os
import logging

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.httpops as httpops
from elmclient.testscript import TestScript, TestScriptStep, TestScriptStepDefinition

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
#SCENARIO 8
#
# Create a new Test Script with 3 steps that have links to Requirements
#
# Get the JSESSIONID cookie required for POST/PUT requests
jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID', None)
if not jsessionid:
    raise Exception( "JSESSIONID not found!" )

post_headers = {'Referer': jazzhost + '/qm', 'X-Jazz-CSRF-Prevent': jsessionid}

# Step definitions — each step carries: title, description, expected_result, req_url, req_title
# The first three fields map to TestScriptStepDefinition; req_url/req_title are used in Step 5.
step_definitions = [
    (
        TestScriptStepDefinition(
            title           = "Step 1 - Login",
            description     = "Open the application and log in with valid credentials",
            expected_result = "The user is logged in and the dashboard is displayed",
        ),
        "https://jazz.ibm.com:9443/rm/resources/BI_kC8csQ_WEfCjT5cep7iZxA",
        "req1",
    ),
    (
        TestScriptStepDefinition(
            title           = "Step 2 - Navigate to settings",
            description     = "Click on the Settings menu item",
            expected_result = "The Settings page is displayed",
        ),
        "https://jazz.ibm.com:9443/rm/resources/BI_kC8csQ_WEfCjT5cep7iZxB",
        "req2",
    ),
    (
        TestScriptStepDefinition(
            title           = "Step 3 - Logout",
            description     = "Click on the Logout button",
            expected_result = "The user is logged out and the login page is displayed",
        ),
        "https://jazz.ibm.com:9443/rm/resources/BI_kC8csQ_WEfCjT5cep7iZxC",
        "req3",
    ),
]

# ---------------------------------------------------------------------------
# STEP 1 - POST the new Test Script
# ---------------------------------------------------------------------------

print("--- Step 1: Creating the Test Script ---")

ts_factory_u = c.get_factory_uri(resource_type='TestScript', context=None, return_shapes=False)
if not ts_factory_u:
    raise Exception( "TestScript factory URI not found" )

newTS = TestScript.create_minimal(
    "New TS created by Python ELMclient (scenario 8)",
    description="Test Script created by Python ELMclient (scenario 8)",
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

# ---------------------------------------------------------------------------
# STEP 2 - GET the script to populate execution_instructions_url
# ---------------------------------------------------------------------------

print("\n--- Step 2: GET the Test Script ---")

tsObject = TestScript.from_etree( c.execute_get_rdf_xml(ts_url, cacheable=False) )
if not tsObject.execution_instructions_url:
    raise Exception( "No oslc_qm:executionInstructions found — script may not be fully initialised." )
print(f"executionInstructions URL: {tsObject.execution_instructions_url}")

# ---------------------------------------------------------------------------
# STEP 3 - Create the 3 steps via IIntegrationService
# ---------------------------------------------------------------------------

print("\n--- Step 3: Creating steps ---")

tsObject.put_steps(
    session      = p.app.server._session,
    steps        = [step_def for step_def, _, _ in step_definitions],
    post_headers = post_headers,
)
print("Steps created successfully")

# ---------------------------------------------------------------------------
# STEP 4 - Re-GET the script to collect the real step URLs
# ---------------------------------------------------------------------------

print("\n--- Step 4: GET the Test Script to retrieve step URLs ---")

tsObject = TestScript.from_etree( c.execute_get_rdf_xml(ts_url, cacheable=False) )
print(f"Script now has {len(tsObject.step_urls)} step(s)")
if len(tsObject.step_urls) != len(step_definitions):
    raise Exception( f"Expected {len(step_definitions)} steps but found {len(tsObject.step_urls)}." )

# ---------------------------------------------------------------------------
# STEP 5 - Add a validatesRequirement link to each step
# ---------------------------------------------------------------------------

print("\n--- Step 5: Adding validatesRequirement links ---")

# Build index → (req_url, req_title) from the step definitions (sorted by index)
req_by_index = {
    i: (req_url, req_title)
    for i, (_, req_url, req_title) in enumerate(step_definitions, start=1)
}

steps = tsObject.fetch_and_sort_steps(
    lambda url: c.execute_get_rdf_xml(url, cacheable=False)
)

for stepObject in steps:
    req_url, req_title = req_by_index.get(stepObject.index, (None, None))
    if req_url is None:
        continue
    print(f"  Step {stepObject.index}: adding link -> {req_url} (title: '{req_title}')")
    stepObject.put_with_link(c, post_headers, req_url, req_title)
    print(f"  Step {stepObject.index} updated successfully")

# ---------------------------------------------------------------------------
# STEP 6 - Verify
# ---------------------------------------------------------------------------

print("\n--- Step 6: Verifying steps and links ---")

tsObject = TestScript.from_etree( c.execute_get_rdf_xml(ts_url, cacheable=False) )
steps = tsObject.fetch_and_sort_steps(
    lambda url: c.execute_get_rdf_xml(url, cacheable=False)
)

for stepObject in steps:
    print(f"  Step {stepObject.index}: {stepObject.title}")
    vr_links = [
        lnk for lnk in stepObject.links
        if lnk.predicate == "http://open-services.net/ns/qm#validatesRequirement"
    ]
    for lnk in vr_links:
        print(f"    validatesRequirement -> {lnk.target} (title: {lnk.title})")
    if not vr_links:
        print(f"    (no validatesRequirement links)")

#####################################################################################################

print( "Finished" )
