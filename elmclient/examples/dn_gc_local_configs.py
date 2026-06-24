##
## © Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#######################################################################################################
#
# demonstrate finding the DN local contributions to a global configuration (bt name of the GC)
# Uses GCM OSLC Query for a global configuration to get the GC URL
# Then RM's flatListOfContributionsForGcHierarchy API to get the contributions
#

import sys
import os
import csv
import logging
import urllib.parse

import elmclient
import elmclient._rm
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

utils.log_commandline( os.path.basename(sys.argv[0]) )

jazzhost = 'https://jazz.ibm.com:9443'
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'
gccontext  = 'gc'

gcproj=None # this will beed to be set if one of the specified GC names matches more than one GC config 

gcnames="gccomp Initial Development,SGC Production stream"

#outfile = "dn_gc_local_configs_results.csv"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2

# create our "server" which is how we connect to DOORS Next
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring=f"rm:{rmcontext}", cachingcontrol=caching)

# create the RM application interface
dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )

# create the GC application interface
gcapp = theserver.find_app( f"gc:{gccontext}", ok_to_create=True )

# GC query base for configurations
qcbase = gcapp.get_query_capability_uri("oslc_config:Configuration")

allgcs=[]

# query
for gcname in gcnames.split(","):
    results = gcapp.execute_oslc_query(
        qcbase,
        whereterms=[['dcterms:title','=',f'"{gcname}"']],
        select=['*'],
    #    prefixes={rdfxml.RDF_DEFAULT_PREFIX["process"]:'process'} # note this is reversed - url to prefix - and dcterms mustn't be provided!
        )
    print( f"{results=}" )
    if not results:
        raise Exception( "GC config {gcname} not found!" )
    for result in results:
        print( f"{result=}" )

        allgcs.append(result)

print( f"\n{allgcs=}\n" )

alllocalcontribs=[]
for gcuri in allgcs:
#    print( f"\n{gcuri=}" )
    localconfs = dnapp.flatListOfContributionsForGcHierarchy( gcuri, returnCompAndPA=True )
#    print( f"{localconfs=}" )
    for contribURI,compURI,paURI in localconfs:
        print( f"{contribURI=} {compURI=} {paURI=}" )
        proj = dnapp.find_project( paURI )
        comp = proj.find_local_component( compURI )
        conf = comp.get_local_config( contribURI )
#        print( f"{confname=} {compnane=} {paname=}" )
        print( f"{conf=} {comp.name=} {proj.name=}" )
    alllocalcontribs.extend( localconfs )

print( f"{alllocalcontribs=}" )
