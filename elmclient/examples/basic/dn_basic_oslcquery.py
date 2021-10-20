##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of:
# 1) not using elmclient - does all low-level HTTP queries to find the project+component_config and then do OSLC Query
# AND 2) using elmclient to do the same query
# exporting to CSV

# the minimal example has many limitations:
#  only easy for a query which doesn't involve custom attributes/links
#  only gets first page
#  only works for RM
#  ...

import logging

import lxml.etree as ET
import csv

logger = logging.getLogger(__name__)

jazzhost = 'https://jazz.ibm.com:9443'
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

projectname = "rm_gc_p1"
componentname = "rm_gc_p1"
configname="rm_gc_p1 Initial Stream"

query = 'dcterms:modified>"" and dcterms:modified<""'
select= "*"
prefix = 'dcterms=<>'

outfile = "dnoq.csv"

prefixes = {
'oslc_rm':
'oslc_config':
'rdf':
'dcterms':
}

#######################################################################################################
#
# low-level version
#

# generic HTTP GET with login if auth is needed
def get_with_optional_login(s,url, *, params=None, headers=None, username="", password="", verify=False):
    '''
    This function tries to perform a GET on url - and checks the result,
    If authentication is needed it does this using provided username/password, and then returns the data
    ONLY WORKS FOR FORM AUTHENTICATION!
    '''
    params = params or {}
    headers = headers or {}
    
    # execute the request - NOTE verify (of SSL cert) is set to False because test server using self-signed cert
    fullurl = 
    
    response = s.get(url,headers=headers, params=params, verify=verify )
    response.raise_for_status()

    # The response is "good" (i.e. 200) but if auth is needed there is a specific header+value
    # (in which case the response is not the data requested, but the data will be returned by authenticating)
    if response.headers.get('X-com-ibm-team-repository-web-auth-msg',"") == 'authrequired':
        print("Auth required")
        # unparse to get the auth URL

        auth_url = f"{host}/jts/j_security_check?j_username={username}&j_password={password}"
        
        response = s.get(auth_url)
        response.raise_for_status()
        # check the auth was successful - is there a JAZZ_AUTH_TOKEN?
        if 'JAZZ_AUTH_TOKEN' not in response.cookies:
            raise Exception ( f"Authentication failed using {username=} {password=}!" )
        print("Auth successful")
    elif # OIDC
    
    elif # FORM prompt (ENI)
    
    else:
    
    return response

# Create the session used for all requests to the server
s = requests.session()

