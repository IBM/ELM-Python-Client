##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario4: Run a query for all Test Plans modified since 01/01/2025
#               -> Display their URL, identifier, title, number of test cases and test case URLs
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

#### DO NOT TOUCH elmclient initializing####### Go to scenario4
import sys
import os
import logging

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml
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
#SCENARIO 4
# Query all Test Plans modified after 01/01/2025.
# For each plan, do a GET to retrieve the full resource, then display:
#   - URL, identifier, title
#   - number of test cases
#   - list validateRequiremtCollection links
#
# Why a GET per plan?
# The OSLC query can return scalar fields via select, but oslc_qm:usesTestCase is
# multi-valued and not reliably returned in full by all ETM query endpoints.
# A GET on the plan URL gives the complete RDF/XML, which TestPlan.from_etree()
# parses into the test_cases list directly.

# Get the Test Plan query capability URI
tpquerybase = c.get_query_capability_uri("oslc_qm:TestPlanQuery")
if not tpquerybase:
    raise Exception( "TestPlanQueryBase not found !!!" )

# OSLC query: Test Plans modified after 2025-01-01, retrieve identifier and title
tps = c.execute_oslc_query(
        tpquerybase,
        whereterms=[['dcterms:modified','>','"2025-01-01T00:00:00.000Z"^^xsd:dateTime']],
        select=['dcterms:identifier,dcterms:title,rqm_qm:shortIdentifier'],
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rqm_qm"]:'rqm_qm'} # note this is reversed - url to prefix
        )

nbTP = len(tps)
print(f"The query returned {nbTP} Test Plan(s)")
print("----------------------------------------------------------")

count = 0

for tp_url in tps:
    count += 1
    print(f"Test Plan #{count}")
    print(f"URL:        {tp_url}")
    print(f"Title:      {tps[tp_url]['dcterms:title']}")
    print(f"Identifier: {tps[tp_url]['rqm_qm:shortIdentifier']}")

    # GET the full Test Plan resource to retrieve the test cases list and the validatesRequirementCollection links
    xml_data = c.execute_get_rdf_xml(tp_url, cacheable=False)
    tpObject = TestPlan.from_etree(xml_data)

    print(f"Test Cases: {len(tpObject.test_cases)}")
    print(f"validatesRequirementCollection links: {len(tpObject.links)}")
    for link in tpObject.links:
        print(f" - {link.predicate} -> {link.target} (title: {link.title})")

    print("----------------------------------------------------------")

#####################################################################################################

print( "Finished" )
