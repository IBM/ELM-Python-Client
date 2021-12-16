##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of using the elmclient package as a DOORS Next API to do reportable rest query
# exporting to CSV

# NOTE accessing the Reportable REST API may add a lot of load to your server so use with care!
# because it tries to retrieve *all* DOORS Next artifacts!
# code below only retrieves the first two pages!

# DN/DNG Reportable REST API https://jazz.net/wiki/bin/view/Main/DNGReportableRestAPI
#   DN/DNG FAQ on reportable rest https://jazz.net/wiki/bin/view/Main/RRCReportServiceFAQ
# ETM/RQM Reportable REST API https://jazz.net/wiki/bin/view/Main/RqmApi#Resources_and_their_Supported_Op
# EWM/RTC Reportable REST API https://jazz.net/wiki/bin/view/Main/ReportsRESTAPI

import csv
import logging

import lxml.etree as ET

import elmclient.server as elmserver
import elmclient.utils as utils

logger = logging.getLogger(__name__)

jazzhost = 'https://jazz.ibm.com:9443'
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

outfile = "dnrr.csv"

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

# A DN Reportable Rest query url (this also works in your browser)
rrurl = dnapp.reluri( dnapp.reportablerest_baseurl+"/resources/*" )
print( f"{rrurl=}" )
# limit to this number of pages to limit load on server
# the Reportable REST query "resources/*" used here, with no constraining project or module URI will attempt
# to retrieve all the artifacts in the default configuration of all projects
# that can be A LOT of data even on a very small deployment.
pagelimit = 3

# retrieve all the results - works for one or many pages
rows = []
allcolumns = []

print( f"Retrieving {pagelimit} pages from DOORS Next Reportable REST API" )

headings = []
rows=[]

while rrurl is not None and pagelimit > 0:
    # perform the Reportable Rest query
    # because query results are often updated as users work, this request is NOT cached even if caching is enabled
    print( f"Requesting page {rrurl}" )
    xmlresult = dnapp.execute_get_xml(rrurl, cacheable=False, remove_headers=['net.jazz.jfs.owning-context'])
    root = xmlresult.getroot()


    # go to each result (one row) below the root  -this will be a row of the results
    for res in list(xmlresult.getroot()):
        row = {}
        # def getcontentrow( node, thisrowdict, allcolumns, level, path, remove_ns=True ):
        row = utils.getcontentrow( res )
        for k in row.keys():
            if k not in headings:
                headings.append(k)                
        rows.append(row)
        
    # find the href for the next page of results
    rrurl = root.get("href",None)
    pagelimit -= 1

print( f"Writing to CSV {outfile}" )

with open( outfile, "w", newline='' ) as csvfile:
    csvwriter = csv.DictWriter(csvfile,fieldnames=sorted(headings))
    csvwriter.writeheader()
    for row in rows:
        csvwriter.writerow(row)

print( "Finished" )
