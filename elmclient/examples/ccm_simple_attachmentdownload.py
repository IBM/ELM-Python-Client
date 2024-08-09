##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


# example of using the elmclient package to download a work item attachment

import logging

import lxml.etree as ET

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml

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

jazzhost = 'https://jazz.ibm.com:9443'
username = 'ibm'
password = 'ibm'

jtscontext = 'jts' # specifies /jts change if your jts is on a different context root
ccmcontext  = 'ccm' # specifies /ccm change if your ccm is on a different context root

workitemid=38

# caching control
# 0=fully cached (but code below specifies queries aren't cached)
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 0

# create our "server" which is how we connect to DOORS Next
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

# create the CMM application interface
ccmapp = theserver.find_app( f"ccm:{ccmcontext}", ok_to_create=True )

wiurl = ccmapp.reluri(f'resource/itemName/com.ibm.team.workitem.WorkItem/{workitemid}')

print( f"Retrieving wi details" )

xmlresult = ccmapp.server.execute_get_xml(wiurl, cacheable=False, headers={'OSLC-Core-Version': '2.0'}, intent="Retrieve work item content (including attachment details)" )

print( f"{xmlresult=}" )

for attachment in rdfxml.xml_find_elements( xmlresult, './/rtc_cm:com.ibm.team.workitem.linktype.attachment.attachment' ):
    # find the attachment URI
    # <rtc_cm:com.ibm.team.workitem.linktype.attachment.attachment oslc_cm:collref="https://jazz.ibm.com:9443/ccm/oslc/workitems/_SPJOV0B2EeuDvqpPB-fV1g/rtc_cm:com.ibm.team.workitem.linktype.attachment.attachment"/>
    attachment_u = rdfxml.xmlrdf_get_resource_uri( attachment )
    print( f"{attachment_u=}" )

    # get the attachment metadata
    attachment_info = ccmapp.server.execute_get_xml(attachment_u, cacheable=False, headers={'OSLC-Core-Version': '2.0'}, intent="Retrieve attachment details (points to attachment content)" )

    # find the download link
    # <rtc_cm:content rdf:resource="https://jazz.ibm.com:9443/ccm/resource/content/_IZCsIRuREeyjc_YwJfTLJA"/>
    download_u = rdfxml.xmlrdf_get_resource_uri( attachment_info, './/rtc_cm:content' )
    print( f"{download_u=}" )
    filename = rdfxml.xmlrdf_get_resource_text( attachment_info, './/dcterms:title' )
    print( f"{filename=}" )
    # download it, using Referer set to the URI (addresses a security measure built-in to ccm)
    attachment_binary = ccmapp.server.execute_get_binary(download_u, cacheable=False, headers={'OSLC-Core-Version': '2.0', 'Referer':download_u}, intent="Retrieve attachement content (binary)" )
    print( f"{len(attachment_binary.content)}" )
    # open( filename,"wb" ).write( attachment_binary )

print( "Finished" )
