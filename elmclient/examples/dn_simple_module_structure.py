##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of accessing the module structure API

import csv
import logging

import lxml.etree as ET

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml

# setup logging - see levels in utils.py
#loglevel = "INFO,INFO"
loglevel = "OFF,OFF"
levels = [utils.loglevels.get(l,-1) for l in loglevel.split(",",1)]
if len(levels)<2:
    # assert file logging level if not provided
    levels.append(logging.DEBUG)
if -1 in levels:
    raise Exception( f'Logging level {loglevel} not valid - should be comma-separated one or two values from DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF' )
utils.setup_logging(consolelevel=levels[0],filelevel=levels[1])

logger = logging.getLogger(__name__)

VER=8
REPS = 200
CONTEXT="NONE"
CONTEXT="AS003"
CONTEXT="PROJ"

if VER==8:
    jazzhost = 'https://jazz.ibm.com:9443'
elif VER==3:
    jazzhost = 'https://testsvl1.fyre.ibm.com'
else:
    raise Exception( f"Unknown VER {VER}" )
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

proj = "rm_optin_p1"
comp = "rm_optin_p1_comp2"
conf = comp+" Initial Stream"
mod = "AMR Stakeholder Requirements Specification"

proj = "SGC Requirements"
comp = "SGC AMR"
conf =  "SGC AMR 1.1 Development"
mod = "AMR Stakeholder Requirements Specification"


outfile = "modstruct.csv"

# caching control
# 0=fully cached (but code below specifies queries aren't cached)
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2

# create our "server" which is how we connect to DOORS Next
# first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
elmserver.setupproxy(jazzhost,proxyport=8888)
theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

# create the RM application interface
dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )

# open the project
p = dnapp.find_project(proj)

# find the component
c = p.find_local_component(comp)

# select the configuration
config = c.get_local_config(conf)
c.set_local_config(config)

# find the module - using OSLC Query

# get the query capability base URL for requirements
qcbase = c.get_query_capability_uri("oslc_rm:Requirement")

# query for a title and for format=module
modules = c.execute_oslc_query(
    qcbase,
    whereterms=[['dcterms:title','=',f'"{mod}"'], ['rdm_types:ArtifactFormat','=','jazz_rm:Module']],
    select=['*'],
    prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rdm_types"]:'rdm_types',rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]:'jazz_rm'}
    )
    
if len(modules)==0:
    raise Exception( f"No module '{mod}' with that name in project {proj} component {comp} configuraition {conf}" )
elif len(modules)>1:
    for k,v in modules.items():
        print( f'{k} {v.get("dcterms:title","")}' )
    raise Exception( "More than one module with that name in project {proj} component {comp} configuraition {conf}" )

# we've found the module, it's the only entry in the modules dictionary, keyed by URL
themodule_u = list(modules.keys())[0]
print( f"{themodule_u=}" )

for n in range(REPS):
    # get the structure
    # works but verbose RDF - modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DoorsRP-Request-Type':'private','vvc.configuration': config,'net.jazz.jfs.owning-context': c.reluri(f"cm/component/{c.iid}")}, remove_headers=['OSLC-Core-Version'] )
    if VER==8:
    # works    modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DoorsRP-Request-Type':'private','vvc.configuration': config}, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
        print( f"iFix008!" )
        if CONTEXT=="NONE":
            modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client', 'DoorsRP-Request-Type':'private','vvc.configuration': config, 'Cache-Control':'no-cache'}, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
        elif CONTEXT=="PROJ":
            modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client', 'DoorsRP-Request-Type':'private','vvc.configuration': config, 'Cache-Control':'no-cache', 'net.jazz.jfs.owning-context': c.reluri(f"rm-projects/{p.iid}/components/{c.iid}")}, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
        elif CONTEXT=="AS003":
            modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client','DoorsRP-Request-Type':'private','vvc.configuration': config, 'net.jazz.jfs.owning-context': c.reluri(f"cm/component/{c.iid}") }, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
        else:
            burp
    elif VER==3:
        print( f"iFix003!" )
        if CONTEXT=="NONE":
            modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client', 'DoorsRP-Request-Type':'private','vvc.configuration': config, 'Cache-Control':'no-cache'}, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
        elif CONTEXT=="PROJ":
            modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client', 'DoorsRP-Request-Type':'private','vvc.configuration': config, 'Cache-Control':'no-cache', 'net.jazz.jfs.owning-context': c.reluri(f"rm-projects/{p.iid}/components/{c.iid}")}, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
        elif CONTEXT=="AS003":
            modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client','DoorsRP-Request-Type':'private','vvc.configuration': config, 'net.jazz.jfs.owning-context': c.reluri(f"cm/component/{c.iid}") }, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
        else:
            burp
# with net.jazz.        modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client','DoorsRP-Request-Type':'private','vvc.configuration': config, 'net.jazz.jfs.owning-context': c.reluri(f"cm/component/{c.iid}")}, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
#        modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DNT':'1','User-Agent':'Requisis Client','DoorsRP-Request-Type':'private','vvc.configuration': config, 'net.jazz.jfs.owning-context': c.reluri(f"cm/component/{c.iid}") }, remove_headers=['OSLC-Core-Version','Configuration-Context','Referer'], remove_parameters=['oslc_config.context'] )
    else:
        burp
#    burp
    #modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DoorsRP-Request-Type':'public 2.0','net.jazz.jfs.owning-context': c.reluri(f"rm-projects/{p.iid}/components/{c.iid}")}, remove_headers=['OSLC-Core-Version'])
#    modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = {'DoorsRP-Request-Type':'public 2.0','net.jazz.jfs.owning-context': c.reluri(f"cm/component/{c.iid}"),'vvc.configuration': config}, remove_headers=['OSLC-Core-Version','Configuration-Context','oslc_config.context'], remove_parameters=['oslc_config.context'])
    #modget = c.execute_get_rdf_xml(themodule_u, cacheable=False, headers = { 'net-jazz-jfs-owning-context': c.reluri(f"rm-projects/{p.iid}/components/{c.iid}")})

    print( f"{modget=}" )
    # report the structure

