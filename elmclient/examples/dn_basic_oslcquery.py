##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# a self-contained example for 7.0.2/7.0.2SR1 not using elmclient - does all low-level HTTP GETs to discover to find the project+component_config and then do OSLC Query
# and then does a very basic save to CSV

# NOTE the very primitive authentication in this code only works with Liberty form authentication, i.e. NOT with JAS!

# You see all the fun of picking stuff out of the RDF XML
# It's quite possible this could be simpler or at least more readable using rdflib

# CONTRAST this with dn_simple_oslcquery.py which uses elmclient

# this brutally minimal example has many limitations:
#  only works for a query which doesn't involve custom attributes/links - because otherwise you have to find the URIs of these - hardcoded to get all resuls with no oslc.where
#  only works for RM - it's hardcoded to rm
#  Only works for the first project/component/configuration name which matches (assumes names are unique)
#  ...

import logging

# this code uses lxml (rather than ElementTree) because of its xpath support for using text() 
import lxml.etree as ET
import csv
import requests
import urllib.parse
import socket
import codecs

from elmclient import httpops

# Disable the InsecureRequestWarning so we can quietly control SSL certificate validation
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

jazzhost = 'https://jazz.ibm.com:9443'
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

projectname = "rm_gc_p1"
componentname = "rm_gc_p1"
configname="rm_gc_p1 Initial Stream"

projectname = "SGC Requirements"
componentname = "SGC AMR"
configname="test1"

query = 'dcterms:modified>"" and dcterms:modified<""'
select= "*"
prefix = 'dcterms=<>'

outfile = "dn_basicoslcqueryresults.csv"

prefixes = {
    'dcterms':          'http://purl.org/dc/terms/',
    'oslc':             'http://open-services.net/ns/core#',
    'oslc_config':      'http://open-services.net/ns/config#',
    'rm_config':        'http://jazz.net/ns/rm/dng/config#',
    'oslc_rm':          'http://open-services.net/ns/rm#',
    'rdf':              'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs':             'http://www.w3.org/2000/01/rdf-schema#',
}

use_proxy = True
proxydict = None
proxyport = 8888

#######################################################################################################
# utility functions to configure a proxy so you can see communication with the server in a https
# proxy such as Telerik Fiddler Classic configured as a MITM https proxy

# utility to see if a port is active listening for connections
def tcp_can_connect_to_url(host, port, timeout=5):
    # create an INET, STREAMing socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # now connect to the web server on port
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False

def setupproxy(url,proxyportT):
    # If a proxy is running on proxyport, setup proxydict so requests uses the proxy
    proxydict = None
    if proxyport!=0:
        # test if proxy is running
        if tcp_can_connect_to_url('127.0.0.1', proxyport, timeout=2.0):
            # proxy e.g. Telerik Fiddler Classic on port 8888 is running so setup proxy
            urlparts = urllib.parse.urlsplit(url)
            if urlparts.port:
                proxyurl = urlparts.scheme + "://" + urlparts.netloc[:urlparts.netloc.find(':')]
            else:
                proxyurl = urlparts.scheme + "://" + urlparts.netloc
            # insert the proxy dictionary
            proxydict = {
                            'https':'http://127.0.0.1:'+str(proxyport) # NOTE the proxy URL is "http:" - Fiddler doesn't provide a https proxy by default so don't change this!
                            ,'http':'http://127.0.0.1:'+str(proxyport)
                        }
            logger.info( f'Setting proxy to {proxydict}' )
    return proxydict
        
# find the encoding of a response
def find_encoding(response, encoding):
    if isinstance(encoding, str):
        encoding = encoding
    elif encoding is None and (
        isinstance(response, requests.Response) or isinstance(response, requests.models.Response)):
        encoding = response.encoding
    elif encoding is None:
        pass
    else:
        raise Exception('Unknown encoding type [%s]' % encoding)
    if encoding is None:
        encoding = 'utf-8'  # default
    if "7bit" == encoding:
        encoding = 'us-ascii'
    return encoding



