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
# HOW ETM CREATES TEST SCRIPT STEPS
# -----------------------------------
# ETM has no OSLC creation factory for TestScriptStep (there is no POST endpoint
# that creates steps as standalone OSLC resources).
#
# The ONLY reliable approach for config-managed projects is the IIntegrationService
# (legacy RQM REST API).  Every test script resource exposes a property:
#
#   oslc_qm:executionInstructions rdf:resource="<iintegrationservice_url>"
#
# That URL points to the ETM-native XML representation of the script, and it is
# what the ETM web UI uses internally to manage steps.  A PUT to that URL with
# the full step list (in ETM-native XML, not RDF/XML) creates/replaces all steps
# atomically, without needing oslc_config.context.
#
# ETM-native step XML format (namespace http://jazz.net/xmlns/prod/jazz/rqm/qm/1.0/)
# -----------------------------------------------------------------------------------
#   <ns2:testscript xmlns:ns2="http://jazz.net/xmlns/prod/jazz/rqm/qm/1.0/"
#                   xmlns:ns4="http://purl.org/dc/elements/1.1/">
#     <ns4:title>Script title</ns4:title>
#     <ns2:steps>
#       <ns2:step type="com.ibm.rqm.execution.common.type.manual">
#         <ns2:title>Step 1</ns2:title>
#         <ns2:description>Plain text or XHTML</ns2:description>
#         <ns2:expectedResult>Plain text or XHTML</ns2:expectedResult>
#       </ns2:step>
#       ...
#     </ns2:steps>
#   </ns2:testscript>
#
# WORKFLOW
# --------
# Step 1 - POST the new Test Script        → Location header → script URL
# Step 2 - GET the script                  → live object; captures execution_instructions_url
# Step 3 - GET the executionInstructions   → inspect the current native XML (printed for TSE)
# Step 4 - PUT the executionInstructions   → ETM creates all 3 steps atomically
# Step 5 - GET the script again            → step_urls now contains the real step URLs
# Step 6 - For each step: GET → add validatesRequirement link → PUT (OSLC RDF/XML)
# Step 7 - Verify: fetch steps sorted by index, print links
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

#### DO NOT TOUCH elmclient initializing####### Go to scenario8
import sys
import os
import logging

import lxml.etree as ET

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.httpops as httpops
from elmclient.testscript import TestScript, TestScriptStep

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
#SCENARIO 8

# Get the JSESSIONID cookie required for POST/PUT requests
jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID', None)
if not jsessionid:
    raise Exception( "JSESSIONID not found!" )

post_headers = {'Referer': jazzhost + '/qm', 'X-Jazz-CSRF-Prevent': jsessionid}

# ---------------------------------------------------------------------------
# STEP 1 - POST the new Test Script
# ---------------------------------------------------------------------------
# The services.xml has a creationFactory for TestScript
# (oslc:resourceType = oslc_qm:TestScript).
# create_minimal() sets title, description, rdf:type and the mandatory
# rqm_qm:scriptType (manual) property.

print("--- Step 1: Creating the Test Script ---")

ts_title       = "New TS created by Python ELMclient (scenario 8)"
ts_description = "Test Script created by Python ELMclient (scenario 8)"

ts_factory_u = c.get_factory_uri(resource_type='TestScript', context=None, return_shapes=False)
if not ts_factory_u:
    raise Exception( "TestScript factory URI not found" )

newTS = TestScript.create_minimal(ts_title, description=ts_description)

response = c.execute_post_rdf_xml(
    ts_factory_u,
    data=newTS.to_etree(),
    intent="Create a test script",
    headers=post_headers,
    remove_parameters=['oslc_config.context']
)

if response.status_code != 201:
    raise Exception( f"Failed to create Test Script: HTTP {response.status_code}" )

# The Location header directly gives the new Test Script URL — no query needed
ts_url = response.headers.get('Location')
if not ts_url:
    raise Exception( "No Location header in the Test Script creation response!" )
print(f"Test Script created: {ts_url}")

# ---------------------------------------------------------------------------
# STEP 2 - GET the script to obtain execution_instructions_url
# ---------------------------------------------------------------------------
# oslc_qm:executionInstructions in the RDF/XML points to the IIntegrationService
# URL for this script.  That is the endpoint we use to create steps.

print("\n--- Step 2: GET the Test Script ---")

xml_ts = c.execute_get_rdf_xml(ts_url, cacheable=False)
tsObject = TestScript.from_etree(xml_ts)

if not tsObject.execution_instructions_url:
    raise Exception(
        "No oslc_qm:executionInstructions found on the Test Script resource.\n"
        "This is the IIntegrationService URL required to create steps.\n"
        "The script may not have been fully initialised by ETM — try again."
    )

