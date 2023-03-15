##
## © Copyright 2023- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# RM-specific example of creating/removing a link, in this case between two core artifacts in the same project/component/configuration (hardcoded for simplicity)
# If the link is already present it is removed, otherwise it is created
# Link constraints are NOT handled, so if any exist and the new link conflicts with these there will be an error when trying to create the link!
# if your configuration requires changesets you'll have to set the hardcoded configuration to the changeset name and changes will be in that changeset.

# Provide on the commandline the id of the From artifact, the name of the link type (encloised with " if it contains space), and the id of the To artifact
# these must exist in the hardcoded project/config (i.e. within one component)

# NOTE this example isn't as simple as some of the others because of the added complexity of handling RDF XML - it uses the rdfxml library from elemclient

# Steps are:
# Find the link type
# Use OSLC Query to find the FROM artifact - filter the results to determine the core artifact
# Use OSLC Query again, to find the TO artifact - filter the results to determine the core artifact
# GET the from artifact
# check for the link already existing:
#   if present, remove it
#   if not present, add it

# Tested using 7.0.2SR1 (only) - don't know a reason it shouldn't work for earlier versions :-)

# In DN (and ELM) there are what I'd describe as threee types of link type;
# * OSLC links - these always have predefined source and target applications, and predefined URIs - see https://www.ibm.com/docs/en/elm/7.0.2?topic=services-links-across-oslc-domains
# * System-deined link types - e.g. Mitigates, Elaborates, these always have predefined URIs and are present and available in every DN project/component
# * Custom link types - these are *always* within an application such as DN or EWM - if to be used between components must be defined in both components, AND you MUST you define the RDF URI with the type definition in each component

# Link types available are discovered when loading the type system from a component+configuration; all the available link types are referenced on each Artifact Type
# this is handled in the rm typesystem loading code which now understands link typesT# 
# Discovery of link types for other applications hasn't been implemented (yet)

import logging
import os.path
import sys
import time

import lxml.etree as ET

import elmclient.server as elmserver
import elmclient.utils as utils
import elmclient.rdfxml as rdfxml


####################################################################################
# for information only
# These OSLC link types are never present as outgoing link on a DN resource!
OSLC_LINK_TYPES = [
    [ "am",  "Derives Architecture Element", "Derives From Architecture Element / Derives Architecture Element",   "http://jazz.net/ns/dm/linktypes#derives",      "(System-defined) Captures the relationship between a Requirements Management artifact and an Architecture Management item that represents a model of the requirement artifact (e.g., a UML Use Case in IBM Engineering Systems Design Rhapsody - Model Manager). Links of this type appear as 'Derives From' in Architecture Management."         ],
    [ "am",  "Refines Architecture Element", "Refines Architecture Element / Refined By Architecture Element",     "http://jazz.net/ns/dm/linktypes#refine",       "(System-defined) The target is a refinement of the source. (e.g. a use case scenario might be a refinement of a textual requirement that describes the interaction)."                                                                                                                                                                                ],
    [ "am",  "Satisfy Architecture Element", "Satisfies Architecture Element / Satisfied By Architecture Element", "http://jazz.net/ns/dm/linktypes#satisfy",      "(System-defined) The model element satisfies the requirement (e.g. The use case satisfies a functional requirement)."                                                                                                                                                                                                                           ],
    [ "am",  "Trace Architecture Element",   "Trace Architecture Element / Traced By Architecture Element",        "http://jazz.net/ns/dm/linktypes#trace",        "(System-defined) The model element has a trace to the requirement (e.g. an attribute or its value are traced to a requirement)."                                                                                                                                                                                                                           ],
    [ "ccm", "Affected By",                  "Affects / Affected By",                                              "http://open-services.net/ns/rm#affectedBy",    "(System-defined) Captures the relationship between a Requirements Management artifact and a Change Management item that has an effect on the implementation of the requirement artifact (e.g., a Defect in IBM Engineering Workflow Management). Links of this type appear as 'Affects' in Change Management."                                                                                              ],
    [ "ccm", "Implemented By",               "Implements / Implemented By",                                        "http://open-services.net/ns/rm#implementedBy", "(System-defined) Captures the relationship between a Requirements Management artifact and a Change Management item that describes the implementation of the requirement artifact (e.g., a Story in IBM Engineering Workflow Management). Links of this type appear as 'Implements' in Change Management."                                                                                       ],
    [ "ccm", "Tracked By",                   "Tracks / Tracked By",                                                "http://open-services.net/ns/rm#trackedBy",     "(System-defined) Captures the relationship between a Requirements Management artifact and a Change Management item that tracks the implementation of the requirement artifact (e.g., a Task in IBM Engineering Workflow Management). Links of this type appear as 'Tracks' in Change Management."                                                                                                               ],
    [ "qm",  "Validated By",                 "Validates / Validated By",                                           "http://open-services.net/ns/rm#validatedBy",   "(System-defined) Captures the relationship between a Requirements Management artifact and a Quality Management item that validates the implementation of the requirement artifact (e.g. a Test Case in IBM Engineering Test Management). Links of this type appear as 'Validates' in Quality Management."                                                                                              ],
]

