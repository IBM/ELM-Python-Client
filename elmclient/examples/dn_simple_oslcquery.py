##
## © Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# elmclient simple oslc query for hardcoded values
#

import sys
import os
import csv
import logging
import urllib.parse

import elmclient.server as elmserver
import elmclient.utils as utils

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
rmcontext  = 'rm'

# the project+component+config that will be queried
proj = "rm_optin_p1"
comp = proj
conf =  f"{comp} Initial Stream"

outfile = "dn_simple_oslcquery_results.csv"


# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 0

# create our "server" which is how we connect to DOORS Next
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring=f"rm:{rmcontext}", cachingcontrol=caching)

# create the RM application interface
dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )
p = dnapp.find_project( proj )
c = p.find_local_component( comp )
local_config_u = c.get_local_config( conf )
c.set_local_config(local_config_u)

qcbase = c.get_query_capability_uri("oslc_rm:Requirement")

# query
results = c.execute_oslc_query(
    qcbase,
#    whereterms=[['dcterms:identifier','=',f'"{sys.argv[1]}"']],
    select=['*'],
#    prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
    )

# want to find all the headers
allcolumns = {}
for uri,row in results.items():
    for k in row.keys():
        allcolumns[k]=True

def safeint(s):
    try:
        return int(s.get('dcterms:identifier',0))
    except:
        pass
    return 0
    
# sort by dcterms.identifier
uris = sorted(results, key=lambda s: safeint(results[s]) )

print( f"Writing to CSV {outfile}" )

with open( outfile, "w", newline='' ) as csvfile:
    csvwriter = csv.DictWriter(csvfile,fieldnames=sorted(allcolumns.keys()))
    csvwriter.writeheader()
    for uri in uris:
        row = results[uri]
        csvwriter.writerow(row)

print( "Finished" )