# encode to binary for non-XML strings
def to_binary(text, encoding=None, errors='strict'):
    if isinstance(text, bytes) or isinstance(text, bytearray):
        return text
    encoding = find_encoding(None, encoding)
    if encoding is None:
        result = codecs.encode(text, errors=errors)
    else:
        result = codecs.encode(text, encoding=encoding, errors=errors)
    return result        

# this is a bit primitive but works well enough for now
def getconfigtype( configuri ):
    if '/baseline/' in configuri:   return "Baseline" 
    if '/stream/' in configuri:     return "Stream"
    if '/changeset/' in configuri:  return "Changeset"
        
#######################################################################################################
#
# low-level version NOT using elmclient AT ALL - everything including authentication for basic Liberty form auth is done here
#
# NOTE THIS ONLY WORKS FOR FORM-BASED login, i.e. doesn't work with JAS!
#

# generic HTTP GET with login if auth is needed
def get_with_optional_login( sess, url, *, params=None, headers=None, username="", password="", verify=False):
    '''
    This function tries to perform a GET on url - and checks the result,
    If authentication is needed it does this using provided username/password, and then returns the data
    ONLY WORKS LIBERTY FOR FORM AUTHENTICATION!
    '''
    params = params or {}
    headers = headers or {}

    retry_needed = False
    
    # execute the request - NOTE verify (of SSL cert) is set to False because test server using self-signed cert
    response = sess.get(url,headers=headers, params=params, verify=verify )
    # could check here for 401 response from OIDC/JAS    
    response.raise_for_status()

    # The response is "good" (i.e. 200) but if auth is needed there is a specific header+value
    # (in which case the response is not the data requested, but the data will be returned by authenticating)
    if response.headers.get('X-com-ibm-team-repository-web-auth-msg',"") == 'authrequired':
        print("Authentication required")
        # get the auth path from the JazzFormAuth cookie path
        cookiedetails = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path} for c in sess.cookies if c.name=='JazzFormAuth'][0]
        authpath = cookiedetails['path']
        # unparse to get the host then construct the auth url
        parts = urllib.parse.urlparse( url )
        host = f"{parts.scheme}://{parts.netloc}"
        auth_url = f"{host}{authpath}/j_security_check?j_username={username}&j_password={password}"
        
        response = sess.get(auth_url)
        response.raise_for_status()
        # check the auth was successful - is there a JAZZ_AUTH_TOKEN?
        if 'JAZZ_AUTH_TOKEN' not in response.cookies:
            raise Exception ( f"Authentication failed using {username=} {password=}!" )
        print("Auth successful - redoing the GET now authenticated")
        retry_needed = True
        
    if retry_needed:
        # this is usually a re-request because the authentication redirection will have finished with a GET on the original URL
        # BUT this is guaranteed to have correct headers!
        response = sess.get(url,headers=headers, params=params, verify=verify )
        response.raise_for_status()
    return response

# Create the session used for all requests to the server
# BECAUSE it gets the authentication cookie and provides it on later requests
thesession = requests.session()

if use_proxy:
    proxydict = setupproxy( jazzhost, proxyport )
    if proxydict:
        thesession.proxies.update( proxydict )
        
headers = { 'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml' }
params = {}

# get rootsservices
response = get_with_optional_login( thesession, urllib.parse.urljoin(jazzhost,f"/{rmcontext}/rootservices"),headers=headers, username=username,password=password, verify=False )
rootservices_x = ET.fromstring(response.content)

# refer to discovery example here https://jazz.net/forum/questions/266334/dng-oslcfetch-components-from-project-area
cmsp_x = rootservices_x.find( './/oslc_config:cmServiceProviders',prefixes )
cmsp_u = cmsp_x.get(f"{{{prefixes['rdf']}}}resource")

print( f"Config Managment service provider URL is {cmsp_u}" )

# get the compponents entry point
response = get_with_optional_login( thesession, cmsp_u,headers=headers, username=username,password=password)
candc_x = ET.fromstring( response.content )

