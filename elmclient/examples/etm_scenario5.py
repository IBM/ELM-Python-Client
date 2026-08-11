##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario5: Find Test Plan with identifier 2
#               -> Update its description
#               -> Create a new Test Case and add it to the Test Plan
#               -> Add a new ValidateRequirementCollection link to
#                  https://jazz.ibm.com:8443/dwa/rm/urn:rational::1-6989e7b94842499a-M-000000e1
#                  with title "moduleGC"
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

#### DO NOT TOUCH elmclient initializing####### Go to scenario5
import sys
import os
import logging

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml
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
#SCENARIO 5
#
# Step 1 - Find Test Plan with identifier 2 and update its description
# Step 2 - Create a new Test Case
# Step 3 - Add the new Test Case to the Test Plan
# Step 4 - Add a new ValidateRequirementCollection link to the Test Plan

# ---------------------------------------------------------------------------
# STEP 1 - Find the Test Plan with shortIdentifier = 2 and update description
# ---------------------------------------------------------------------------

# Identifier of the Test Plan we are looking for
tp_identifier = 2

print(f"--- Step 1: Finding Test Plan with identifier = {tp_identifier} ---")

# Get the Test Plan query capability URI
tpquerybase = c.get_query_capability_uri("oslc_qm:TestPlanQuery")
if not tpquerybase:
    raise Exception( "TestPlanQueryBase not found !!!" )

# OSLC query to find the Test Plan by its shortIdentifier
tps = c.execute_oslc_query(
        tpquerybase,
        whereterms=[['rqm_qm:shortIdentifier','=',f'"{tp_identifier}"']],
        select=['dcterms:identifier,dcterms:title,rqm_qm:shortIdentifier'],
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rqm_qm"]:'rqm_qm'} # note this is reversed - url to prefix
        )

if len(tps) == 0:
    raise Exception( f"No Test Plan found with identifier = {tp_identifier}" )
if len(tps) > 1:
    raise Exception( f"More than one Test Plan found with identifier = {tp_identifier} !!!???" )

tp_url = list(tps.keys())[0]
print(f"Found Test Plan URL: {tp_url}")
print(f"Title:      {tps[tp_url]['dcterms:title']}")
print(f"Identifier: {tps[tp_url]['rqm_qm:shortIdentifier']}")

# GET the full Test Plan resource (with ETag for the subsequent PUT)
print("Doing a GET on the Test Plan URL...")
xml_data, etag = c.execute_get_rdf_xml(tp_url, return_etag=True, cacheable=False)
print(f"ETag: {etag}")

# Parse into a TestPlan object
tpObject = TestPlan.from_etree(xml_data)

# Update the description
new_description = "Description updated by Python ELMclient (scenario 5)"
tpObject.description = new_description
print(f"Updated description to: '{new_description}'")

# ---------------------------------------------------------------------------
# STEP 2 - Create a new Test Case
# ---------------------------------------------------------------------------

print("\n--- Step 2: Creating a new Test Case ---")

# Title and description for the new Test Case
tc_title       = "New TC created by Python ELMclient (scenario 5)"
tc_description = "Test Case created and linked to Test Plan by Python ELMclient (scenario 5)"

# Create a minimal TestCase object
newTC = TestCase.create_minimal(tc_title)
newTC.description = tc_description

# Get the Test Case factory URI
tc_factory_u = c.get_factory_uri(resource_type='TestCase', context=None, return_shapes=False)

# Get the JSESSIONID cookie required for the POST request
jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID', None)
if not jsessionid:
    raise Exception( "JSESSIONID not found!" )

# POST request to create the new Test Case
xml_data_tc = newTC.to_etree()
response = c.execute_post_rdf_xml(
    tc_factory_u,
    data=xml_data_tc,
    intent="Create a test case",
    headers={'Referer': jazzhost + '/qm', 'X-Jazz-CSRF-Prevent': jsessionid},
    remove_headers=['Configuration-Context']
)

if response.status_code != 201:
    raise Exception( f"Failed to create Test Case: HTTP {response.status_code}" )

print("Test Case created successfully")

# The Location header in the 201 response directly gives the new Test Case URL
tc_url = response.headers.get('Location')
if not tc_url:
    raise Exception( "No Location header in the Test Case creation response!" )
print(f"New Test Case URL: {tc_url}")

# ---------------------------------------------------------------------------
# STEP 3 - Add the new Test Case to the Test Plan
# ---------------------------------------------------------------------------

print("\n--- Step 3: Adding the new Test Case to the Test Plan ---")

# Add an oslc_qm:usesTestCase link pointing to the newly created Test Case
tpObject.add_usesTestCase(tc_url)
print(f"Added usesTestCase link -> {tc_url}")

# ---------------------------------------------------------------------------
# STEP 4 - Add a ValidatesRequirementCollection link to the Test Plan
# ---------------------------------------------------------------------------

print("\n--- Step 4: Adding a ValidatesRequirementCollection link to the Test Plan ---")

req_collection_url   = "https://jazz.ibm.com:8443/dwa/rm/urn:rational::1-6989e7b94842499a-M-000000e1"
req_collection_title = "moduleGC"

tpObject.add_validatesRequirementCollectionLink(req_collection_url, req_collection_title)
print(f"Added validatesRequirementCollection link -> {req_collection_url} (title: '{req_collection_title}')")

# ---------------------------------------------------------------------------
# PUT request to save the updated Test Plan (description + new TC + new link)
# ---------------------------------------------------------------------------

print("\nSending PUT request to update the Test Plan...")
xml_data_tp = tpObject.to_etree()
response = c.execute_post_rdf_xml(
    tp_url,
    data=xml_data_tp,
    put=True,
    cacheable=False,
    headers={'If-Match': etag, 'Content-Type': 'application/rdf+xml'},
    intent="Update the Test Plan"
)

if response.status_code == 200:
    print("Test Plan updated successfully")
    print(f"  - Description set to: '{new_description}'")
    print(f"  - usesTestCase link added for: {tc_url}")
    print(f"  - validatesRequirementCollection link added for: {req_collection_url} (title: '{req_collection_title}')")
else:
    print(f"Test Plan update failed: HTTP {response.status_code}")

#####################################################################################################

print( "Finished" )