print(f"executionInstructions URL: {tsObject.execution_instructions_url}")

# ---------------------------------------------------------------------------
# STEP 3 - GET the executionInstructions (ETM-native XML)
# ---------------------------------------------------------------------------
# This GET returns the current ETM-native XML representation of the script.
# For a freshly created script it will have no steps yet.
# We print it so the TSE can see the exact format before we PUT.
#
# Note: execute_get_xml sends Accept: application/xml (not RDF/XML),
# which is what the IIntegrationService endpoint expects.

print("\n--- Step 3: GET the executionInstructions (ETM-native XML) ---")

native_xml = c.execute_get_xml(
    tsObject.execution_instructions_url,
    cacheable=False,
    intent="GET the native XML representation of the script from IIntegrationService"
)

print("Current ETM-native XML (pretty-printed):")
print(ET.tostring(native_xml.getroot(), pretty_print=True).decode())

# ---------------------------------------------------------------------------
# STEP 4 - Build the step XML and PUT to executionInstructions
# ---------------------------------------------------------------------------
# We build a <testscript> document in ETM-native XML (not RDF/XML).
# The namespace is http://jazz.net/xmlns/prod/jazz/rqm/qm/1.0/
# Each <step> element has:
#   - type attribute: "com.ibm.rqm.execution.common.type.manual"
#   - <title>      : step title (plain text)
#   - <description>: step description (plain text or XHTML)
#   - <expectedResult>: expected result (plain text or XHTML)
#
# The PUT replaces the entire step list atomically.
# After the PUT, ETM creates real ExecutionElement2 OSLC resources for each step
# and links them to the script via rqm_qm:containsTestScriptStep.

print("\n--- Step 4: PUT steps via executionInstructions ---")

# Step definitions: (title, description, expected_result, req_url, req_title)
step_definitions = [
    (
        "Step 1 - Login",
        "Open the application and log in with valid credentials",
        "The user is logged in and the dashboard is displayed",
        "https://jazz.ibm.com:9443/rm/resources/BI_kC8csQ_WEfCjT5cep7iZxA",
        "req1",
    ),
    (
        "Step 2 - Navigate to settings",
        "Click on the Settings menu item",
        "The Settings page is displayed",
        "https://jazz.ibm.com:9443/rm/resources/BI_kC8csQ_WEfCjT5cep7iZxB",
        "req2",
    ),
    (
        "Step 3 - Logout",
        "Click on the Logout button",
        "The user is logged out and the login page is displayed",
        "https://jazz.ibm.com:9443/rm/resources/BI_kC8csQ_WEfCjT5cep7iZxC",
        "req3",
    ),
]

# Build the ETM-native XML document
# The namespace map mirrors what ETM uses in its own responses
_NS_QM  = "http://jazz.net/xmlns/prod/jazz/rqm/qm/1.0/"
_NS_DC  = "http://purl.org/dc/elements/1.1/"

NSMAP = {
    'ns2': _NS_QM,
    'ns4': _NS_DC,
}

root_el = ET.Element(ET.QName(_NS_QM, 'testscript'), nsmap=NSMAP)

# Title (dc:title — preserves the script title)
title_el = ET.SubElement(root_el, ET.QName(_NS_DC, 'title'))
title_el.text = ts_title

# Steps container
steps_el = ET.SubElement(root_el, ET.QName(_NS_QM, 'steps'))

for title, description, expected_result, _req_url, _req_title in step_definitions:
    step_el = ET.SubElement(
        steps_el,
        ET.QName(_NS_QM, 'step'),
        {'type': 'com.ibm.rqm.execution.common.type.manual'}
    )
    t = ET.SubElement(step_el, ET.QName(_NS_QM, 'title'))
    t.text = title

    d = ET.SubElement(step_el, ET.QName(_NS_QM, 'description'))
    d.text = description

    e = ET.SubElement(step_el, ET.QName(_NS_QM, 'expectedResult'))
    e.text = expected_result

print("ETM-native XML we are about to PUT (pretty-printed):")
print(ET.tostring(root_el, pretty_print=True).decode())

# PUT using execute_post_rdf_xml with put=True.
# Override Content-Type to application/xml — the IIntegrationService endpoint
# does NOT accept application/rdf+xml.
# Also skip oslc_config.context — this endpoint is not config-aware.
response = c.execute_post_rdf_xml(
    tsObject.execution_instructions_url,
    data=ET.ElementTree(root_el),
    put=True,
    cacheable=False,
    headers={**post_headers, 'Content-Type': 'application/xml'},
    intent="PUT step definitions to IIntegrationService",
    remove_parameters=['oslc_config.context']
)

