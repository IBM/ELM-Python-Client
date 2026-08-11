##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient sample for TSE

#ETM scenario3: Create a new test case
#• Set the title and description
#• Save the test case
#• Add 2 Validated By links, 1 to a DNG requirement – 1 to a DWA requirement

#parameters
jazzhost = 'https://jazz.ibm.com:9443'

username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
qmappdomain  = 'qm'

# the project+component+config that will be queried
proj = "SGC Quality Management"
comp = "SGC MTM"
conf = "SGC MTM Production stream" #conf="" if project is optout

#### DO NOT TOUCH elmclient initializing####### Go to scenario3
import sys
import os
import csv
import logging
import urllib.parse

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.httpops as httpops
from elmclient.testcase import TestCase, TestCaseLink
import lxml.etree as ET

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
    
    
# if project is optin -> find the config
if conf!="":
    local_config_u = c.get_local_config( conf )
    if not local_config_u:
        raise Exception( f"Configuration {conf} not found !!!" )
        
    # select the configuration - from now on use c for all operations in the local config
    c.set_local_config(local_config_u)
#print(f"{local_config_u=}")
#####################################################################################################
#SCENARIO 3
#Create a new test case
#• Set the title and description
#• Save the test case
#• Add 2 Validated By links, 1 to a DNG requirement – 1 to a DWA requirement

#get the factory URL
tc_factory_u = c.get_factory_uri(resource_type='TestCase',context=None, return_shapes=False)

#variable for our tc title and description
tc_title = "my new TC created by Python ELMclient"
tc_description = "description from the new TC created by Python ELMclient"

#creating a new object TestCase with a single argument: title
newTC = TestCase.create_minimal(tc_title)
#add the description to our test case
newTC.description = tc_description

#get the XML representation of the new Test Case
xml_data = newTC.to_etree()

#get the ELM cookie id, needed for the POST request
jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID',None)
if not jsessionid:
    raise Exception( "JSESSIONID not found!" )

#POST request to create the new test case
response = c.execute_post_rdf_xml( tc_factory_u, data=xml_data, intent="Create a test case", headers={'Referer': 'https://jazz.ibm.com:9443/qm', 'X-Jazz-CSRF-Prevent': jsessionid }, remove_headers=['Configuration-Context']  )

#if response is 201, Test Case has been created succesfully
if response.status_code != 201:
    raise Exception( f"Failed to create Test Case: HTTP {response.status_code}" )

print("Test Case created successfully")

# The Location header in the 201 response directly gives the new Test Case URL
tc_u = response.headers.get('Location')
if not tc_u:
    raise Exception( "No Location header in the Test Case creation response!" )
print(f"New Test Case URL: {tc_u}")

print("Doing a GET on test case url")
xml_data, etag = c.execute_get_rdf_xml( tc_u, return_etag=True)
print("Etag: " + etag)

#put the TC data in a test case object
newTC = TestCase.from_etree(xml_data)

#adding a link to a DWA requirement, provide URL and link title
newTC.add_validatesRequirementLink("https://dwa9729rom1.fyre.ibm.com:8443/dwa/rm/urn:rational::1-66cdc1432a885b81-O-2-00000040","Module1 (2)")

#adding a link to a DNG requirement, provide URL and link title
newTC.add_validatesRequirementLink("https://jazz.ibm.com:9443/rm/resources/BI_kC8csQ_WEfCjT5cep7iZxA","req3")

#get the data from the test case object
xml_data = newTC.to_etree()
print("Sending the PUT request to update the test case")
response = c.execute_post_rdf_xml(tc_u, data=xml_data, put=True, cacheable=False, headers={'If-Match':etag,'Content-Type':'application/rdf+xml'}, intent="Update the test case")
if response.status_code == 200:
    print("Update successful")
else:
    print(f"Update failed: HTTP {response.status_code}")

####################################################################################################

print( "Finished" )