# for information only
# this lists system-defined link types in DOORS Next
# the actual link types present in a project/component (i.e. including these) are discovered when loading the type system 
SYSTEM_DEFINED_RM_LINK_TYPES = [
    [ "Artifact Term Reference", "References Term / Term Referenced From", "http://www.ibm.com/xmlns/rdm/types/ArtifactTermReferenceLink", "(System-defined) Captures glossary-based relationships between part of a Requirements Management artifact (e.g., a word or phrase) and a Glossary Term. This type of link is created when performing Term-based operations for Text artifacts, for example, the 'Create New Term' operation."                                                               ],
    [ "Decomposition",           "Child Of / Parent Of",                   "http://www.ibm.com/xmlns/rdm/types/Decomposition",             "(System-defined) Captures part-whole relationships between Requirements Management artifacts. These types of links are typically used to represent artifact hierarchies."                                                                                                                                                                                                                           ],
    [ "Elaborated By",           "Elaborated By / Elaborates",             "http://open-services.net/ns/rm#elaboratedBy",                  "(System-defined) Expresses an elaboration relationship between entities, where the subject entity is elaborated by the object entity. For example, a requirement is elaborated by a model element."                                                                                                                                                                                                ],
    [ "Elaborates",              "Elaborates / Elaborated By",             "http://open-services.net/ns/rm#elaborates",                    "(System-defined) Expresses an elaboration relationship between entities, where the subject entity elaborates the object entity. For example, a requirement elaborates a model element."                                                                                                                                                                                                                 ],
    [ "Embeds",                  "Embeds / Embedded In",                   "http://www.ibm.com/xmlns/rdm/types/Embedding",                 "(System-defined) Tracks a containment relationship between Requirements Management artifacts. These types of relationships occur when performing operations such as 'Insert Artifact' and 'Insert Image' for a Text artifact."                                                                                                                                                                                 ],
    [ "Extraction",              "Extracted / Extracted From",             "http://www.ibm.com/xmlns/rdm/types/Extraction",                "(System-defined) Captures when the content of a Requirements Management artifact has been created from content of another Requirements Management artifact. This type of link is created when performing extraction-based operations, for example, the 'Save As New' operation for a Text artifact."                                                                                                ],
    [ "Link",                    "Link To / Link From",                    "http://www.ibm.com/xmlns/rdm/types/Link",                      "(System-defined) Tracks a general relationship between Requirements Management artifacts."                                                                                                                                                                                                                                                                                                                             ],
    [ "Mitigation",              "Mitigates / Mitigated By",               "",                                                             "A requirement mitigates a hazard or a risk"                                                                                                                                                                                                                                                                                                                                                                                                        ],
    [ "References",              "References / Referenced By",             "http://purl.org/dc/terms/references",                          "(System-defined) Captures the relationship between a Requirements Management artifact and another Requirements Management artifact in a different RM instance or external project area."                                                                                                                                                                                                                      ],
    [ "Satisfaction",            "Satisfies / Satisfied By",                "",                                                            "A requirement satisfies a higher level requirement."                                                                                                                                                                                                                                                                                                                                                                                             ],
    [ "Specified By",            "Specified By / Specifies",               "http://open-services.net/ns/rm#specifiedBy",                   "(System-defined) Expresses a specification relationship between entities, where the subject entity is specified by the object entity. For example, a requirement is specified by a model element."                                                                                                                                                                                                     ],
    [ "Specifies",               "Specifies / Specified By",               "http://open-services.net/ns/rm#specifies",                     "(System-defined) Expresses a specification relationship between entities, where the subject entity further clarifies or specifies the object entity. For example, a requirement specifies a model element."                                                                                                                                                                                                 ],
    [ "Synonym",                 "Synonym / Synonym",                      "http://www.ibm.com/xmlns/rdm/types/SynonymLink",               "(System-defined) Relates two Requirements Management Glossary Terms that have the same meaning."                                                                                                                                                                                                                                                                                                               ],
]


