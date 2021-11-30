##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of accessing the module structure API
# prints the module content with indenting corresponding to headings
# attempted recreating the section number scheme used by DOORS Next but doesn't yet work correctly :-o

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

jazzhost = 'https://jazz.ibm.com:9443'
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

proj = "rm_optout_p1"
comp = proj
conf =  f"{comp} Initial Stream"
mod = "AMR Stakeholder Requirements Specification"

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 0

##################################################################################
# converts heading level into a string that looks like "section" when you add that column into a module
# not exhaustively tested but seems to work :-)
def getsectionnumber( headinglevel):

hs = []
    for hn,tn in headinglevel:
        if tn:
            hs.append( f"{hn}-{tn}" )
        else:
            hs.append( f"{hn}" )
    h = ".".join(hs)
    return h


##################################################################################
# iterator to walk the XML hierarchy in a way that lets us track entry/exit from a nesting
def iterwalk(root, events=None, tags=None):
    """Incrementally walks XML structure (like iterparse but for an existing ElementTree structure)
    Returns an iterator providing (event, elem) pairs.
    Events are start and end
    events is a list of events to emit - defaults to ["start","end"]
    tags is a single tag or a list of tags to emit events for - if None or empty list then events are generated for all tags
    """
    # each stack entry consists of a list of the xml element and a second entry initially None
    # if the second entry is None a start is emitted and all children of current element are put into the second entry
    # if the second entry is a non-empty list the first item in it is popped and then a new stack entry is created
    # once the second entry is an empty list, and end is generated and then stack is popped
    stack = [[root,list(root)]]
#    tags = tags if type(tags) == list else tags or []
    tags = [] if tags is None else tags if type(tags) == list else [tags]
    events = events or ["start","end"]
    def iterator():
        while stack:
            elnow,children = stack[-1]
            if children is None:
                # this is the start of elnow so emit a start and put its children into the stack entry
                if ( not tags or elnow.tag in tags ) and "start" in events:
                    yield ("start",elnow)
                # put the children into the top stack entry
                stack[-1][1] = list(elnow)
            elif len(children)>0:
                # do a child and remove it
                thischild = children.pop(0)
                # and now create a new stack entry for this child
                stack.append([thischild,None])                
            else:
                # finished these children - emit the end
                if len(stack)>1 and ( not tags or elnow.tag in tags ) and "end" in events:
                    yield ("end",elnow)
                stack.pop()
    return iterator

def iterwalk1(root, events=None, tags=None):
    """Recuirsive version - Incrementally walks XML structure (like iterparse but for an existing ElementTree structure)
    Returns an iterator providing (event, elem) pairs.
    Events are start and end
    events is a list of events to emit - defaults to ["start","end"]
    tags is a single tag or a list of tags to emit events for - if None or empty list then events are generated for all tags
    """
    tags = [] if tags is None else tags if type(tags) == list else [tags]
    events = events or ["start","end"]
    
    def recursiveiterator(el,suppressyield=False):
        if not suppressyield and ( not tags or el.tag in tags ) and "start" in events:
            yield ("start",el)
        for child in list(el):
            yield from recursiveiterator(child)
        if not suppressyield and  ( not tags or el.tag in tags ) and "end" in events:
            yield ("end",el)
            
    def iterator():
        yield from recursiveiterator( root, suppressyield=True )
        
    return iterator


##################################################################################
if __name__=="__main__":

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
    config_u = c.get_local_config(conf)
    print( f"{config_u=}" )
    c.set_local_config(config_u)

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

    mod_x = c.execute_get_rdf_xml(themodule_u, cacheable=False,  headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header

    print( f"{mod_x=}" )

    # report the structure

    structure_u = rdfxml.xmlrdf_get_resource_uri( mod_x, ".//rm_module:structure" )
    print( f"{structure_u=}" )

    # retrieve the structure element
    modstructure_x = c.execute_get_rdf_xml(structure_u, cacheable=False, headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header

    # find the root binding
    modroot_x = rdfxml.xml_find_element( modstructure_x, './rm_module:Binding' )

        
    # Now explore the structure for childBinding (which corresponds to nesting) and Binding (which is a binding of an artifact into the module)
    it = iterwalk1(modroot_x, events=["start","end"], tags=[rdfxml.uri_to_tag('rm_module:childBindings'),rdfxml.uri_to_tag("rm_module:Binding")] )
    print( f"{it=}" )
    level = 0

    headinglevel = [] # heading level is a list of two-element lists - first is the heading number, second is the non-heading number

    for event,el in it():
        logger.info( f"{event=} {el.tag=} {headinglevel=}" )
        
        # childBinding is an increase in nesting of headings
        if el.tag==rdfxml.uri_to_tag("rm_module:childBindings"):
            if event == "start":
                level += 1
                headinglevel.append([0,0])
            if event == "end":
                level -= 1
                headinglevel.pop()
                
        # Binding is an artifact
        if el.tag==rdfxml.uri_to_tag("rm_module:Binding"):
            # if it's a heading this increments section differently from non-heading
            isheading = ( rdfxml.xmlrdf_get_resource_text( el, './rm_module:isHeading' ) == "true" )
            logger.info( f"{isheading=}" )
            
            if event=="start":
                # retrieve the title of the artifact, only needed in the "start"
                ba_u = rdfxml.xmlrdf_get_resource_uri( el, './rm_module:boundArtifact' )
                if ba_u and ba_u.startswith( c.app.baseurl ):
                    req_x = c.execute_get_rdf_xml( ba_u )
                    summary = rdfxml.xmlrdf_get_resource_text( req_x,'.//dcterms:title')
                else:
                    summary = "TOP LEVEL"
                    raise Exception( f"Unexpected: No or invalid artifact URI {ba_u}" )
                if isheading:
                    # increment the heading number and reset the sub-number
                    headinglevel[-1][0] += 1
                    headinglevel[-1][1] = 0
                else:
                    # increment the sub-number
                    headinglevel[-1][1] += 1
                # report the current item
                print( f"{'    '*level}", end="" )
                if True or isheading:
                    h = getsectionnumber(headinglevel)
                    print( f"{h}", end="" )
                print( f"  {summary}" )