comps_x = candc_x.find( './/oslc:ServiceProvider',prefixes )
comps_u = comps_x.get( f"{{{prefixes['rdf']}}}about" )

print( f"Components Service Provider URL is {comps_u=}" )

# get the projects
response = get_with_optional_login( thesession, comps_u,headers=headers, username=username,password=password)
projs_x = ET.fromstring( response.content )

# find the project
project_x = projs_x.xpath( './/oslc:CreationFactory/oslc:resourceType[@rdf:resource="http://open-services.net/ns/config#Component"]/../dcterms:title[text()="'+projectname+'"]/../oslc:creation',namespaces=prefixes )
project_u = project_x[0].get(f"{{{prefixes['rdf']}}}resource")

print( f"The project URL is {project_u}" )

# find the component
response = get_with_optional_login( thesession, project_u,headers=headers, username=username,password=password)
thecomps_x = ET.fromstring( response.content )
thecomp_x = thecomps_x.xpath( f'.//rdf:Description/dcterms:title[text()="{componentname}"]/..', namespaces=prefixes )
thecomp_u = thecomp_x[0].get(f"{{{prefixes['rdf']}}}about")

print( f"Component URL is {thecomp_u}" )

# find the configuration list pointer
response = get_with_optional_login( thesession, thecomp_u,headers=headers, username=username,password=password)
proj_services_x = ET.fromstring( response.content )
comp_configs_x = proj_services_x.find( './/oslc_config:configurations', prefixes )
comp_configs_u = comp_configs_x.get(f"{{{prefixes['rdf']}}}resource")

print( f"Streams and Baselines URL is {comp_configs_u}" )

# search for the config we want
response = get_with_optional_login( thesession, comp_configs_u,headers=headers, username=username,password=password)
aconf_x = ET.fromstring( response.content )

# search for the config name we want by going through all the members in all the configurations, and if they have rm_config:changesets then checking those too
# finding the first stream/baseline that matches the name - duplicated names won't be noticed/used!
thisconf_u = None

# this list will be extended as now configs are found - in particular changesets are added to it.
# entries in this list area all rdfs:member - if it has a rdf:about then it's retrieved otherwise it's checked for dcterms:title
confstocheck = aconf_x.findall( './/rdfs:member', prefixes )
while len(confstocheck)>0:
    aconf_x = confstocheck.pop() #take config off the front
    aconf_u = aconf_x.get( f"{{{prefixes['rdf']}}}resource" )
    if aconf_u is not None:
        # retrieve the definition
        response = get_with_optional_login( thesession, aconf_u,headers=headers, username=username,password=password)
        aconf_x = ET.fromstring( response.content )
#    thisconf_x = aconf_x.xpath( f".//oslc_config:Configuration/dcterms:title[text()='{configname}']/..", namespaces=prefixes ) or aconf_x.xpath( f".//oslc_config:Stream/dcterms:title[text()='{configname}']/..", namespaces=prefixes ) or aconf_x.xpath( f".//oslc_config:Baseline/dcterms:title[text()='{configname}']/..", namespaces=prefixes )
    thisconf_x = aconf_x.find( f".//oslc_config:Configuration", prefixes )
    if thisconf_x is None:
        thisconf_x = aconf_x.find( f".//oslc_config:Stream", prefixes )
    if thisconf_x is None:
        thisconf_x = aconf_x.find( f".//oslc_config:Baseline", prefixes )
    if thisconf_x is None:
        thisconf_x = aconf_x.find( f".//oslc_config:ChangeSet", prefixes )
#    print( ET.tostring( thisconf_x ) )

    # check for changesets and if found retrieve them add to confstocheck
    changesets_x = thisconf_x.find( ".//rm_config:changesets", prefixes )
    if changesets_x is not None:
        # retrieve the CS details
        cs_u = changesets_x.get( f"{{{prefixes['rdf']}}}resource" )
        response = get_with_optional_login( thesession, cs_u, headers=headers, username=username,password=password)
        thecs_x =  ET.fromstring( response.content )
        confstocheck.extend( thecs_x.findall( './/rdfs:member', prefixes ) )
        #for acs_x in thecs_x.findall( ".//
    if thisconf_x is not None:
        title = thisconf_x.find( ".//dcterms:title",prefixes ).text
        if title == configname:
            # use the tag to determine the name for the configuration type
            thisconf_u = thisconf_x.get( f"{{{prefixes['rdf']}}}about" )
            configtype = getconfigtype( thisconf_u )
            break
        