if response.status_code not in (200, 204):
    raise Exception(
        f"Failed to PUT steps to executionInstructions: HTTP {response.status_code}\n"
        f"Response body: {response.text[:500]}"
    )
print(f"Steps PUT successful (HTTP {response.status_code})")

# ---------------------------------------------------------------------------
# STEP 5 - GET the script again to retrieve the real step URLs
# ---------------------------------------------------------------------------
# After the PUT to executionInstructions, ETM has created real ExecutionElement2
# OSLC resources for each step and linked them to the script via
# rqm_qm:containsTestScriptStep.  We GET the script again (with config context
# this time — the steps now exist in the stream) to collect those URLs.

print("\n--- Step 5: GET the script to retrieve real step URLs ---")

xml_ts = c.execute_get_rdf_xml(ts_url, cacheable=False)
tsObject = TestScript.from_etree(xml_ts)

print(f"Script now has {len(tsObject.step_urls)} step(s)")
for step_url in tsObject.step_urls:
    print(f"  {step_url}")

if len(tsObject.step_urls) != len(step_definitions):
    raise Exception(
        f"Expected {len(step_definitions)} steps but found {len(tsObject.step_urls)}.\n"
        f"The IIntegrationService PUT may have failed silently or steps are not yet visible.\n"
        f"Check the ETM server logs for more details."
    )

# ---------------------------------------------------------------------------
# STEP 6 - For each step: GET → add validatesRequirement link → PUT
# ---------------------------------------------------------------------------
# Steps are now real OSLC resources (ExecutionElement2), so we can GET/PUT them
# with the standard OSLC RDF/XML approach.
# oslc_config.context IS needed here — steps are config-managed resources
# visible in the stream after the IIntegrationService PUT.

print("\n--- Step 6: Adding validatesRequirement links to each step ---")

# Build a dict: index -> (req_url, req_title) for lookup after sorting
req_by_index = {
    i: (req_url, req_title)
    for i, (_, _, _, req_url, req_title) in enumerate(step_definitions, start=1)
}

# Fetch all steps and sort them by rqm_qm:index so we can match them to
# the step_definitions list reliably (ETM may return steps in any order)
steps = tsObject.fetch_and_sort_steps(
    lambda url: c.execute_get_rdf_xml(url, cacheable=False)
)

for stepObject in steps:
    req_url, req_title = req_by_index.get(stepObject.index, (None, None))
    if req_url is None:
        print(f"  Step {stepObject.index}: no matching requirement — skipping")
        continue

    # Re-GET with ETag for the conditional PUT (optimistic locking)
    xml_step, step_etag = c.execute_get_rdf_xml(
        stepObject.uri,
        return_etag=True,
        cacheable=False
    )
    stepObject = TestScriptStep.from_etree(xml_step)

    stepObject.add_validatesRequirementLink(req_url, title=req_title)
    print(f"  Step {stepObject.index}: adding link -> {req_url} (title: '{req_title}')")

    response = c.execute_post_rdf_xml(
        stepObject.uri,
        data=stepObject.to_etree(),
        put=True,
        cacheable=False,
        headers={**post_headers, 'If-Match': step_etag, 'Content-Type': 'application/rdf+xml'},
        intent=f"Update step {stepObject.index} with validatesRequirement link"
    )

    if response.status_code != 200:
        raise Exception( f"Failed to update step {stepObject.index}: HTTP {response.status_code}" )
    print(f"  Step {stepObject.index} updated successfully")

# ---------------------------------------------------------------------------
# STEP 7 - Verify: fetch all steps sorted by index and print links
# ---------------------------------------------------------------------------

print("\n--- Step 7: Verifying steps and links ---")

# Refresh tsObject to pick up any step URL changes (defensive re-GET)
xml_ts = c.execute_get_rdf_xml(ts_url, cacheable=False)
tsObject = TestScript.from_etree(xml_ts)

steps = tsObject.fetch_and_sort_steps(
    lambda url: c.execute_get_rdf_xml(url, cacheable=False)
)

for stepObject in steps:
    print(f"  Step {stepObject.index}: {stepObject.title}")
    vr_links = [
        lnk for lnk in stepObject.links
        if lnk.predicate == "http://open-services.net/ns/qm#validatesRequirement"
    ]
    if vr_links:
        for lnk in vr_links:
            print(f"    validatesRequirement -> {lnk.target} (title: {lnk.title})")
    else:
        print(f"    (no validatesRequirement links)")

#####################################################################################################

print("\nFinished")
