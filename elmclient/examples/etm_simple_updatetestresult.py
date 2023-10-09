##
## Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient ETM simple example of adding a new test result to a test execution record
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

jazzhost = 'https://jazz.ibm.com:9443'
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
qmappdomain  = 'qm'

# the project+component+config that will be queried
proj = "SGC Quality Management"
comp = "SGC MTM"
conf = "SGC MTM Production stream"

outfile = "etm_test results.csv"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 1

#####################################################################################################

def writeresultstocsv( outfile, queryresults ):
    # want to find all the headers
    allcolumns = {}
    for uri,row in queryresults.items():
        for k in row.keys():
            allcolumns[k]=True

    def safeint(s):
        try:
            return int(s.get('dcterms:identifier',0))
        except:
            pass
        return 0
        
    # sort by dcterms.identifier
    uris = sorted(queryresults, key=lambda s: safeint(queryresults[s]) )

    print( f"Writing results to CSV {outfile}" )

    with open( outfile, "w", newline='' ) as csvfile:
        csvwriter = csv.DictWriter(csvfile,fieldnames=sorted(allcolumns.keys()))
        csvwriter.writeheader()
        for uri in uris:
            row = queryresults[uri]
            csvwriter.writerow(row)

#####################################################################################################
# get the commandline args
if len(sys.argv) != 5:
    raise Exception("need exactly four arguments - the testplan name, the testcase name and the tcer name, and the verdict (passed or failed) - BE CAREFUL WITH EXACT SPELLING!" )
    
tpname = sys.argv[1]
tcname = sys.argv[2]
tcername = sys.argv[3]
verdict = sys.argv[4]

if verdict not in ['passed', 'failed']:
    raise Exception( "Only verdicts pass or failed are accepted!" )
    
#####################################################################################################
# create our "server" which is how we connect to ETM
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring=qmappdomain, cachingcontrol=caching)

#####################################################################################################
# create the RM application interface
qmapp = theserver.find_app( qmappdomain, ok_to_create=True )
if not qmapp:
    raise Exception( "Something serious went wrong" )

#####################################################################################################
# find the project/component/config
p = qmapp.find_project( proj )
if not p:
    raise Exception( "Something serious went wrong" )
pa_u = p.project_uri
print( f"{pa_u=}" )
print( f"{p.get_alias()=}" )

c = p.find_local_component( comp )
if not c:
    raise Exception( "Something serious went wrong" )

comp_u = c.project_uri
print( f"{comp_u=}" )
    
local_config_u = c.get_local_config( conf )
if not local_config_u:
    raise Exception( "Something serious went wrong" )
    
# select the configuration - from now on use c for all operations in the local config
c.set_local_config(local_config_u)

#####################################################################################################
# find the test plan

tpquerybase = c.get_query_capability_uri("oslc_qm:TestPlanQuery")
if not tpquerybase:
    raise Exception( "Something serious went wrong" )

# query for Test Case
tps = c.execute_oslc_query(
    tpquerybase,
    whereterms=[['dcterms:title','=',f'"{tpname}"']],
    select=['*'],
#    prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
    )
if len(tps.items())!=1:
    raise Exception( "Something serious went wrong" )
#print( f"\n{tcs=}" )
#print( f"\n{tcs.items()=}" )
#print( f"\n{list(tcs.keys())[0]=}" )

# the testcase URL is the only key as exactly one result :-)
tp_u = list(tps.keys())[0]
print( f"{tp_u=}" )

writeresultstocsv( "01_testplans.csv", tps )


#####################################################################################################
# find the test case
tcquerybase = c.get_query_capability_uri("oslc_qm:TestCaseQuery")
if not tcquerybase:
    raise Exception( "Something serious went wrong" )

# query for Test Case
tcs = c.execute_oslc_query(
    tcquerybase,
    whereterms=[['dcterms:title','=',f'"{tcname}"']],
    select=['*'],
#    prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
    )
if len(tcs.items())!=1:
    raise Exception( "Something serious went wrong" )