####################################################################################
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

####################################################################################
# some hardcoded settings - these will need modifying for other environemnts
jazzhost = 'https://jazz.ibm.com:9443'
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

# the project+compontent+config that will be updated
proj = "rm_optout_p1"
comp = proj
conf =  f"{comp} Initial Stream"

####################################################################################
# caching control - if the types in your project aren't changing use 0, otherwise use 2 to re-fetch every time
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2

##################################################################################
if __name__=="__main__":
    if len(sys.argv) != 4:
        raise Exception( 'You must provide: a from identifier, a string for the link type name (enclose in "if it has spaces) and ato identifier' )

    fromid = sys.argv[1]
    linktypename = sys.argv[2]
    toid = sys.argv[3]

    ####################################################################################
    # create our "server" which is how we connect to DOORS Next
    # first enable the proxy so if a proxy is running it can monitor the communication with server (this is ignored if proxy isn't running)
    elmserver.setupproxy(jazzhost,proxyport=8888)
    theserver = elmserver.JazzTeamServer(jazzhost, username, password, verifysslcerts=False, jtsappstring=f"jts:{jtscontext}", appstring='rm', cachingcontrol=caching)

    ####################################################################################
    # create the RM application interface
    dnapp = theserver.find_app( f"rm:{rmcontext}", ok_to_create=True )

    # open the project
    p = dnapp.find_project(proj)

    ####################################################################################
    # find the component
    c = p.find_local_component(comp)
    comp_u = c.project_uri
    print( f"{comp_u=}" )

    ####################################################################################
    # select the configuration
    config_u = c.get_local_config(conf)
    print( f"{config_u=}" )
    c.set_local_config(config_u)

    ####################################################################################
    # load the typesystem - this gets the link types that are available
    c.load_types()
#    print( "Report=",c.textreport() )

    ####################################################################################
    # find the link type
    lt_u = c.get_linktype_uri( linktypename )
    if lt_u is None:
        raise Exception( f"Link type {linktypename} not found" )
    print( f"Link type '{linktypename}' has URI {lt_u}" )
        
    # get the query capability base URL for requirements
    qcbase = c.get_query_capability_uri("oslc_rm:Requirement")


    ####################################################################################
    # find the FROM artifact using OSLC Query
    # query for the id
    artifacts = c.execute_oslc_query(
        qcbase,
        whereterms=[['dcterms:identifier','=',f'"{fromid}"']],
        select=['*'],
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
        )
        
#    print( f"{artifacts=}" )

    if len(artifacts)==0:
        raise Exception( f"No artifact with identifier '{fromid}' found in project {proj} component {comp} configuration {conf}" )
    elif len(artifacts)>2:
        for k,v in artifacts.items():
            print( f'{k} ID {v.get("dcterms:identifier","???")} Title {v.get("dcterms:title","")}' )
        raise Exception( "More than one artifcact with that id in project {proj} component {comp} configuraition {conf}" )
    
    # find the core artifact - it has a value for rm_nav:parent
    fromartifact_u = None
    for artifact in artifacts.keys():
