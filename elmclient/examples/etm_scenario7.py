##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario7: Query all Test Scripts modified since 2026-01-01
#               -> For each script, GET the full resource and list its steps:
#                  - Step index (rqm_qm:index) and title
#                  - Expected result
#                  - validatesRequirement links (title + target URL)
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

#### DO NOT TOUCH elmclient initializing####### Go to scenario7
import sys
import os
import logging

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml
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
#SCENARIO 7
#
# ETM Test Scripts are made of TWO separate resource types:
#
#   1. VersionedExecutionScript  (the "script" resource)
#      - Has its own URL returned by the OSLC query
#      - Contains metadata: title, description, shortIdentifier, etc.
#      - Does NOT embed step content — it only holds a list of step URLs
#        via the rqm_qm:containsTestScriptStep property (one per step)
#
#   2. ExecutionElement2  (the "step" resource)
#      - Each step is a completely separate ETM resource with its own URL
#      - Contains: title, description, expected result, rqm_qm:index,
#        and oslc_qm:validatesRequirement links
#      - rqm_qm:index is the authoritative step order (1-based integer)
#        The server does NOT guarantee that containsTestScriptStep elements
#        are returned in index order, so we must sort after fetching.
#
# This means displaying a script with its steps requires:
#   - 1 OSLC query  -> returns the list of matching script URLs
#   - 1 GET per script -> to read the list of step URLs
#   - 1 GET per step   -> to read the step content (title, result, links)

# ---------------------------------------------------------------------------
# Get the OSLC query capability URI for Test Scripts
# ---------------------------------------------------------------------------
# The service document exposes one query capability per artifact type.
# "oslc_qm:TestScriptQuery" is the registered name for Test Scripts.
tsquerybase = c.get_query_capability_uri("oslc_qm:TestScriptQuery")
if not tsquerybase:
    raise Exception( "TestScriptQueryBase not found !!!" )

# ---------------------------------------------------------------------------
# OSLC query: find Test Scripts modified after 2026-01-01
# ---------------------------------------------------------------------------
# whereterms  : filter condition — dcterms:modified > the given dateTime
# select      : fields to return inline in the query response
#               (avoids a GET per script just to read title and identifier)
# prefixes    : maps full namespace URIs to the short prefixes used above
#               NOTE: the dict is reversed — key=URI, value=prefix
tss = c.execute_oslc_query(
        tsquerybase,
        whereterms=[['dcterms:modified','>','"2026-01-01T00:00:00.000Z"^^xsd:dateTime']],
        select=['dcterms:title,rqm_qm:shortIdentifier'],
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rqm_qm"]:'rqm_qm'}
        )

print(f"The query returned {len(tss)} Test Script(s)")
print("----------------------------------------------------------")

for count, ts_url in enumerate(tss, start=1):
    print(f"Test Script #{count}")
    print(f"  URL:        {ts_url}")
    # tss[ts_url] is a dict of the fields we asked for in 'select'
    print(f"  Title:      {tss[ts_url].get('dcterms:title', '(unknown)')}")
    print(f"  Identifier: {tss[ts_url].get('rqm_qm:shortIdentifier', '(unknown)')}")

    # -----------------------------------------------------------------------
    # GET the full Test Script resource
    # -----------------------------------------------------------------------
    # The query response only returns the fields listed in 'select'.
    # To get the list of step URLs (rqm_qm:containsTestScriptStep) we need
    # to do a GET on the script URL and parse the full RDF/XML response.
    # cacheable=False ensures we always get the latest version from the server.
    # TestScript.from_etree() parses the RDF/XML into a Python object and
    # populates tsObject.step_urls with all step URLs found in the response.
    xml_ts = c.execute_get_rdf_xml(ts_url, cacheable=False)
    tsObject = TestScript.from_etree(xml_ts)

    print(f"  Steps: {len(tsObject.step_urls)}")

    # -----------------------------------------------------------------------
    # Fetch all steps and sort them by rqm_qm:index
    # -----------------------------------------------------------------------
    # fetch_and_sort_steps() does three things in one call:
    #   1. Issues a GET for each URL in tsObject.step_urls
    #   2. Parses each response into a TestScriptStep object
    #   3. Sorts the resulting list by rqm_qm:index (ascending)
    #
    # We pass a lambda so that the testscript module stays independent of
    # the HTTP layer — it receives a generic "give me the XML for this URL"
    # function and does not need to know about elmclient internals.
    steps = tsObject.fetch_and_sort_steps(
        lambda url: c.execute_get_rdf_xml(url, cacheable=False)
    )

    for stepObject in steps:
        # stepObject.index is rqm_qm:index — the authoritative step order
        print(f"    Step {stepObject.index}: {stepObject.title}")

        # expected_result is stored as an XHTML string in ETM
        # e.g. '<div xmlns="http://www.w3.org/1999/xhtml"><p>result text</p></div>'
        print(f"      Expected result: {stepObject.expected_result or '(none)'}")

        # validatesRequirement links are stored as reified rdf:Statement nodes.
        # Each link has: predicate, target (requirement URL) and an optional title.
        # We filter on the predicate to display only validatesRequirement links
        # (a step could in theory carry other link types in the future).
        if stepObject.links:
            print(f"      validatesRequirement links:")
            for lnk in stepObject.links:
                if lnk.predicate == "http://open-services.net/ns/qm#validatesRequirement":
                    print(f"        - {lnk.title or '(no title)'} -> {lnk.target}")
        else:
            print(f"      validatesRequirement links: (none)")

    print("----------------------------------------------------------")

#####################################################################################################

print( "Finished" )