#print( f"\n{tcs=}" )
#print( f"\n{tcs.items()=}" )
#print( f"\n{list(tcs.keys())[0]=}" )

# the testcase URL is the only key as exactly one result :-)
tc_u = list(tcs.keys())[0]
print( f"{tc_u=}" )

writeresultstocsv( "02_testcases.csv", tcs )

#####################################################################################################
# Now find the test execution record which refers to the tc and has the title=tcername
terquerybase = c.get_query_capability_uri("oslc_qm:TestExecutionRecordQuery")
if not terquerybase:
    raise Exception( "Something serious went wrong" )

tcers = c.execute_oslc_query(
    terquerybase,
    whereterms=[['and',['oslc_qm:runsTestCase','=',f'<{tc_u}>'],['dcterms:title','=',f'"{tcername}"']]],
    select=['*'],
#    prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
    )

print( f"TERs: {len(tcers.items())}" )

writeresultstocsv( "03_testcaseexecutionrecords.csv", tcers )

if len(tcers)>1:
    raise Exception( "Too many tcers!" )
# if len(tcers)==0 we need to create a TER
if len(tcers)==0:
    print( "Need to create a TER)" )
    tcer_factory_u = c.get_factory_uri(resource_type='TestExecutionRecord',context=None, return_shapes=False)
    if not tcer_factory_u:
        raise Exception( "Something serious went wrong" )
    print( f"{tcer_factory_u=}" )
   
    tcer_x = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:rqm_auto="http://jazz.net/ns/auto/rqm#"
    xmlns:bp="http://open-services.net/ns/basicProfile#"
    xmlns:acp="http://jazz.net/ns/acp#"
    xmlns:cmx="http://open-services.net/ns/cm-x#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/"
    xmlns:rqm_lm="http://jazz.net/ns/qm/rqm/labmanagement#"
    xmlns:acc="http://open-services.net/ns/core/acc#"
    xmlns:process="http://jazz.net/ns/process#"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:oslc="http://open-services.net/ns/core#"
    xmlns:owl="http://www.w3.org/2002/07/owl#"
    xmlns:rqm_process="http://jazz.net/xmlns/prod/jazz/rqm/process/1.0/"
    xmlns:oslc_config="http://open-services.net/ns/config#"
    xmlns:oslc_cm="http://open-services.net/ns/cm#"
    xmlns:skos="http://www.w3.org/2004/02/skos/core#"
    xmlns:rqm_qm="http://jazz.net/ns/qm/rqm#"
    xmlns:oslc_qm="http://open-services.net/ns/qm#"
    xmlns:oslc_rm="http://open-services.net/ns/rm#"
    xmlns:jrs="http://jazz.net/ns/jrs#"
    xmlns:foaf="http://xmlns.com/foaf/0.1/"
    xmlns:oslc_auto="http://open-services.net/ns/auto#"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema#" > 
 <rdf:Description>
  <rdf:type rdf:resource="http://open-services.net/ns/qm#TestExecutionRecord"/>
  <oslc_qm:runsTestCase rdf:resource="{tc_u}"/>
  <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">{tcername}</dcterms:title>  
 </rdf:Description>