#        print( f"Testing parent on {artifact=}" )
        if artifacts[artifact].get("rm_nav:parent") is not None:
            fromartifact_u = artifact
            break

    if not fromartifact_u:
        raise Exception( "Artifact with rm_nav:parent not found!" )

    print( f"Found FROM core artifact {fromartifact_u=}" )

    ####################################################################################
    # find the TO core artifact using OSLC Query
    # query for the id
    artifacts = c.execute_oslc_query(
        qcbase,
        whereterms=[['dcterms:identifier','=',f'"{toid}"']],
        select=['*'],
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
        )
        
    if len(artifacts)==0:
        raise Exception( f"No artifact with identifier '{toid}' found in project {proj} component {comp} configuration {conf}" )
    elif len(artifacts)>2:
        for k,v in artifacts.items():
            print( f'{k} ID {v.get("dcterms:identifier","???")} Title {v.get("dcterms:title","")}' )
        raise Exception( "More than one artifcact with that id in project {proj} component {comp} configuraition {conf}" )
    
    # find the core artifact - it has a value for rm_nav:parent
    toartifact_u = None
    for artifact in artifacts.keys():
#        print( f"Testing parent on {artifact=}" )
        if artifacts[artifact].get("rm_nav:parent") is not None:
            toartifact_u = artifact
            break

    if not toartifact_u:
        raise Exception( "TO Artifact with rm_nav:parent not found!" )

    print( f"Found TO core artifact {toartifact_u=}" )
    
    # find the URI for the link type

    ####################################################################################
    # now get the FROM artifact content and its etag
    fromartifact_x, etag = c.execute_get_rdf_xml( fromartifact_u, return_etag=True, intent="Retrieve the FROM artifact", cacheable=False )

    ####################################################################################
    # Finally, we're in position to update the artifact adding the link
    # Examine the RDF for an artifact with an outgoing link to see what it looks like - (ignore the nodeID elements, these are entirely managed by DN) 
    # Have to add, e.g. for a "Link to" a new xml tag below the <rdf:Description which has an attribute rdf:about
    #  <j.0:Link rdf:resource="https://jazz.ibm.com:9443/rm/resources/TX_9srNUFEhEe2d5dG-54qhbg"/>
    # (where namespace xmlns:j.0="http://www.ibm.com/xmlns/rdm/types/" - this is automatically handled by rdfxml.py/lxml/elementtree)

    # the element we want to modify is the only rdf:Description with rdf:about
    thenode_x = rdfxml.xml_find_element( fromartifact_x, ".//rdf:Description[@rdf:about]" )
    
    if thenode_x is None:
        raise Exception( "Something went unexpectedly wrong: no relevant rdf:Description found!" )

    # check if the link is already present!
    print( "Checking for existing link", f"{rdfxml.uri_to_prefixed_tag( lt_u )}[@rdf:resource='{toartifact_u}']" )
    link_x = rdfxml.xml_find_element( thenode_x, f"{rdfxml.uri_to_prefixed_tag( lt_u )}[@rdf:resource='{toartifact_u}']" )
    if link_x is not None:
        print( "Link already exists - removing it!" )
        # remove the link
        thenode_x.remove( link_x ) 
    else:
        print( "Link does not already exist - adding it" )
        # add the new link
        thelink_x = ET.SubElement( thenode_x, rdfxml.uri_to_tag( lt_u ), {'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource': toartifact_u } )
        
    # PUT it back to update the artifact
    response = c.execute_post_rdf_xml( fromartifact_u, data=fromartifact_x, put=True, cacheable=False, headers={'If-Match':etag}, intent="Update the artifact"  )
    print( f"{response.status_code}" )
    location = response.headers.get('Location')
    if response.status_code != 200:
        raise Exception( "PUT failed!" )
                    
    # get the content again - this time it will have the new link :-)
    toartifact_x, etag = c.execute_get_rdf_xml( fromartifact_u, return_etag=True, intent="Retrieve the artifact", cacheable=False )