headers = { 'OSLC-Core-Version': '2.0;, 'Accept': 'application/rdf+xml' }

# get rootsservices
response = get_with_optional_login( urllib.urljoin(jazzhost,f"/{rmcontext}/rootservices'),headers=headers, username=username,password=password)
rootservices_x = lxml.fromstring(response.content)

# refer to discovery example here https://jazz.net/forum/questions/266334/dng-oslcfetch-components-from-project-area
cmsp_x = lxml.find( rootservices_x, './/oslc_config:cmServiceProviders' )
cmsp_u = cmsp_x.get('rdf:resource')

# get the compponents entry point
response = get_with_optional_login( cmsp_u,headers=headers, username=username,password=password)
candc_x = lxml.fromstring( response.content )

comps_x = lxml.find( candc_x,'.//oslc:ServiceProvider )
comps_u = comps_x.get( 'rdf:about' )

# get the projects
response = get_with_optional_login( comps_u,headers=headers, username=username,password=password)
projs_x = lxml.fromstring( response.content )

# find the project
project_x = lxml,.find( projs_x, f'.//oslc:CreationFactory/oslc:resourceType[@rdf:resource="http://open-services.net/ns/config#Component"]/../dcterms:title=[text()='{projectname}']/../oslc:creation' )
project_u = projectx.get['rdf:resource']

# find the component
response = get_with_optional_login( project_u,headers=headers, username=username,password=password)
thecomps_x = lxml.fromstring( response.content )
thecomp_x = lxml.find( thecomps_x, f'.//rdf:Description/dcterms:title[text()="{componentname}"]/..' )
thecomp_u = thecomp_x.get('rdf:about')

# find the configuration list pointer
response = get_with_optional_login( thecomp_u,headers=headers, username=username,password=password)
proj_services_x = lxml.fromstring( response.content )
comp_configs_u = lxml.find( proj_services_x, './/oslc_config:configurations' )

# search for the config we want
response = get_with_optional_login( comp_configs_u,headers=headers, username=username,password=password)
aconf_x = lxml.fromstring( response.content )

# search for the config name we want
thisconf_u
for aconf_x in lxml.findall( aconf_x, './/rdfs:member' )
    aconf_u = aconf_x.get( 'rdf;resource' )
    response = get_with_optional_login( aconf_u,headers=headers, username=username,password=password)
    aconf_x = lxml.fromstring( response.content )
    if ( thisconf_x := lxml.find( aconf_x, f'.//oslc_config:Configuration/dcterms:title[text()='{configname}']/..' ) ):
        thisconf_u = thisconf_x.get('rdf:resource')
        break
        
if thisconf_u is None:
    raise Exception( f"Config {configname} not found" )
    
thisconf_x = aconf_x

# setup headers/params for the rest of the operations  -these are all config-specific
params['oslc_config.context'] = thisconf_u
headers[ 'Configuration.context'] = thisconf_u

# retrieve the services.xml for the config
aservices_x = lxml.find( aconf_x, './/oslc:serviceProvider' )
services_u = services_x.get('rdf;resource')

response = get_with_optional_login( services_u,headers=headers, username=username,password=password)
service_x = lxml.fromstring( response.content )

# find the query capability for oslc_rm:Requirement
req_query_x = lxml.find( service_x,'.//oslc:QueryCapability/oslc:resourceType[@rdf:resource="http://open-services.net/ns/rm#Requirement"]/../oslc:queryBase' )
req_query_base_u = req_query.get( 'rdf:resource' )

# build the query URL
# unparse the query capability URL to get any existing parameters, to which we will add the params for this query
url_parts = list(urllib.parse.urlparse(req_query_base_u))
logger.info( f"{url_parts=}" )

# start the parameters from what's in the base url
query_params = dict(urllib.parse.parse_qsl(url_parts[4]))
# override with the query parameters
query_params.update(dict(((k, server.to_binary(v)) for k, v in list(params.items()) if v)))
url_parts[4] = ""
url_parts[5] = ""
# reconstruct just the base scheme:hostname
query_url = urllib.parse.urlunparse(url_parts)
logger.info( f"The full OSLC Query URL is {query_url}" )


# get the query results
response = s.get(query_url,params=query_params, headers=headers )
response_x = lxml.fromstring( response.content )

# process the XML
resultrows = []


# save the results to CSV
print( f"Writing to CSV {outfile}" )

with open( outfile, "w", newline='' ) as csvfile:
    csvwriter = csv.DictWriter(csvfile,fieldnames=sorted(allcolumns))
    csvwriter.writeheader()
    for row in resultrows:
        csvwriter.writerow(row)



#######################################################################################################
#
# elmclient Version
#

import elmclient.server as elmserver
import elmclient.utils as utils



# caching control
# 0=fully cached (but code below specifies queries aren't cached)
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 0

# create our "server" which is how we connect to DOORS Next
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

# create the RM application interface
dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )


p = dnapp.find_project()
c = dnapp.find_component()
local_config_u = p.find_local_config()
c.set_local_config(local_config_u)
headers = {}

qcbase = c.find_query_capability("oslc_rm:Requirement")

queryurl = .urljoin(qcbase,params)

# now do the direct OSLC query (if the query needed to refer to a specific attribute or enumeration name this would be an awful lot more complicated)
# ONLY get the first page!
response_x = c.app.server.execute_xml_get(queryurl,headers=headers)

# results are in RDF-XML - decode them
resultrows = []

...

print( f"Writing to CSV {outfile}" )

with open( outfile, "w", newline='' ) as csvfile:
    csvwriter = csv.DictWriter(csvfile,fieldnames=sorted(allcolumns))
    csvwriter.writeheader()
    for row in resultrows:
        csvwriter.writerow(row)

print( "Finished" )