</rdf:RDF>
"""

    jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID',None)
    if not jsessionid:
        raise Exception( "JSESSIONID not found!" )

    response = c.execute_post_rdf_xml( tcer_factory_u, data=tcer_x, intent="Create the tcer for the test plan and the test case", headers={'Referer': 'https://jazz.ibm.com:9443/qm', 'X-Jazz-CSRF-Prevent': jsessionid }, remove_parameters=['oslc_config.context']  )
    print( f"{response=}" )
    tcer_u = response.headers['Location']
else:
    tcer_u = list(tcers.keys())[0]
    result = c.execute_get_rdf_xml( tcer_u, headers={ 'Accept': 'application/rdf+xml' } )
    
print( f"{tcer_u=}" )
#####################################################################################################
# now we have a ter, we can create a new test result

trquerybase = c.get_query_capability_uri("oslc_qm:TestResultQuery")
if not trquerybase:
    raise Exception( "Something serious went wrong" )

trs = c.execute_oslc_query(
    trquerybase,
    whereterms=[['oslc_qm:producedByTestExecutionRecord','=',f'<{tcer_u}>']],
    select=['*'],
    prefixes={rdfxml.RDF_DEFAULT_PREFIX["oslc_qm"]:'oslc_qm'} # note this is reversed - url to prefix
    )

print( f"Test results: {len(trs.items())}" )

writeresultstocsv( "04_testresults.csv", trs )

print( "Need to create a TR" )
tr_factory_u = c.get_factory_uri(resource_type='TestResult',context=None, return_shapes=False)
if not tr_factory_u:
    raise Exception( "Something serious went wrong" )
print( f"{tr_factory_u=}" )

#oslc_qm:producedByTestExecutionRecord

tr_x = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:rqm_auto="http://jazz.net/ns/auto/rqm#"
    xmlns:bp="http://open-services.net/ns/basicProfile#"
    xmlns:acp="http://jazz.net/ns/acp#"
    xmlns:cmx="http://open-services.net/ns/cm-x#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/"
    xmlns:rqm_lm="http://jazz.net/ns/qm/rqm/labmanagement#"
    xmlns:acc="http://open-services.net/ns/core/acc#"
    xmlns:process="http://jazz.net/ns/process#"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:oslc="http://open-services.net/ns/core#"
    xmlns:owl="http://www.w3.org/2002/07/owl#"
    xmlns:rqm_process="http://jazz.net/xmlns/prod/jazz/rqm/process/1.0/"
    xmlns:oslc_config="http://open-services.net/ns/config#"
    xmlns:oslc_cm="http://open-services.net/ns/cm#"
    xmlns:skos="http://www.w3.org/2004/02/skos/core#"
    xmlns:rqm_qm="http://jazz.net/ns/qm/rqm#"
    xmlns:oslc_qm="http://open-services.net/ns/qm#"
    xmlns:oslc_rm="http://open-services.net/ns/rm#"
    xmlns:jrs="http://jazz.net/ns/jrs#"
    xmlns:foaf="http://xmlns.com/foaf/0.1/"
    xmlns:oslc_auto="http://open-services.net/ns/auto#"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema#" > 
 <rdf:Description>
  <rdf:type rdf:resource="http://open-services.net/ns/qm#TestResult"/>
  <dcterms:contributor rdf:resource="https://jazz.ibm.com:9443/jts/users/tanuj"/>
  <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Allocate_Dividends_by_Percentage_Firefox_DB2_Tomcat_Windows_S12</dcterms:title>
  <oslc:shortId rdf:datatype="http://www.w3.org/2001/XMLSchema#int">17</oslc:shortId>
  <oslc_qm:producedByTestExecutionRecord rdf:resource="{tcer_u}"/>
  <oslc_qm:reportsOnTestCase rdf:resource="{tc_u}"/>
  <oslc_qm:reportsOnTestPlan rdf:resource="{tp_u}"/>
  <oslc_qm:status rdf:datatype="http://www.w3.org/2001/XMLSchema#string">com.ibm.rqm.execution.common.state.{verdict}</oslc_qm:status>
 </rdf:Description>
</rdf:RDF>
"""

jsessionid = httpops.getcookievalue( p.app.server._session.cookies, 'JSESSIONID',None)
if not jsessionid:
    raise Exception( "JSESSIONID not found!" )

response = c.execute_post_rdf_xml( tr_factory_u, data=tr_x, intent="Create the test result for ter", headers={'Referer': 'https://jazz.ibm.com:9443/qm', 'X-Jazz-CSRF-Prevent': jsessionid }, remove_parameters=['oslc_config.context']  )
print( f"{response=}" )
tr_u = response.headers['Location']
print( f"{tr_u=}" )



#####################################################################################################



#####################################################################################################


print( "Finished" )