if thisconf_u is None:
    raise Exception( f"Config {configname} not found" )

print( f"Found configuration {thisconf_u} which is a {configtype}" )    
thisconf_x = aconf_x

# setup headers/params for the rest of the operations - these are all config-specific
params[httpops.chooseconfigheader(thisconf_u)] = thisconf_u
headers[ 'Configuration.context'] = thisconf_u

# retrieve the services.xml for the config
services_x = aconf_x.find( './/oslc:serviceProvider', prefixes )
services_u = services_x.get( f"{{{prefixes['rdf']}}}resource" )
response = get_with_optional_login( thesession, services_u,headers=headers, username=username,password=password)
service_x = ET.fromstring( response.content )
# find the query capability for oslc_rm:Requirement
req_query_x = service_x.find( './/oslc:QueryCapability/oslc:resourceType[@rdf:resource="http://open-services.net/ns/rm#Requirement"]/../oslc:queryBase', prefixes )
req_query_base_u = req_query_x.get( f"{{{prefixes['rdf']}}}resource" )
print( f"OSLC Query Base URL for requirements is {req_query_base_u}" )
# build the query URL
# unparse the query capability URL to get any existing parameters, to which we will add the params for this query
url_parts = list(urllib.parse.urlparse(req_query_base_u))
logger.info( f"{url_parts=}" )

# start the parameters from what's in the base url
query_params = dict(urllib.parse.parse_qsl(url_parts[4]))

# override with the query parameters
query_params.update(dict(((k, to_binary(v)) for k, v in list(params.items()) if v)))

# set the select to return all attribute values
query_params['oslc.select'] = select

# assert a relatively small page size so the repsonse isn't enormous/overload the server
query_params['oslc.pageSize'] = 100

url_parts[4] = ""
url_parts[5] = ""
# reconstruct just the base scheme:hostname
query_url = urllib.parse.urlunparse(url_parts)

results = []
print( "Retrieving first page of results" )
# if you wanted to get following pages look for <oslc:nextPage rdf:respource='...'> and append them to results
# BEWARE overloading your server with queries - this may impact on users!
while True:
    # get the query results (if paged, then only get the first page)
    response = thesession.get(query_url,params=query_params, headers=headers )

    response_x = ET.fromstring( response.content )
    results.extend( response_x.findall( ".//rdfs:member/oslc_rm:Requirement", prefixes ) )

    nextpage_x = response_x.find( ".//oslc:nextPage" , prefixes )
    if nextpage_x is None:
        break
    query_url = nextpage_x.get( f"{{{prefixes['rdf']}}}resource" )
    print( f"Retrieving next page" )
    # empty the additional params because the nextpage URL provides all needed query parameters
    params = {}


print( f"There are {len(results)} results" )

# process the results
resultrows = []
allcolumns = {}
# process each member
for entry in results:
    resultrows. append({'uri':entry.get( f"{{{prefixes['rdf']}}}about" )})
    allcolumns['uri'] = True
    for child in entry.getchildren():
        allcolumns[child.tag] = True
        resultrows[-1][child.tag] = child.text or child.get( f"{{{prefixes['rdf']}}}resource" )
#    print( f"{resultrows[-1]=}" )
    
# save the results to CSV
print( f"Writing to CSV {outfile}" )

with open( outfile, "w", newline='' ) as csvfile:
    csvwriter = csv.DictWriter(csvfile,fieldnames=sorted(allcolumns.keys()))
    csvwriter.writeheader()
    for row in resultrows:
        csvwriter.writerow(row)

