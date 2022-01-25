##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# example of accessing the module structure API https://jazz.net/wiki/bin/view/Main/DNGModuleAPI
# also see https://jazz.net/wiki/bin/view/Main/DNGModuleApiOverview
# prints the module content with indenting corresponding to headings and calculated section number
# NOTE NOTE NOTE the section number calculation has not been fully verified/checked - it seems to work after superficial inspection

# provide on the commandline the id of an artifact in the same component and a new binding for it will be created in the structure - location hardcoded!

import csv
import logging
import sys
import time

import lxml.etree as ET
import tqdm

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

# choose a format to retrieve the structure
format = "JSON"
#format  ="RDFXML"

print( f"Retreiving structure in {format}" )

# caching control
# 0=fully cached (but code below specifies queries aren't cached) - if you need to clear the cache, delet efolder .web_cache
# 1=clear cache initially then continue with cache enabled
# 2=clear cache and disable caching
caching = 2

##################################################################################
# converts heading level into a string that looks like "section" when you add that column into a module
# not exhaustively tested but seems to work :-)
# NOTE NOTE NOTE the section number calculation has not been fully verified/checked - it seems to work after superficial inspection
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
    comp_u = c.project_uri
    print( f"{comp_u=}" )

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
        prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rdm_types"]:'rdm_types',rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]:'jazz_rm'} # note this is referest - url to prefix
        )
        
    if len(modules)==0:
        raise Exception( f"No module '{mod}' with that name in project {proj} component {comp} configuration {conf}" )
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

    structure_u = rdfxml.xmlrdf_get_resource_uri( mod_x, ".//rm_modules:structure" )
    print( f"{structure_u=}" )

    if len(sys.argv)>1:
        # second argument is an ID - it *MUST* be in the same configuration as the module!
        # first find the artifact to insert, using OSLC Query
        # query for a title and for format=module
        toinserts = c.execute_oslc_query(
            qcbase,
            whereterms=[['dcterms:identifier','=',sys.argv[1]]],
            select=['*'],
            prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'}
            )
            
        if len(toinserts)==0:
            raise Exception( f"No artifact '{sys.argv[1]}' with that name in project {proj} component {comp} configuration {conf}" )
        elif len(toinserts)>1:
            toinsert_u = None
            for k,v in toinserts.items():
                # find the first one with a rm_nav:parent
                folder = v.get("rm_nav:parent")
                if folder is not None:
                    toinsert_u = k
                    break
            if toinsert_u is None:
                raise Exception( f"No artifact {sys.argv[1]} found with a folder" )
        else:
            toinsert_u = list(toinserts.keys())[0]
        print( f"{toinsert_u=}" )
        
    if format == "RDFXML":
        # retrieve the structure element in RDF-XML
        modstructure_x = c.execute_get_rdf_xml(structure_u, cacheable=False, headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header

        if len(sys.argv)>1:            
            # toinsert is already prepared
            # get the etag
            response = c.execute_get_raw(structure_u, cacheable=False, headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header
            etag = response.headers['ETag']
            print( f"{etag=}" )
            # insert a reference to it in a hardcoded location
            firsthead_x = rdfxml.xml_find_elements(modstructure_x,'rm_modules:Binding/rm_modules:childBindings/rm_modules:Binding/rm_modules:childBindings')[0]
            print( f"{firsthead_x=}" )
#        <rm_modules:childBindings rdf:parseType="Collection">
#            <rm_modules:Binding rdf:about="https://clmwb.com:9444/rdm/resources/MB_2f75a3f310ec42ccadb68e4442617a74">
#                <rm_modules:isHeading rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</j.0:isHeading>
#                <oslc_config:component rdf:resource="https://clmwb.com:9444/rdm/cm/component/_Y5OakLruEeevMtDqCXe--Q"/>
#                <rm_modules:boundArtifact rdf:resource="https://clmwb.com:9444/rdm/resources/CA_3a7b45d1caa540d485ffc9832b802d47"/>
#                <rm_modules:module rdf:resource="https://clmwb.com:9444/rdm/resources/_4sscEb43EeeD0-df1VhHuw"/>
#                <rm_modules:childBindings rdf:parseType="Collection">

#            s1 = ET.SubElement( firsthead_x )

            # add a new childbinding
#                    <rm_modules:Binding rdf:about="https://clmwb.com:9444/rdm/resources/_4sscEb43EeeD0-df1VhHuw/structure#1">
#                        <oslc_config:component rdf:resource="https://clmwb.com:9444/rdm/cm/component/_Y5OakLruEeevMtDqCXe--Q"/>
#                        <rm_modules:boundArtifact rdf:resource="https://clmwb.com:9444/rdm/resources/CA1"/>
#                        <rm_modules:module rdf:resource="https://clmwb.com:9444/rdm/resources/_4sscEb43EeeD0-df1VhHuw"/>
#                        <rm_modules:childBindings rdf:resource="http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"/>
#                    </rm_modules:Binding>
            newbinding = ET.fromstring(
                f"""<rm_modules:Binding
                            xmlns:rdf='{rdfxml.RDF_DEFAULT_PREFIX["rdf"]}'
                            xmlns:oslc_config='{rdfxml.RDF_DEFAULT_PREFIX["oslc_config"]}'
                            xmlns:rm_modules='{rdfxml.RDF_DEFAULT_PREFIX["rm_modules"]}'
                            rdf:about="https://clmwb.com:9444/rdm/resources/_4sscEb43EeeD0-df1VhHuw/structure#1">
                        <oslc_config:component rdf:resource="{comp_u}"/>
                        <rm_modules:boundArtifact rdf:resource="{toinsert_u}"/>
                        <rm_modules:module rdf:resource="{themodule_u}"/>
                        <rm_modules:childBindings rdf:resource="http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"/>
                    </rm_modules:Binding>
                """
                )
            print( f"{newbinding=}" )
            firsthead_x.append(newbinding)
            
            # PUT the new structure and wait for it to be saved
            response = c.execute_post_rdf_xml( structure_u, data=modstructure_x, put=True, cacheable=False, headers={'If-Match':etag,'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None}  )
            print( f"{response.status_code}" )
            location = response.headers.get('Location')
            if response.status_code == 202 and location is not None:
                # wait for the tracker to finished
                result = c.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Updating Structure")
                time.sleep( 0.5 )
                    
            # get the structure again
            modstructure_x = c.execute_get_rdf_xml(structure_u, cacheable=False, headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header
            
        # find the root binding
        modroot_x = rdfxml.xml_find_element( modstructure_x, './rm_modules:Binding' )

            
        # Now explore the structure for childBinding (which corresponds to nesting) and Binding (which is a binding of an artifact into the module)
        it = iterwalk1(modroot_x, events=["start","end"], tags=[rdfxml.uri_to_tag('rm_modules:childBindings'),rdfxml.uri_to_tag("rm_modules:Binding")] )
        print( f"{it=}" )
        level = 0

        headinglevel = [] # heading level is a list of two-element lists - first is the heading number, second is the non-heading number

        for event,el in it():
            logger.info( f"{event=} {el.tag=} {headinglevel=}" )
            
            # childBinding is an increase in nesting of headings
            if el.tag==rdfxml.uri_to_tag("rm_modules:childBindings"):
                if event == "start":
                    level += 1
                    headinglevel.append([0,0])
                if event == "end":
                    level -= 1
                    headinglevel.pop()
                    
            # Binding is an artifact
            if el.tag==rdfxml.uri_to_tag("rm_modules:Binding"):
                # if it's a heading this increments section differently from non-heading
                isheading = ( rdfxml.xmlrdf_get_resource_text( el, './rm_modules:isHeading' ) == "true" )
                logger.info( f"{isheading=}" )
                
                if event=="start":
                    # retrieve the title of the artifact, only needed in the "start"
                    ba_u = rdfxml.xmlrdf_get_resource_uri( el, './rm_modules:boundArtifact' )
                    if ba_u and ba_u.startswith( c.app.baseurl ):
                        req_x = c.execute_get_rdf_xml( ba_u )
                        summary = rdfxml.xmlrdf_get_resource_text( req_x,'.//dcterms:title')
                        id = rdfxml.xmlrdf_get_resource_text( req_x,'.//dcterms:identifier')
                    else:
                        summary = "TOP LEVEL"
                        id = "-"
                        raise Exception( f"Unexpected: No or invalid artifact URI {ba_u}" )
                    if isheading:
                        # increment the heading number and reset the sub-number
                        headinglevel[-1][0] += 1
                        headinglevel[-1][1] = 0
                    else:
                        # increment the sub-number
                        headinglevel[-1][1] += 1
                    # report the current item
                    print( f"{id}{'    '*level}", end="" )
                    if True or isheading:
                        # NOTE NOTE NOTE the section number calculation has not been fully verified/checked - it seems to work after superficial inspection
                        h = getsectionnumber(headinglevel)
                        print( f"{h}", end="" )
                    print( f"  {summary}" )

    elif format == "JSON":
        # retrieve the structure element in RDF-XML
        modstructure_j = c.execute_get_json(structure_u, cacheable=False, headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header

        if len(sys.argv)>1:     
            # Following code harcodes location where new binding is inserted, so need the root to be the first element in the structure list
            if not modstructure_j[0]["isStructureRoot"]:
                raise Exception( "Root not at start of structure!" )
            # toinsert is already prepared
            # get the etag
            response = c.execute_get_raw(structure_u, cacheable=False, headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header
            etag = response.headers['ETag']
            print( f"{etag=}" )
            # insert a reference to it in a hardcoded location
            # this is a very blunt method - a tidier method would be to find the section and insert at that location
#{
#  "uri" : "https://jazz.ibm.com:9443/rm/resources/BI__yq5s0B6Eeuh3Iiax2L3Ow",
#  "type" : "dng_module:Binding",
#  "component" : "https://jazz.ibm.com:9443/rm/cm/component/__J_JEEB6Eeuh3Iiax2L3Ow",
#  "isHeading" : false,
#  "module" : "https://jazz.ibm.com:9443/rm/resources/MD__y90_0B6Eeuh3Iiax2L3Ow",
#  "boundArtifact" : "https://jazz.ibm.com:9443/rm/resources/TX__2GBIkB6Eeuh3Iiax2L3Ow",
#  "childBindings" : [ ]
#}          
            tempbinding_u = "https://clmwb.com:9444/rdm/resources/_4sscEb43EeeD0-df1VhHuw/structure#1"
            newbinding = {
                    "uri": tempbinding_u,
                    "component": comp_u,
                    "type": "dng_module:Binding",
                    "module": themodule_u,
                    "boundArtifact": toinsert_u,
                    "childBindings": []
                }
            # this assumes the root is the first entry!
            modstructure_j[0]["childBindings"].append(tempbinding_u)
            modstructure_j.append(newbinding)
            # PUT the new structure and wait for it to be saved
            response = c.execute_post_json( structure_u, data=modstructure_j, put=True, cacheable=False, headers={'If-Match':etag,'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None}  )
            print( f"{response.status_code}" )
            location = response.headers.get('Location')
            if response.status_code == 202 and location is not None:
                # wait for the tracker to finished
                result = c.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Updating Structure")
                time.sleep( 0.5 )
                    
            # get the structure again afer the update
            modstructure_j = c.execute_get_json(structure_u, cacheable=False, headers={'vvc.configuration': config_u,'DoorsRP-Request-Type':'public 2.0', 'OSLC-Core-Version': None, 'Configuration-Context': None} ) # have to remove the OSLC-Core-Version and Configuration-Context headers, and provide vvc.configuration header

        # scan all the entries into a dictionary keyed by the URL
        entries = {}
        for s in modstructure_j:
            entries[s["uri"]] = s

        # find the root binding
        modroot = entries[structure_u]

        # generator recursively walking the structure
        def json_structure_walk(rooturi,entries):
            """
            Module structure recursive iterator
            """
            def recursiveiterator(uri,suppressyield=False):
#                print( f"starting {uri}" )
                if not suppressyield:
                    yield ("start",entries[uri])
                yield ("startChildren",entries[uri])
                for child in list(entries[uri]["childBindings"]):
                    yield from recursiveiterator(child)
                yield ("endChildren",entries[uri])
                if not suppressyield:
                    yield ("end",entries[uri])
#                print( f"ending {uri}" )
                    
            def iterator():
                yield from recursiveiterator( rooturi, suppressyield=True )
                
            return iterator        

        # Now explore the structure for childBinding (which corresponds to nesting) and Binding (which is a binding of an artifact into the module)
        it = json_structure_walk(structure_u,entries )
#        print( f"{it=}" )
        level = 0

        headinglevel = [] # heading level is a list of two-element lists - first is the heading number, second is the non-heading number

        for event,el in it():
            
            # childBinding is an increase in nesting of headings
            if event == "startChildren":
                level += 1
                headinglevel.append([0,0])
            if event == "endChildren":
                level -= 1
                headinglevel.pop()
                    
            isheading = el["isHeading"]
            
            if event=="start":
                # retrieve the title of the artifact, only needed in the "start"
                ba_u = el["uri"]
                if ba_u.startswith( c.app.baseurl ):
                    req_x = c.execute_get_rdf_xml( ba_u )
                    summary = rdfxml.xmlrdf_get_resource_text( req_x,'.//dcterms:title')
                    id = rdfxml.xmlrdf_get_resource_text( req_x,'.//dcterms:identifier')
                else:
                    summary = "TOP LEVEL"
                    id = "-"
                    raise Exception( f"Unexpected: No or invalid artifact URI {ba_u}" )
                if isheading:
                    # increment the heading number and reset the sub-number
                    headinglevel[-1][0] += 1
                    headinglevel[-1][1] = 0
                else:
                    # increment the sub-number
                    headinglevel[-1][1] += 1
                # report the current item
                print( f"{id}{'    '*level}", end="" )
                if True or isheading:
                    # NOTE NOTE NOTE the section number calculation has not been fully verified/checked - it seems to work after superficial inspection
                    h = getsectionnumber(headinglevel)
                    print( f"{h}", end="" )
                print( f"  {summary}" )

    else:
        raise Exception( f"Invalid format {format}" )
        