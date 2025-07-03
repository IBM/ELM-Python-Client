##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

import datetime
import logging
import re
import sys
import time

import anytree
import dateutil.parser
import dateutil.tz
import lxml.etree as ET
import requests
import tqdm
import pytz

from . import _app
from . import _config
from . import _project
from . import _typesystem
from . import oslcqueryapi
from . import rdfxml
from . import server
from . import utils
from . import _newtypesystem
from . import resource

# used for OSLC Query on types
typeresources = {
    'http://jazz.net/ns/rm/dng/types#ArtifactType':        ('ArtifactType'       ,'OT'),
    'http://jazz.net/ns/rm/dng/types#AttributeDefinition': ('AttributeDefinition','AD'),
    'http://jazz.net/ns/rm/dng/types#AttributeType':       ('AttributeType'      ,'AT'),
    'http://jazz.net/ns/rm/dng/types#LinkType':            ('LinkType'           ,'LT'),
}


#################################################################################################

logger = logging.getLogger(__name__)

#################################################################################################

class _Folder(anytree.NodeMixin):
    def __init__(self, name=None, folderuri=None, parent=None):
        super().__init__()
        self.name = name
        self.folderuri = folderuri
        self.parent = parent

#################################################################################################

if False:
    @utils.mixinomatic
    class _RM_PA_stream( _config._Stream,_RMProject ):
        pass

    @utils.mixinomatic
    class _RM_PA_baseline( _config._Baseline,_RMProject ):
        pass

    @utils.mixinomatic
    class _RM_PA_changeset( _config._Changeset,_RMProject):
        pass

@utils.mixinomatic
class RMProject(_project._Project, resource.Resources_Mixin ):
    # A project
    # NOTE there is a derived class RMComponent used for RM components - it doesn't offer any
    #   functionality, and is a separate class only so it's easier to see whether an instance is a component or the overall project
    # For opt-out projects the only component *is* the project, so RMComponent isn't used.
    # For full optin there are as many components as real components; for <=6.0.3 Cfgm-enabled and for >=7.0
    #   CfgM-disabled (called single mode), there's only ever a single component
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True):
#        super().__init__(name, project_uri, app, is_optin,singlemode,defaultinit=defaultinit)
#        self.oslcquery = oslcqueryapi._OSLCOperations(self.app.server,self)
        self._components = {}  # keyed on component uri
        self._configurations = {} # keyed on the config name
        self._folders = None
        self._foldersnotyetloaded = None
        self.is_singlemode = False # this is only true if config enabled is true and single mode is true
        self.gcconfiguri = None
        self.default_query_resource = "oslc_rm:Requirement"
        self._iscomponent=False
        self._confs_to_load = []
        self._confstoparent = []
        self.configTree = None
        self._types = None
        
    # save a folder details, and return the new folder instance
    def _savefolder( self, parent, fname, folderuri ):
        ROOTNAME = "+-+root+-+"
        if parent is None:
            # ROOT folder
            thisfolder = _Folder(name=ROOTNAME,folderuri=folderuri)
            self._folders[ROOTNAME] = thisfolder
            logger.debug( f"Adding root {ROOTNAME} {thisfolder}" )
        else:
            # non-ROOT folder
            thisfolder = _Folder(name=fname,folderuri=folderuri, parent=parent)

        # insert the name and its queryuri
        if fname in self._folders:
            if self._folders[fname] is not None:
                if folderuri != self._folders[fname].folderuri:
                    self._folders[fname] = None # ambiguous!!!
                    logger.info( f"Folder name ambiguous {fname=} {folderuri} is ambiguous!" )
        else:
            logger.info( "Not ambiguous" )
            self._folders[fname]=thisfolder

        # insert by folder uri
        self._folders[folderuri] = thisfolder
        logger.debug( f"Adding by uri {folderuri} {thisfolder}" )

        # insert by path
        if parent is None:
            pathname = "/"
        else:
            pathname = "/"+"/".join([n.name for n in thisfolder.path[1:]])
        logger.info( f"{pathname=}" )
        self._folders[pathname]=thisfolder
        logger.debug( f"Adding by path {pathname} {thisfolder}" )

        thisfolder.pathname = pathname
        return thisfolder

    #
    # load folders until name_or_uri is found (cuts loading short, remembers folders still to load) or until all loaded
    #  returns None or the matching Folder instance
    #
    # name_or_uri can be:
    #   a folder URI
    #   a folder name - NEVER begins with / - BUT NOTE if the name is ambiguous the return will be None!
    #   a folder path - which ALWAYS begins with /, mustn't end with /. Whitespace is allowed in names but not at start or end!
    #
    # can be called again and will continue loading folders
    # returns None or Folder instance
    #
    # a folder path starts with / from the equivalent root in DNG
    # _folders is a dictionary which holds:
    #    folder name ->  Folder instance
    #    folder path ->  Folder instance
    #    query uri   ->  Folder instance (query URI is only used when building the folder tree)
    #

    def load_folders(self,name_or_uri=None,force=False):
        raise Exception( "This call is no longer supported - use find_folder() instead of load_folders()!" )

    def _load_folders(self,name_or_uri=None,force=False):
        logger.info( f"load_folders {name_or_uri=}" )
        if name_or_uri is None:
            raise Exception( "name_or_uri is None!" )


        if self._folders is not None and name_or_uri in self._folders:
            # we've loaded _folders, and the one we're looking for is present in _folders
            if self._folders[name_or_uri] is None:
                # ambiguous name
                logger.info( f"Found folder name {name_or_uri} as Ambiguous" )
                return None
            logger.info( f"Found {name_or_uri} as {self._folders[name_or_uri]}" )
            return self._folders[name_or_uri]

        # the name_or_uri isn't known - may need to load some more folders!
        if force or self._folders is None:
            # need to load folders from scratch starting from the folder query capability
            self._folders = {}
            self._foldersnotyetloaded=[]
            # retrieve the folder query - this is the starting point
            qcuri = self.get_query_capability_uri(resource_type='http://jazz.net/ns/rm/navigation#folder')
            if qcuri is None:
                logger.info( "No folder query capability - this must be a very old version of DOORS Next" )
                self._folders={}
                return None
            logger.debug( f"Root folder query= {qcuri}" )
            self._foldersnotyetloaded=[qcuri] # this list becomes None once all folders are loaded - as folders are loaded, their subfolders are added here

        # load more folders until either the name_or_uri is matched or there aren't any more to load
        while len(self._foldersnotyetloaded)>0:
            logger.info( "-----------------------" )
            # retrieve the next fodler query result
            queryuri = self._foldersnotyetloaded.pop(0)
            parent = self._folders.get(queryuri) # parent is None for the first query for the root folder

            logger.info( f"Retrieving {queryuri=} parent {self._folders.get(queryuri)}" )
            # get these with caching disabled because folder changes are more frequent than typesystem (probably?)
            folderxml = self.execute_get_xml(queryuri, cacheable=False, intent="Retrieve folder definition").getroot()

            # find the contained folders
            folderels = rdfxml.xml_find_elements(folderxml,'.//rm_nav:folder')

            # process the contained folders
            for folderel in folderels:
                # get this folder details - name, queryuri
                fname = rdfxml.xmlrdf_get_resource_text(folderel,'.//dcterms:title')
                folderuri = rdfxml.xmlrdf_get_resource_uri( folderel )
                logger.info( f"{fname=} {folderuri=}" )

                thisfolder = self._savefolder( parent, fname, folderuri )

                # insert the subfolder query uris into the list still to be loaded
                for subel in rdfxml.xml_find_elements(folderel,'.//rm_nav:subfolders'):
                    # add the subfolder query queryuri onto the list of folders to retrieve
                    subqueryuri = rdfxml.xmlrdf_get_resource_uri( subel )
                    # add at start of folders to load so search goes deep first
                    self._foldersnotyetloaded.insert( 0,subqueryuri )
                    # for the queryuri, record the folder which is its parent
                    self._folders[subqueryuri] = thisfolder

            # now this response has been processed check if name_or_uri has been matched
            if name_or_uri in self._folders:
                if self._folders[name_or_uri] is None:
                    logger.info( f"Retrieved {name_or_uri} as Ambiguous" )
                    # ambiguous
                    return None
                logger.info( f"Retrieved {name_or_uri} as {self._folders[name_or_uri]}" )
                return self._folders[name_or_uri]
        return None

    def find_folder( self, name_or_path_or_uri, force=False ):
        return self._load_folders( name_or_path_or_uri, force=force )

    # MUST be provided a path starting with / because if it were just a name we wouldn't know where to create it!
    # this will create any missing folders in the path to create the final folder
    # new folders are recorded so no need to reoaod the full folder hierarchy!
    def create_folder( self, path ):
        if not path.startswith( "/" ):
            raise Exception( f"You *must* provide a path starting with / for the new folder otherwise don't know where to create it! You provided {path}" )

        existing = self._load_folders(name_or_uri=path)
        if existing is not None:
            return existing
        # at this point we know the folder path doesn't already exist - will have to create at least the final folder on the path
        pathels = path[1:].split( "/" )
        # walk forwards through the path ensuring all the path elements exist
        # get the root folder - must have been loaded by the prior call to load_folders() above here
        parent = self.find_folder( "/" )
        for n in range( len( pathels) ):
            if len(pathels[n].strip())==0:
                raise Exception( f"Badly specified path '{path}' has consecutive // or a path element is just whitespace or path ends with /!" )
            thispath = "/"+"/".join(pathels[0:n+1])
            this_folder = self.find_folder( thispath )
            if this_folder is None:
                # create the new folder
                folderfactory_u = self.reluri( "folders" )
                # this isn't an elegant way of creating XML; would be much better to build it and let ET do the namespaces!
                # NOTE the rdf:about must be an empty string!
                folderuri = parent.folderuri if parent else None
                logger.info( f"Creating folder {pathels[n]=} in {parent} {folderuri=}" )
                newfolder_t = f"""<rdf:RDF
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns:dcterms="http://purl.org/dc/terms/"
xmlns:oslc="http://open-services.net/ns/core"
xmlns:oslc_config="http://open-services.net/ns/config#"
xmlns:nav="http://jazz.net/ns/rm/navigation#"
xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/"
>
<nav:folder rdf:about="">
  <dcterms:title>{pathels[n]}</dcterms:title>
  <dcterms:description>The description is optional.</dcterms:description>
  <nav:parent rdf:resource="{parent.folderuri}"/>
</nav:folder>
</rdf:RDF>"""

                newfolder_x = ET.fromstring( newfolder_t )
                response = self.execute_post_rdf_xml( folderfactory_u, data=newfolder_x, params={'projectURL': self.reluri(f'process/project-areas/{self.iid}')}, headers={'vvc.configuration': self.local_config, 'Configuration-Context': None, }, intent=f"Create the new folder '{this_folder}'"  )
                thefolder_u = response.headers.get('Location')

                # in case caching is in use, re-retrieve the parent folder bypassing the cache
                # no need to save it!
                logger.info( f"re-retrieve parent {parent.folderuri=} parent '{self._folders.get(parent.folderuri)}'" )
                self.execute_get_xml( parent.folderuri, cacheable=False, intent="Re-retrieve parent folder definition" )

                # insert the new folder into the known folders
                newfolder = self._savefolder( parent, pathels[n], thefolder_u )
                parent = newfolder
            else:
                logger.info( f"Path exists {thispath=}" )
                parent = this_folder
                pass
        logger.info( f"{self.find_folder( path )=}" )
        return self.find_folder( path )

    def delete_folder( self, name_or_uri ):
        raise Exception( "Folder delete not implemented! Left as an exercise for the user" )
        
    def _get_headers(self, headers=None):
        logger.info( f"rmp gh {headers=}" )
        result = super()._get_headers()
#        result['net.jazz.jfs.owning-context'] = self.baseurl
        if headers:
            result.update(headers)
        logger.info( f"rmp gh {result=}" )
        return result

    def load_components_and_configurations(self,force=False, cacheable=True):
        if self._components and not force:
            return
        self.configTree = anytree.AnyNode(name="theroot")
        logger.info( f"load_components_and_configurations {self=} {self.is_optin=}" )
        self._components = {}
        self._configurations = {}
        ncomps = 0
        nconfs = 0
        # retrieve components and configurations for this project
        if not self.is_optin:
            # get the default configuration
            projx = self.execute_get_xml(self.reluri('rm-projects/' + self.iid), intent="Retrieve project definition", cacheable=cacheable)
            compsu = rdfxml.xmlrdf_get_resource_text( projx, './/jp06:components' )
            compsx = self.execute_get_xml(compsu, intent="Retrieve component definition", cacheable=cacheable)
            defaultcompu = rdfxml.xmlrdf_get_resource_uri( compsx, './/oslc_config:component' )

            # register the only component
            ncomps += 1
            self._components[defaultcompu] = {'name': self.name, 'configurations': {}, 'confs_to_load': []}
            thisconfu = defaultcompu+"/configurations"
            configs = self.execute_get_json(thisconfu, intent="Retrieve configurations (JSON)")
#            configdetails = configs[defaultcompu+"/configurations"]
            if thisconfu in configs:
                if type(configs[thisconfu]["http://www.w3.org/2000/01/rdf-schema#member"])==dict:
                    confs = [configs[thisconfu]["http://www.w3.org/2000/01/rdf-schema#member"]['value']]
                else:
                    confs = [c['value'] for c in configs[thisconfu]["http://www.w3.org/2000/01/rdf-schema#member"]]
            else:
                # old - 6.0.2?
                ids = configs["http://www.w3.org/2000/01/rdf-schema#member"]
                if type(ids)==list:
                    confs = [i['@id'] for i in ids]
                else:
                    confs = [ids['@id']]
                logger.debug( "{confs=}" )
            for confu in confs:
#                confu = aconf['value']
                confx = self.execute_get_xml(confu, intent="Retrieve a configuration definition", cacheable=cacheable)
                conftitle = rdfxml.xmlrdf_get_resource_text(confx,'.//dcterms:title')
                conftype = 'Stream' if 'stream' in confu else 'Baseline'
                created = rdfxml.xmlrdf_get_resource_uri(confx, './/dcterms:created')
                self._components[defaultcompu]['configurations'][confu] = {'name': conftitle, 'conftype': conftype, 'confXml': confx, 'created': created}
                self._configurations[defaultcompu] = self._components[defaultcompu]['configurations'][confu]
                nconfs += 1
        elif self.singlemode:
            #get the single component from a QueryCapability
            # <oslc:QueryCapability>
            #    <oslc_config:component rdf:resource="https://mb02-calm.rtp.raleigh.ibm.com:9443/rm/cm/component/_ln_roBIOEeumc4tx0skHCA"/>
            #    <oslc:resourceType rdf:resource="http://jazz.net/ns/rm/dng/view#View"/>
            #    <oslc:queryBase rdf:resource="https://mb02-calm.rtp.raleigh.ibm.com:9443/rm/views_oslc/query?componentURI=https%3A%2F%2Fmb02-calm.rtp.raleigh.ibm.com%3A9443%2Frm%2Fcm%2Fcomponent%2F_ln_roBIOEeumc4tx0skHCA"/>
            #    <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">View Definition Query Capability</dcterms:title>
            # </oslc:QueryCapability>

            px = self.execute_get_xml(self.project_uri, intent="Retrieve the project definition", cacheable=cacheable)

            sx = self.get_services_xml()
            assert sx is not None, "sx is None"
            compuri = rdfxml.xmlrdf_get_resource_uri(sx, ".//oslc:QueryCapability/oslc_config:component")
            assert compuri is not None, "compuri is None"

            ncomps += 1
            self._components[compuri] = {'name': self.name, 'configurations': {}, 'confs_to_load': []}
            configs = self.execute_get_xml(compuri+"/configurations", intent="Retrieve project/component's list of all configurations", cacheable=cacheable)
            for conf in rdfxml.xml_find_elements(configs,'.//rdfs:member'):
                confu = rdfxml.xmlrdf_get_resource_uri(conf)
                try:
                    thisconfx = self.execute_get_xml(confu, intent="Retrieve a configuration definition", cacheable=cacheable)
                except:
                    logger.info( f"Singlemode config ERROR probably archived {confu} !!!!!!!" )
                    continue
                conftitle= rdfxml.xmlrdf_get_resource_text(thisconfx,'.//dcterms:title')
                created = rdfxml.xmlrdf_get_resource_uri(thisconfx, './/dcterms:created')
                # e.g. http://open-services.net/ns/config#Stream
                isstr = rdfxml.xml_find_element( thisconfx,'.//oslc_config:Stream' )
                if isstr is None:
                    conftype = "Baseline"
                else:
                    conftype = "Stream"
                self._components[compuri]['configurations'][confu] = {'name': conftitle, 'conftype': conftype, 'confXml': thisconfx, 'created':created}
                self._configurations[confu] = self._components[compuri]['configurations'][confu]
                nconfs += 1
            self._configurations = self._components[compuri]['configurations']
        else: # optin but could be single component
            cmsp_xml = self.app.retrieve_cm_service_provider_xml()
            components_uri = rdfxml.xmlrdf_get_resource_uri(cmsp_xml, './/oslc:ServiceProvider')
            components_xml = self.execute_get_rdf_xml(components_uri, intent="Retrieve project's components service provider definition")
            projcx = rdfxml.xml_find_element(components_xml, './/oslc:CreationFactory', 'dcterms:title', self.name)
            if projcx is None:
                # Old opt-in: single component
                logger.info( f"old optin {self.name=} {self=} {self._iscomponent=}" )

                projx = self.execute_get_xml(self.reluri('rm-projects/' + self.iid), intent="Retrieve the project definition", cacheable=cacheable)
                compsu = rdfxml.xmlrdf_get_resource_text( projx, './/jp06:components' )
                compsx = self.execute_get_xml(compsu, intent="Retrieve the component definition", cacheable=cacheable)
                defaultcompu = rdfxml.xmlrdf_get_resource_uri( compsx, './/oslc_config:component' )

                # register the only component
                ncomps += 1
                self._components[defaultcompu] = {'name': self.name, 'configurations': {}, 'confs_to_load': []}

                configs = self.execute_get_json(defaultcompu+"/configurations", intent="Retrieve configurations (JSON)")
                if type(configs["http://www.w3.org/2000/01/rdf-schema#member"])==dict:
                    confs = [configs["http://www.w3.org/2000/01/rdf-schema#member"]]
                else:
                    confs = configs["http://www.w3.org/2000/01/rdf-schema#member"]
                for aconf in confs:
                    confu = aconf['@id']
                    try:
                        confx = self.execute_get_xml(confu, intent="Retrieve configuration definition RDF", cacheable=cacheable)
                    except:
                        logger.info( f"Old optin config ERROR probably archived {confu} !!!!!!!" )
                        continue
                    conftitle = rdfxml.xmlrdf_get_resource_text(confx,'.//dcterms:title')
                    conftype = 'Stream' if 'stream' in confu else 'Baseline'
                    created = rdfxml.xmlrdf_get_resource_uri(confx, './/dcterms:created')
                    self._components[defaultcompu]['configurations'][confu] = {'name': conftitle, 'conftype': conftype, 'confXml': confx, 'created': created}
                    self._configurations[defaultcompu] = self._components[defaultcompu]['configurations'][confu]
                    nconfs += 1
                    raise Exception( "Something odd in an old 6.0.3-style project" )
            else:
                # full optin
                cru = rdfxml.xmlrdf_get_resource_uri(projcx, 'oslc:creation')
                crx = self.execute_get_rdf_xml(cru, intent="Retrieve project's oslc:creation RDF", cacheable=cacheable)

                for component_el in rdfxml.xml_find_elements(crx, './/ldp:contains'):
                    compu = component_el.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
                    compx = self.execute_get_rdf_xml(compu, intent="Retrieve component definition to find all configurations", action="Retrieve each configuration", cacheable=cacheable)
                    comptitle = rdfxml.xmlrdf_get_resource_text(compx, './/dcterms:title')
                    confu = rdfxml.xmlrdf_get_resource_uri(compx, './/oslc_config:configurations')
                    self._components[compu] = {'name': comptitle, 'configurations': {}, 'confs_to_load': [confu]}
                    ncomps += 1
                    if False:
                        confs_to_load = [confu]
                        while True:
                            if not confs_to_load:
                                break
                            confu = confs_to_load.pop()
                            if not confu:
                                # skip None in list
                                continue
                            logger.debug( f"Retrieving config {confu}" )
                            try:
                                configs_xml = self.execute_get_rdf_xml(confu, intent="Retrieve a configuration definition", cacheable=cacheable)
                            except:
                                logger.info( f"Config ERROR {thisconfu} !!!!!!!" )
                                continue
                            confmemberx = rdfxml.xml_find_elements(configs_xml, './/rdfs:member[@rdf:resource]')
                            if confmemberx:
                                #  a list of members
                                for confmember in confmemberx:
                                    thisconfu = confmember.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
                                    confs_to_load.append(thisconfu)
                            # maybe it's got configuration(s)
                            confmemberx = rdfxml.xml_find_elements(configs_xml, './/oslc_config:Configuration') + rdfxml.xml_find_elements(configs_xml, './/oslc_config:Stream') + rdfxml.xml_find_elements(configs_xml, './/oslc_config:Baseline') + rdfxml.xml_find_elements(configs_xml, './/oslc_config:ChangeSet')

                            for confmember in confmemberx:
                                thisconfu = rdfxml.xmlrdf_get_resource_uri( confmember )
                                logger.debug( f"{thisconfu=}" )
                                conftitle = rdfxml.xmlrdf_get_resource_text(confmember, './/dcterms:title')
                                if rdfxml.xmlrdf_get_resource_uri( confmember,'.//rdf:type[@rdf:resource="http://open-services.net/ns/config#ChangeSet"]') is not None:
                                    conftype = "ChangeSet"
                                elif rdfxml.xmlrdf_get_resource_uri( confmember,'.//rdf:type[@rdf:resource="http://open-services.net/ns/config#Baseline"]') is not None:
                                    conftype = "Baseline"
                                elif rdfxml.xmlrdf_get_resource_uri( confmember,'.//rdf:type[@rdf:resource="http://open-services.net/ns/config#Stream"]') is not None:
                                    conftype = "Stream"
                                elif rdfxml.xmlrdf_get_resource_uri( confmember,'.//rdf:type[@rdf:resource="http://open-services.net/ns/config#Configuration"]') is not None:
                                    conftype = "Stream"
                                else:
                                    print( ET.tostring(confmember) )
                                    raise Exception( f"Unrecognized configuration type" )
                                created = rdfxml.xmlrdf_get_resource_uri(confmember, './/dcterms:created')
                                if thisconfu not in self._components[compu]['configurations']:
                                    logger.debug( f"Adding {conftitle}" )
                                    self._components[compu]['configurations'][thisconfu] = {
                                                                                                'name': conftitle
                                                                                                , 'conftype': conftype
                                                                                                ,'confXml': confmember
                                                                                                ,'created': created
                                                                                            }
                                    self._configurations[thisconfu] = self._components[compu]['configurations'][thisconfu]
                                else:
                                    logger.debug( f"Skipping {thisconfu} because already defined" )
                                # add baselines and changesets
                                confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember, './oslc_config:streams') )
                                confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember, './oslc_config:baselines') )
                                confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember, './rm_config:changesets') )
                                nconfs += 1

        # now create the "components"
        for cu, cd in self._components.items():
            cname = cd['name']
            cconfs_to_load = cd['confs_to_load']
            if not self.is_optin:
                c = self
            else:
                c = self._create_component_api(cu, cname, cconfs_to_load)
            c._configurations = self._components[cu]['configurations']
            c._confs_to_load = self._components[cu]['confs_to_load']
            self._confs_to_load.extend(self._components[cu]['confs_to_load'])
            self._components[cu]['component'] = c
        return (ncomps, nconfs)

    def add_external_component(self,compu):
        # this is only ever used for opt-in projects!
        compx = self.execute_get_rdf_xml(compu, intent="Retrieve component definition to find all configurations", action="Retrieve each configuration")
        comptitle = rdfxml.xmlrdf_get_resource_text(compx, './/dcterms:title')
        confu = rdfxml.xmlrdf_get_resource_uri(compx, './/oslc_config:configurations')
        self._components[compu] = {'name': comptitle, 'configurations': {}, 'confs_to_load': [confu]}

        cname = comptitle
        cconfs_to_load = [confu]
        c = self._create_component_api(compu, cname, cconfs_to_load)
        c._configurations = self._components[compu]['configurations']
        c._confs_to_load = self._components[compu]['confs_to_load']
        self._confs_to_load.extend(self._components[compu]['confs_to_load'])
        self._components[compu]['component'] = c
        return c

    # if given stopatnameoruri returns True if found, False if not (which means all configs have been loaded and it isn't there!)
    def load_configs(self, cacheable=True, stopatnameoruri=None, verbose=False, incremental=False ):
        logger.debug( f"Loading configs {self._confs_to_load=}, {stopatnameoruri=}" )
        # load configurations
        # and build a tree with initial baseline as root, alternating baseline and stream nodes each with a list of children, so it can be walked if needed
        if not incremental or not self.configTree:
            self.configTree = anytree.AnyNode(name='theroot',title='root', created=None, typesystem=None, ismutable=False, ischangeset=False )
        result = False
#        print("Loading configs", self._confs_to_load)
        # now load configs
        while True:
            if verbose:
                print( ".",end="" )
            if not self._confs_to_load:
                break
            confu = self._confs_to_load.pop()
            if not confu:
                # skip None in list
                continue

#            print( f"Retrieving config {confu}" )
            logger.debug( f"Retrieving config {confu}" )
            try:
                configs_xml = self.execute_get_rdf_xml(confu, intent="Retrieve a configuration definition", cacheable=cacheable)
            except:
                logger.info( f"Config ERROR {thisconfu} ignored (the config was probably archived) !!!!!!!" )
                continue

            confmemberx = rdfxml.xml_find_elements(configs_xml, './/rdfs:member[@rdf:resource]')
            if confmemberx:
                #  a list of members
                for confmember in confmemberx:
                    thisconfu = confmember.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
                    self._confs_to_load.append(thisconfu)
#                   print( f"   Adding {thisconfu=}" )
#                    print( f"   Now {self._confs_to_load=}" )

            # maybe it's got configuration(s)
            confmembers_x = list( set( rdfxml.xml_find_elements(configs_xml, './/oslc_config:Configuration') + rdfxml.xml_find_elements(configs_xml, './/oslc_config:Stream') + rdfxml.xml_find_elements(configs_xml, './/oslc_config:Baseline') + rdfxml.xml_find_elements(configs_xml, './/oslc_config:ChangeSet') ) )

            for confmember_x in confmembers_x:
                if verbose:
                    print( ">",end="",flush=True )
#                print( f"========================\n{confmember_x=}" )
#                print( f"{confmember_x.tag=}" )
#               print( "XML=",ET.tostring( confmember_x ) )
                thisconfu = rdfxml.xmlrdf_get_resource_uri( confmember_x )
#                print( f"Member {thisconfu=}" )
                # add baselines and changesets
                self._confs_to_load=list(set(self._confs_to_load))
#                print( f"1 {len(self._confs_to_load)} {self._confs_to_load=}" )
                self._confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember_x, './oslc_config:streams') )
                self._confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember_x, './oslc_config:baselines') )
                self._confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember_x, './rm_config:changesets') )
                self._confs_to_load=list(set(self._confs_to_load))
#                print( f"2 {len(self._confs_to_load)} {self._confs_to_load=}" )
                logger.debug( f"{thisconfu=}" )
                ismutable = False
                ischangeset = False
                conftitle = rdfxml.xmlrdf_get_resource_text(confmember_x, './dcterms:title')
                
                if stopatnameoruri and ( conftitle==stopatnameoruri or thisconfu==stopatnameoruri ):
                    result = True
                    
                created = rdfxml.xmlrdf_get_resource_uri(confmember_x, './dcterms:created', exceptionifnotfound=True)
#                print( f"{conftitle=}" )
#                print( f"{created=}" )
                if confmember_x.tag == '{http://open-services.net/ns/config#}ChangeSet':
                    conftype = "ChangeSet"
                    ischangeset=True
                    ismutable=True
                elif confmember_x.tag == '{http://open-services.net/ns/config#}Baseline':
                    conftype = "Baseline"
                elif confmember_x.tag == '{http://open-services.net/ns/config#}Stream' or rdfxml.xmlrdf_get_resource_uri( confmember_x,'.//rdf:type[@rdf:resource="http://open-services.net/ns/config#Stream"]') is not None:
                    conftype = "Stream"
                    ismutable=True
                else:
#                    print( f"{confmember_x.tag=}" )
#                    print( ET.tostring(confmember_x) )
                    if '/baseline/' in thisconfu:
                        conftype = "Baseline"
                    else:
                        raise Exception( f"Unrecognized configuration type {confmember_x.tag}" )


                if thisconfu in self._configurations:
                    logger.debug( f"Skipping {thisconfu} because already defined" )
#                    print( f"Skipping {thisconfu} because already defined" )
#                    burp
                else:
                    logger.debug( f"Adding {conftitle}" )
#                    print( f"Adding {conftitle}" )
                    self._configurations[thisconfu] = {
                                                        'name': conftitle
                                                        ,'conftype': conftype
                                                        ,'confXml': confmember_x
                                                        ,'created': created
                                                    }
#                    self._configurations[thisconfu] = self._components[self.project_uri]['configurations'][thisconfu]
                # use wasDerivedfrom to find the source or eaither a stream or baseline - there isn't one for the Initial Stream!
                theparent_u = rdfxml.xmlrdf_get_resource_uri( confmember_x,'./prov:wasDerivedFrom')
#                print( f"{theparent_u=}" )
                if not theparent_u:
                    # this is the initial stream
                    parentnode = self.configTree
#                    print( f"Config {conftitle} used theroot {parentnode=}" )
                else:
                    parentnode = anytree.search.find( self.configTree, filter_=lambda n: n.name==theparent_u )
#                    print( f"Config {conftitle} found {parentnode=}" )

                # try to find this config url to see if it's already known
                if anytree.search.find( self.configTree, filter_=lambda n: n.name==thisconfu ):
                    # already in the tree!
#                    print( f"Config {conftitle} Config has parent in configtree {thisconfu} parent={parentnode}" )
                    pass
                else:
                    # need to find the parent to attach to
                    # create the node - if we don't attach it now we'll attach it later - typesystem is set to None so if needed this can be filled in later.
                    thisnode = anytree.AnyNode( None, name=thisconfu, title=conftitle, conftype=conftype, created=created, typesystem=_newtypesystem.TypeSystem(conftitle, thisconfu), ismutable=ismutable ) #TypeSystem(conftitle, thisconfu), ismutable=ismutable, ischangeset=ischangeset )
                    if parentnode is None:
                        # do this one later
                        self._confstoparent.append( ( thisnode, theparent_u ) )
#                        print( f"\nSaved for later {self._confstoparent[-1]=}" )
                    else:
                        # parent is known so attach to it
                        thisnode.parent = parentnode
#                        print( f"\nConfig {conftitle} Added config {thisconfu} parent={parentnode}" )
            # now check if stopatnameoururi is present and if so set result True
            if result:
                break
        
        return result
        
        # now iterate over the unparented nodes repeatedly finding their parents until there are none left because all have been parented
        while self._confstoparent:
            foundparent = False
            # we're going to copy unparented node into this new list, then copy the new list into confstoparent
            newconfstoparent = []
            for (i,nodedetails) in enumerate(self._confstoparent):
                (node,theparent_u) = nodedetails
#                print( f"\n{node=} {theparent_u=}" )
                # if we find the parent, attach it - if not found, add it to this list of those still needing parent
                parentnode = anytree.search.find( self.configTree, filter_=lambda n: n.name==theparent_u )
                if parentnode:
                    # found!
                    node.parent = parentnode
                    foundparent = True
#                    print( f"\nParented {node=} {theparent_u}" )
                else:
                    # remember this still needs parenting! Will be found on a later pass UNLESS it's been tried a few times and always fails
                    # in which case we'll print a message and ignore the config!
                    newconfstoparent.append( (node,theparent_u) )
#                    print( f"\npostponing {node=} {theparent_u}" )
#                    print( f"tree= {anytree.RenderTree(self.configTree, style=anytree.AsciiStyle())}" )
                    
            self._confstoparent = newconfstoparent
            # if no parent was found on this run through confstoparent, give up with the confs to parent preserved
            if not foundparent:
                if verbose:
                    print( f"\nPostponing potentially unparentable configs {self._confstoparent}" )
                break
            
        if verbose:
            print( "" )
            
        return result

    def load_configtree( self, *, fromconfig_u=None, loadbaselines=False, followsubstreams=False, loadchangesets=False, alwayscaching=False ):
        # show the config tree
        print( f"tree= {anytree.RenderTree(self.configTree, style=anytree.AsciiStyle())}" )
        print( f"{self.configTree=}" )
        print( f"{self.configTree.children=}" )
        if not fromconfig_u:
            fromconfig_u = self.configTree.children[0].name
#            print( f"{fromconfig_u=}" )
        startnode = anytree.search.find( self.configTree, filter_=lambda n: n.name==fromconfig_u )

        for conf in anytree.iterators.preorderiter.PreOrderIter( startnode ):
            # load the typesystem for this node
            if conf is None or conf.name is None or not conf.name.startswith( 'http'):
    #            print( f"Ignoring {conf}" )
                continue
            if conf.conftype == "Changeset" and not loadchangesets:
                continue
            if conf.conftype == "Baseline":
                if not loadbaselines and not followsubstreams and conf.name != fromconfig_u:
                    # remember the substreams and come back to load them
                    continue
                if not loadbaselines:
                    continue
                
#            print( f"------------------------------\n'{conf.title}' {conf.ismutable=} {conf.created} {conf.name}" )
#            print( f"{conf.children=}" )
            self.set_local_config(conf.name)
    #        continue
            # GET the typesystem - caching is determinded by ismutable
    #typeresources = {
    #    'http://jazz.net/ns/rm/dng/types#ArtifactType':        ('ArtifactType'       ,'OT'), 
            return
            for resourcetype,typedetails in typeresources.items():
                # QUERY to get the types
    #            print( f"Getting {typedetails[0]} {typedetails[1]=}" )
#                print( f"{alwayscaching or not conf.ismutable=}" )
                results = self.do_complex_query( resourcetype, querystring=None, select="*",show_progress=False,cacheable=alwayscaching or not conf.ismutable )
    #            print( f"{results=}" )
                for k,v in results.items():
    #                print( f"  result {k=} {v=}" )
                    if not self.app.is_server_uri( k ):
                        # ignore non-local references
#                        print( f"Ignoring non-local {typedetails[1]} {k}" )
                        continue
                    if typedetails[1]=='OT':
                        # find the attributes and record them
                        conf.typesystem.load_ot( self, k, iscacheable=alwayscaching or not conf.ismutable, isused=True )
                    elif typedetails[1]=='AD':
                        conf.typesystem.load_ad( self, k, iscacheable=alwayscaching or not conf.ismutable, isused=False )
                    elif typedetails[1]=='AT':
#                        print( f"Loading AT {k=}" )
                        conf.typesystem.load_at( self, k, iscacheable=alwayscaching or not conf.ismutable, isused=False )
                    elif typedetails[1]=='LT':
#                        print( f"Loading LT {k=}" )
                        conf.typesystem.load_lt( self, k, iscacheable=alwayscaching or not conf.ismutable, isused=False )
                    else:
                        raise Exception( f"Unkown type {typedetails[1]}" )


    def get_local_config(self, name_or_uri, global_config_uri=None, verbose=False, incremental=False ):
        logger.info( f"GLC {self=} {name_or_uri=}" )
#        print( f"GLC {self=} {name_or_uri=} {global_config_uri=}" )
        if global_config_uri:
            # gc and local config both specified - try to avoid loading all the local configs by using the gc tree to locate the local config
            gc_contribs = self.get_gc_contributions(global_config_uri)
            # find the contribution for this component
            config_uri = None
            for config in gc_contribs['configurations']:
#                print( f"Checking {config=} for {self.project_uri=}" )
                if config['componentUri'] == self.project_uri:
                    config_uri = config['configurationUri']
            if not config_uri:
                raise Exception( 'Cannot find configuration [%s] in project [%s]' % (name_or_uri, self.uri))
            result = config_uri
        else:
            result = None
            filter = None
            if name_or_uri.startswith("S:"):
                filter="Stream"
                name_or_uri = name_or_uri[2:]
            elif name_or_uri.startswith("B:"):
                filter="Baseline"
                name_or_uri = name_or_uri[2:]
            elif name_or_uri.startswith("C:"):
                filter="ChangeSet"
                name_or_uri = name_or_uri[2:]

            while result is None:
                for cu, cd in self._configurations.items():
    #                print( f"{cu=} {cd=}" )
                    if filter and cd['conftype'] != filter:
                        continue
                    if cu == name_or_uri or cd['name'] == name_or_uri:
                        if result:
                            raise Exception( f"Config {name_or_uri} isn't unique - you could try prefixing it with S: for stream, B: for baseline, or C: for changeset")
                        result = cu
                if result is None:
                    if not self.load_configs( stopatnameoruri=name_or_uri, verbose=verbose, incremental=incremental ):
                        # config not found - give up (if found, this loops back to scan for the config again
                        break
#        print( f"GLC {result} {self=} {name_or_uri=}" )
                    
        return result

    def list_configs( self ):
        configs = []
        self.load_configs()
        for cu, cd in self._configurations.items():
#            print(cd)
            configs.append( cd )

        return configs

    # for RM, load the typesystem using the OSLC shape resources listed for the Requirements and Requirements Collection creation factories
    def _load_types(self,force=False):
        logger.debug( f"load type {self=} {force=}" )
          
        # if already loaded, try to avoid reloading
        if self.typesystem_loaded and not force:
            return

        self.clear_typesystem()

        if self.local_config:
            # get the configuration-specific services.xml
            sx = self.get_services_xml(force=True,headers={'Configuration.Context': self.local_config, 'net.jazz.jfs.owning-context': None})
        else:
            # No config - get the services.xml
            sx = self.get_services_xml(force=True)
        if sx:
            shapes_to_load = rdfxml.xml_find_elements(sx, './/oslc:resourceShape' )
            
            pbar = tqdm.tqdm(initial=0, total=len(shapes_to_load),smoothing=1,unit=" results",desc="Loading DN shapes")

            for el in shapes_to_load:
                self._load_type_from_resource_shape(el)
                pbar.update(1)

            pbar.close()

        else:
            raise Exception( "services xml not found!" )
        self.typesystem_loaded = True

        return None

    # pick all the attributes from a resource shape definition
    # and for enumerated attributes get all the enumeration values
    def _load_type_from_resource_shape(self, el, supershape=None):
        uri = el.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
        logger.info( f"Loading shape URI {uri}" )
#        print( f"Loading shape URI {uri}")
        try:
            if not self.is_known_shape_uri(uri):
                logger.info( f"Starting shape {uri} =======================================" )
                logger.debug( f"Getting {uri}" )
                shapedef = self._get_typeuri_rdf(uri)
                # find the title
                nameel = rdfxml.xml_find_element(shapedef, './oslc:ResourceShape/dcterms:title')
                if nameel is None:
                    nameel = rdfxml.xml_find_element(shapedef, './oslc:ResourceShape/rdfs:label')
                name = nameel.text
                rdfuri = rdfxml.xmlrdf_get_resource_uri( shapedef, ".//owl:sameAs" )
#                print( f"Registering shape {name=} {uri=} {rdfuri=}" )
                self.register_shape( name, uri )
                logger.info( f"Opening shape {name} {uri}" )
            else:
 
                return
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.info( f"Failed because type not found 404 - ignoring! {e}")
                return
            elif e.response.status_code == 410:
                logger.info( f"Failed because type not found 410 - ignoring! {e}")
                return
            else:
                raise

        # register this shape as an oslc_instanceShape enum
        # ensure the oslc:instanceShape property is defined (but don't overwrite existing definition)
        self.register_property( 'oslc:instanceShape', 'oslc:instanceShape', do_not_overwrite=True )
        # add the shape to it using the shape's URI as an enum URI
        self.register_enum( name, uri, 'oslc:instanceShape')

        n = 0
        # scan the attributes/properties
        for el in rdfxml.xml_find_elements(shapedef, './/oslc:Property/dcterms:title/..'):
            property_title = rdfxml.xml_find_element(el, 'dcterms:title').text
            propuri = rdfxml.xml_find_element(el, 'oslc:propertyDefinition').get( "{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
            proptype = rdfxml.xmlrdf_get_resource_uri(el,'oslc:valueType' )

            if self.is_known_property_uri( propuri ):
                logger.debug( f"ALREADY KNOWN" )
                continue

            # get the property definition
            # a link has a Reference oslc:representation
            if rdfxml.xml_find_element( el, "oslc:representation[@rdf:resource='http://open-services.net/ns/core#Reference']") is not None:
                if propuri is not None:
                # this could be a link type or an attribute datatype reference
                # confirm this is a link type by checking for oslc:representation rdf:resource="http://open-services.net/ns/core#Reference"

                    # record the link type in the typesystem
                    if propuri.startswith( self.reluri() ):
                        linktype_x = self._get_typeuri_rdf(propuri)
                        label = rdfxml.xml_find_element(linktype_x, './/rdfs:label').text
                        ilabel = rdfxml.xml_find_element(linktype_x, './/rdfs:inverseLabel')
                        inverselabel = ilabel.text if ilabel is not None else None
                        rdfuri = None
                    else:
                        rdfuri = propuri
                        label = property_title
                        inverselabel = None

                    self.register_linktype( property_title, propuri, label, inverselabel=inverselabel, rdfuri=rdfuri, shape_uri=uri )
            logger.info( f"Defining property {name}.{property_title} {propuri=} +++++++++++++++++++++++++++++++++++++++" )
#            print( f"Defining property {name}.{property_title} {propuri=} {uri=} +++++++++++++++++++++++++++++++++++++++" )
#            self.register_property(property_title,propuri, shape_uri=uri)
            self.register_property(property_title,propuri)
            # load the attribute definitions
            n += 1
            for range_el in rdfxml.xml_find_elements(el, 'oslc:range'):
                range_uri = range_el.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])

                if not range_uri.startswith( self.app.baseurl):
                    logger.info( f"EXTERNAL {range_uri=}" )

                if True or range_uri.startswith(self.app.baseurl):
                    # retrieve all the enum value definitions
                    try:
                        range_xml = self._get_typeuri_rdf(range_uri)
                        if range_xml is not None:
                            # now process any enumeration values
                            for enum_el in rdfxml.xml_find_elements(range_xml, './/rdf:Description/rdfs:label/..'):
                                enum_uri = enum_el.get("{%s}about" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
                                enum_value_name = rdfxml.xml_find_element(enum_el, 'rdfs:label').text
                                enum_value_el = rdfxml.xml_find_element(enum_el, 'rdf:value')

                                if enum_value_el is not None:
                                    enum_value = enum_value_el.text

                                    logger.info( f"defining enum value {enum_value_name=} {enum_uri=}" )
                                    self.register_enum( enum_value_name, enum_uri, property_uri=propuri )
                    except requests.exceptions.HTTPError as e:
                        pass
        return n

    # return a dictionary with all local component uri as key and name as value (so two components could have the same name?)
    def get_local_component_details(self):
        results = {}
        for compuri, compdetail in self._components.items():
            results[compuri] = compdetail['name']
        return results


    def find_local_component(self, name_or_uri, oneshot=True):
        comps = list()
        self.load_components_and_configurations()
        for compuri, compdetail in self._components.items():
            #print(compuri, compdetail)
            if (compuri == name_or_uri or compdetail['name'] == name_or_uri) and oneshot is True:
                return compdetail['component']
            comps.append(compdetail)
        return comps

    def list_components( self ):
        # list all the component names
        self.load_components_and_configurations()
        components = []
        for compuri, compdetail in self._components.items():
            if compdetail.get('name'):
                components.append( compdetail.get('name') )
        return components

    def _create_component_api(self, component_prj_url, component_name, confs_to_load):
        logger.info( f"CREATE RM COMPONENT {self=} {component_prj_url=} {component_name=} {self.app=} {self.is_optin=} {self.singlemode=}" )
        result = RMComponent(component_name, component_prj_url, self.app, self.is_optin, self.singlemode, defaultinit=False, project=self)
        result.confs_to_load = confs_to_load
        return result

    # for OSLC query, given a type URI, return its name
    # rm-specific resolution
    def app_resolve_uri_to_name(self, uri):
        if self.is_folder_uri(uri):
            result = self.folder_uritoname_resolver(uri)
        elif self.is_resource_uri(uri):
            result = self.resource_id_from_uri(uri)
        elif self.is_type_uri(uri):
            result = self.type_name_from_uri(uri)
        else:
            result = None
        return result

    def is_type_uri(self, uri):
        if uri and uri.startswith(self.app.baseurl) and '/types/' in uri:
            return True
        return False

    # for OSLC query, given a type URI, return the type name
    def type_name_from_uri(self, uri):
        logger.info( f"finding type name {uri}" )
        if self.is_type_uri(uri):
            try:
                # handle artifact formats (these don't have a title or label in the returned XML)
                if match:=re.search("#([a-zA-Z0-9_]+)$",uri ):
                    id = match.group(1)
                else:
                    # retrieve the definition
                    resource_xml = self.execute_get_rdf_xml(reluri=uri, intent="Retrieve type RDF to get its name")
                    # check for a rdf label (used for links, maybe other things)
                    id = rdfxml.xmlrdf_get_resource_text(resource_xml,".//rdf:Property/rdfs:label") or rdfxml.xmlrdf_get_resource_text(resource_xml,".//oslc:ResourceShape/dcterms:title") or rdfxml.xmlrdf_get_resource_text(resource_xml,f'.//rdf:Description[@rdf:about="{uri}"]/rdfs:label') or rdfxml.xmlrdf_get_resource_text(resource_xml,f'.//dng_types:LinkType/rdfs:label')
                    if id is None:
                        id = f"STRANGE TYPE {uri}"
                        raise Exception( f"No type for {uri=}" )
            except requests.HTTPError as e:
                if e.response.status_code==404:
                    logger.info( f"Type {uri} doesn't exist!" )
                    raise
                else:
                    raise
            return id
        raise Exception(f"Bad type uri {uri}")

    def is_resource_uri(self, uri):
        if uri and uri.startswith(self.app.baseurl) and '/resources/' in uri:
            return True
        return False

    # for OSLC query, given a resource URI, return the requirement dcterms:identifier
    def resource_id_from_uri(self, uri):
        if self.is_resource_uri(uri):
            try:
                resource_xml = self.execute_get_rdf_xml(reluri=uri, intent="Retrieve type RDF to get its id (dcterms:identifier)")
            except requests.HTTPError as e:
                if e.response.status_code==410:
                    logger.info( f"Type {uri} doesn't exist!" )
                    print( f"Error retrieving URI, probably a reference outside the component, i.e. it's in a different (unknown) configuration - ignored {uri}" )
                    return None
                else:
                    raise
            id = rdfxml.xmlrdf_get_resource_text(resource_xml, ".//dcterms:identifier")
            return id
        raise Exception(f"Bad resource uri {uri}")

    def is_folder_uri(self, uri):
        if uri and uri.startswith(self.app.baseurl) and '/folders/' in uri:
            return True
        return False
    # {'https://jazz.ibm.com:9443/rm/resources/BI_STtIxNd8EeqV5_5cfWW9rw': {}, 'https://jazz.ibm.com:9443/rm/resources/TX_SRBoRdd8EeqV5_5cfWW9rw': {'rm_nav:parent': 'https://jazz.ibm.com:9443/rm/folders/FR_SS9iOdd8EeqV5_5cfWW9rw'}}

    def resolve_reqid_to_core_uri( self, reqid ):
        # get the query capability base URL
        qcbase = self.get_query_capability_uri("oslc_rm:Requirement")
        results = self.execute_oslc_query( qcbase, whereterms=[['dcterms:identifier','=',str(reqid)]],select=['rm_nav:parent'], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rm_nav"]:'rm_nav'})
        logger.debug( f"{results=}" )
        if len( results.keys() ) == 0:
            result = None
        else:
            # need to find the entry with a non-empty rm_nav:parent - that's the core artifact
            result = None
            for k in results.keys():
                if results[k].get('rm_nav:parent',None):
                    if not result:
                        result = k
                    else:
                        raise Exception( f"More than one core artifact returned for id {reqid}!" )
        return result

    def resolve_reqid_to_module_uris( self, reqid ):
        # get the query capability base URL
        qcbase = self.get_query_capability_uri("oslc_rm:Requirement")
        results = self.execute_oslc_query( qcbase, whereterms=[['dcterms:identifier','=',str(reqid)]],select=['rm_nav:parent'], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["rm_nav"]:'rm_nav'})
        logger.debug( f"resolve_reqid_to_module_uris {results=}" )
        if len( results.keys() ) == 0:
            requris = None
        else:
            # need to find the entrs with a empty rm_nav:parent - these are module artifacts
            requris = []
            for k in results.keys():
                if results[k].get('rm_nav:parent',None) is None:
                    requris.append(k)
        return requris

    def resolve_modulename_to_uri( self, modulename ):
        # get the query capability base URL
        qcbase = self.get_query_capability_uri("oslc_rm:Requirement")
        results = self.execute_oslc_query( qcbase, whereterms=[['and', ['dcterms:title','=',f'"{modulename}"'],['rdf:type','=','jazz_rm:Module']]], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]:'jazz_rm'})
        logger.debug( f"resolve_modulename_to_uri {results=}" )
        if len( results.keys() ) == 0:
            result = None
        else:
            if len( results.keys() ) > 1:
                raise Exception( f"More than one module named {modulename}!" )
            result = list(results.keys())[0]
            logger.info( f"rmtu {result=}" )
        return result

#    def resolve_configname_to_uri( self, configname ):
        # configname syntax is domain/project/component/config
        # for example (remove the')  'rm:rm23/rm_optin_p1/rm_optin_p1 comp2/rm_optin_p1 comp2 Initial Stream'
#        # get the query capability base URL
#        qcbase = self.get_query_capability_uri("oslc_rm:Requirement")
#        results = self.execute_oslc_query( qcbase, whereterms=[['and', ['dcterms:title','=',f'"{modulename}"'],['rdf:type','=','jazz_rm:Module']]], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]:'jazz_rm'})
#        logger.debug( f"resolve_modulename_to_uri {results=}" )
#        if len( results.keys() ) == 0:
#            result = None
#        else:
#            if len( results.keys() ) > 1:
#                raise Exception( f"More than one module named {modulename}!" )
#            result = list(results.keys())[0]
#            logger.info( f"rmtu {result=}" )
#        return result


    def resolve_uri_to_reqid( self, requri ):
        pass

    def folder_nametouri_resolver(self, path_or_uri):
        logger.debug( f"Finding uri {path_or_uri}" )
        if self.is_folder_uri(path_or_uri):
            return path_or_uri
        name = self._load_folders(path_or_uri)
        if name is not None:
            return name
        if path_or_uri in self._folders:
            return self._folders[path_or_uri].folderuri
        raise Exception(f"Folder name {path_or_uri} not found")

    def folder_uritoname_resolver(self,uri):
        logger.debug( f"Finding name {uri}" )
        if not self.is_folder_uri(uri):
            raise Exception( "Folder uri isn't a uri {uri}" )
        thisfolder = self._load_folders(uri)
        if thisfolder is not None:
            return thisfolder.pathname
        logger.info( f"Folder uri {uri} not found")
        return uri

    def _do_find_config_by_name(self, name_or_uri, nowarning=False, include_workspace=True, include_snapshot=True,
                                include_changeset=True):
        if name_or_uri.startswith('http'):
            return name_or_uri
        return self.get_local_config(name_or_uri)

    def get_default_stream_name( self ):
        if self.is_optin and not self.singlemode:
            raise Exception( "Not allowed if compontn is not singlemode!" )
        for configuri,configdetails in self._configurations.items():
            if configdetails['conftype'] == 'Stream':
                return configuri
        raise Exception( "No stream found!" )

#################################################################################################

class RMComponent( RMProject, resource.Resources_Mixin ):
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True, project=None):
        if not project:
            raise Exception( "You must provide a project instance when creating a component" )
        super().__init__(name, project_uri, app, is_optin,singlemode,defaultinit=defaultinit)
        self.component_project = project
        self.services_uri = project.services_uri    # needed for reqif which wants to put the services.xml URI into created XML for new definitions
        self._iscomponent=True

    # this is a bit primitive but works well enough for now
    def getconfigtype( self, configuri ):
        if '/baseline/' in configuri:   return "Baseline"
        if '/stream/' in configuri:     return "Stream"
        if '/changeset/' in configuri:  return "Changeset"
        raise Exception( f"Config URL {configuri} not valid!" )

    # create a changeset in the current config (must be a stream)
    def create_changeset( self, name, noexception=False ):
        # make sure config is a stream
        if self.getconfigtype( self.local_config ) != 'Stream' :
            raise Exception( "Can't create CS if not in stream!" )

        # make sure name doesn't already exist amywhere in this component!
        if self.find_config( name, nowarning=True) is not None:
            if noexception:
                return None
            raise Exception( "CS name already exists!" )

        # create the changeset - it's up to the caller to select it as current config
        # get the current stream
        stream_x = self.execute_get_rdf_xml( self.local_config )
#        print( f"{stream_x=}" )
        # find the changesets URL
        cs_u = rdfxml.xmlrdf_get_resource_uri( stream_x, ".//rm_config:changesets" )
        comp_u = rdfxml.xmlrdf_get_resource_uri( stream_x, './/oslc_config:component' )
#        print( f"{cs_u=}" )
#        print( f"{comp_u=}" )
        # create a new CS by POST
        body = f"""<rdf:RDF
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:oslc="http://open-services.net/ns/core#"
    xmlns:oslc_config="http://open-services.net/ns/config#"
    xmlns:acc="http://open-services.net/ns/core/acc#"
    xmlns:process="http://jazz.net/ns/process#">
  <oslc_config:Configuration  rdf:about="https://laptop-e95ocmuv:9443/rm/cm/changeset/something">
    <oslc_config:component rdf:resource="{comp_u}"/>
    <dcterms:title rdf:parseType="Literal">{name}</dcterms:title>
  </oslc_config:Configuration>
</rdf:RDF>"""

        response = self.execute_post_rdf_xml( cs_u, data=body, headers={'Content-Type': 'application/rdf+xml', 'OSLC-Core-Version':'2.0'}, intent="Initiate changeset creation" )

        location = response.headers.get('Location')
        if response.status_code == 201:
            pass
        elif response.status_code == 202 and location is not None:
            # wait for the tracker to finished
            result = self.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Waiting for changeset creation to complete")
            if result is None:
                raise Exception( f"No result from tracker!" )
        else:
            raise Exception( f"Unknown response {response.status_code}" )

        cs = rdfxml.xmlrdf_get_resource_uri( result, './/dcterms:references')

        return cs

    def discard_changeset( self ):
        raise Exception( "Discard changeset not implemented yet!" )

    # deliver changeset and forget it
    def deliver_changeset( self ):
        raise Exception( "unfinished/untested!" )
        # check we're in a changeset
        if self.getconfigtype( self.local_config ) != 'Changeset' :
            raise Exception( f"Can't deliver CS if not in CS! Current config is {self.local_config}" )

        # get the target stream from the changeset
        cs_x = self.execute_get_rdf_xml( self.local_config )
        stream_u = rdfxml.xmlrdf_get_resource_uri( cs_x, './/oslc_config:overrides' )
        csname = rdfxml.xmlrdf_get_resource_text( cs_x, './/dcterms:title' )
#        print( f"target {stream_u=}" )
#        print( f"cs name {csname=}" )
        # find the delivery session factory
        ds_f_u = self.get_factory_uri("rm_config:DeliverySession" )
#        print( f"{ds_f_u=}" )
#        print( f"{self.services_uri=}" )
        # create the content
        body=f"""<rdf:RDF
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:rm_config="http://jazz.net/ns/rm/dng/config#"
    xmlns:oslc="http://open-services.net/ns/core#">
  <rm_config:DeliverySession>
    <oslc:serviceProvider rdf:resource="{self.services_uri}"/>
    <rm_config:source rdf:resource="{self.local_config}"/>
    <rm_config:target rdf:resource="{stream_u}"/>
    <dcterms:title rdf:parseType="Literal">Delivery session for cs {csname}</dcterms:title>
  </rm_config:DeliverySession>
</rdf:RDF>
"""

        # switch to the target config
        self.local_config = stream_u

        # create the delivery session
        response = self.execute_post_rdf_xml( ds_f_u, data=body,headers={'Content-Type': 'application/rdf+xml', 'OSLC-Core-Version':'2.0'}, intent="Create delivery session" )
        location = response.headers.get('Location')
        if response.status_code == 201:
            ds_u = location
        else:
            raise Exception( f"Unknown response {response.status_code}" )
#        print( f"{ds_u=}" )

        # deliver it by first retrieving the delivery session then putting it back with a different state
        ds_x = self.execute_get_rdf_xml( ds_u )
        # set rm_config:deliverySessionState to rm_config:delivered
        state_x = rdfxml.xml_find_element( ds_x, ".//rm_config:deliverySessionState" )
#        print( f"{state_x=}" )
#        print( f"{state_x.items()=}" )
#        print( f'{rdfxml.tag_to_uri("rdf:resource")=}' )
#        print( f'{rdfxml.tag_to_uri( "rm_config:delivered" )=}' )
        state_x.set(rdfxml.uri_to_tag("rdf:resource"), rdfxml.tag_to_uri( "rm_config:delivered" ) )
#        print( f"{state_x.items()=}" )
        # PUT the new state to start delivery
        response = self.execute_post_rdf_xml( ds_u, data=ds_x,headers={'Content-Type': 'application/rdf+xml', 'OSLC-Core-Version':'2.0'}, intent="Start the delivery", put=True )
        location = response.headers.get('Location')
        if response.status_code == 200:
            state = rdfxml.xmlrdf_get_resource_uri( response, ".//rm_config:deliverySessionState" )
#            print( f"{state=}" )
        elif response.status_code == 202:
            # wait for the tracker to finished
            result = self.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Waiting for changeset delivery to complete")
            if result is None:
                raise Exception( f"No result from tracker!" )
#            print( f"{result=}" )
#            print( ET.tostring(result) )
            state = rdfxml.xmlrdf_get_resource_uri( result, './/oslc_auto:verdict ')
        else:
            raise Exception( f"Unknown response {response.status_code}" )
        print( f"tracker result {state=}" )

        self.local_config = None
        # TODO: how to remove the delivered changeset from known configs?


#################################################################################################

@utils.mixinomatic
class RMApp (_app._App, oslcqueryapi._OSLCOperations_Mixin, _typesystem.Type_System_Mixin ):
    domain = 'rm'
    project_class = RMProject
    supports_configs = True
    supports_components = True
    supports_reportable_rest = True
    reportablerestbase='publish'
    reportable_rest_status = "Supported by application and implemented here"
    artifact_formats = [ # For RR
            'collections'
            ,'comments'
            ,'comparison'  # new for 7.0.2
            ,'linktypes'
            ,'modules'
            ,'processes'
            ,'resources'
            ,'reviews'
            ,'revisions'
            ,'screenflows'
            ,'storyboards'
            ,'terms'
            ,'text'
            ,'uisketches'
            ,'usecasediagrams'
            ,'views'
        ]
    identifier_name = 'Identifier'
    identifier_uri = 'dcterms:identifier'

    def __init__(self, server, contextroot, jts=None):
        super().__init__(server, contextroot, jts=jts)
        self.rootservices_xml = self.execute_get_xml(self.reluri('rootservices'), intent="Retrieve RM application rootservices", action="Locate project areas URL using tag jp06:projectAreas" )
        self.serviceproviders = 'oslc_rm_10:rmServiceProviders'
        self.version = rdfxml.xmlrdf_get_resource_text(self.rootservices_xml,'.//oslc_rm_10:version')
        self.majorversion = rdfxml.xmlrdf_get_resource_text(self.rootservices_xml,'.//oslc_rm_10:majorVersion')
#        self.reportablerestbase = 'publish'
        self.rmcmServiceProviders = "oslc:details"
        self.default_query_resource = 'http://open-services.net/ns/config#Configuration' # pre-7.1 RM didn't provide any app-level queries

        logger.info( f"Versions {self.majorversion} {self.version}" )

    def _get_headers(self, headers=None):
        logger.info( f"rm gh {headers=}" )
        result = super()._get_headers()
#        result['net.jazz.jfs.owning-context'] = self.baseurl
        if headers:
            result.update(headers)
        logger.info( f"rmapp_gh {result}" )
        logger.info( f"rm gh {result=}" )
        return result

    def find_pa_comp_from_config( self, configurl ):
        # get the config - find the pa and component from the result
        # used whan a GC has a contribution URL from rm, to find the rm pa and component - then we can create a project and component object
        config_x = self.execute_get_rdf_xml( configurl )
        pa_u = rdfxml.xmlrdf_get_resource_uri( config_x, ".//process:projectArea" )
        comp_u = rdfxml.xmlrdf_get_resource_uri( config_x, ".//oslc_config:component" )
        return (pa_u,comp_u)
        
    # load the typesystem using the OSLC shape resources listed for all the creation factories and query capabilities
    def load_types(self, force=False):
        self._load_types(force)

    # load the typesystem using the OSLC shape resources
    def _load_types(self,force=False):
        logger.debug( f"load type {self=} {force=}" )

        # if already loaded, try to avoid reloading
        if self.typesystem_loaded and not force:
            return

        self.clear_typesystem()

        # get the services.xml
        sx = self.retrieve_oslc_catalog_xml()
        if sx:
            shapes_to_load = rdfxml.xml_find_elements(sx, './/oslc:resourceShape')
#            print( f"{shapes_to_load=}" )

            pbar = tqdm.tqdm(initial=0, total=len(shapes_to_load),smoothing=1,unit=" results",desc="Loading ERM/DN shapes")

            for el in shapes_to_load:
                self._load_type_from_resource_shape(el)
                pbar.update(1)

            pbar.close()
        else:
            raise Exception( "services xml not found!" )

        self.typesystem_loaded = True
        return None

    # RM has to find app-wide query capabilities differently from ETM/GCM - the XML with the QueryCapability is in the component RDF
    # see https://jazz.net/wiki/bin/view/Main/DNGOSLCConfigurationQueryCapabilityOverview
    def retrieve_rm_cm_service_provider_xml(self):
        cm_service_provider_uri = rdfxml.xmlrdf_get_resource_uri( self.rootservices_xml, self.cmServiceProviders )
        rdfcomponent = self.execute_get_rdf_xml( cm_service_provider_uri, intent="Retrieve application CM Service Provider" )
        rm_cm_service_provider_uri = rdfxml.xmlrdf_get_resource_uri( rdfcomponent, f".//{self.rmcmServiceProviders}" )
        rdf = self.execute_get_rdf_xml( rm_cm_service_provider_uri, intent="Retrieve RM CM Service Provider" )
        return rdf

    def get_query_capability_uri(self,resource_type=None,context=None):
        context = context or self
        resource_type = resource_type or context.default_query_resource
        return self.get_query_capability_uri_from_xml( capabilitiesxml=context.retrieve_rm_cm_service_provider_xml(), resource_type=resource_type, context=context )

    # given a type URI, return its name
    def resolve_uri_to_name(self, uri, prefer_same_as=True, dontpreferhttprdfrui=True):
        logger.info( f"resolve_uri_to_name {uri=}" )
        if not uri:
            result = None
            return result
        if not uri.startswith('http://') or not uri.startswith('https://'):
        # try to remove prefix
            uri1 = rdfxml.tag_to_uri(uri,noexception=True)
            logger.debug(f"Trying to remove prefix {uri=} {uri1=}")
            if uri1 is None:
                return uri
            if uri1 != uri:
                logger.debug( f"Changed {uri} to {uri1}" )
            else:
                logger.debug( f"NOT Changed {uri} to {uri1}" )
            # use the transformed URI
            uri = uri1
        if not uri.startswith(self.reluri()):
            if self.server.jts.is_user_uri(uri):
                result = self.server.jts.user_uritoname_resolver(uri)
                logger.debug(f"returning user")
                return result
            uri1 = rdfxml.uri_to_prefixed_tag(uri,noexception=True)
            logger.debug(f"No app base URL {self.reluri()=} {uri=} {uri1=}")
            return uri1
        elif not self.is_known_uri(uri):
            if self.server.jts.is_user_uri(uri):
                result = self.server.jts.user_uritoname_resolver(uri)
            else:
                if uri.startswith( "http://" ) or uri.startswith( "https://" ):
                    uri1 = rdfxml.uri_to_prefixed_tag(uri)
                    logger.debug( f"Returning the raw URI {uri} so changed it to prefixed {uri1}" )
                    uri = uri1
                result = uri
            # ensure the result is in the types cache, in case it recurrs the result can be pulled from the cache
            self.register_name(result,uri)
        else:
            result = self.get_uri_name(uri)
        logger.info( f"Result {result=}" )
        return result

    @classmethod
    def add_represt_arguments( cls, subparsers, common_args ):
        '''
        NOTE this is called on the class (i.e. is a class method) because at this point don't know which app with be queried
        '''
        parser_rm = subparsers.add_parser('rm', help='RM Reportable REST actions', parents=[common_args] )

        parser_rm.add_argument('artifact_format', choices=cls.artifact_formats, default=None, help=f'RM artifact format - possible values are {", ".join(cls.artifact_formats)}')

        # SCOPE settings
        parser_rm.add_argument('-p', '--project', default=None, help='Scope: Name of project - required when using module/collection/view/resource/typename ID/typename as a filter')
        parser_rm.add_argument('-c', '--component', default=None, help='Scope: Name of component - required when using module/collection/view/resource/typename ID/typename as a filter')
        parser_rm.add_argument('-g', '--globalconfiguration', default=None, help='Scope: Name or ID of global config (make sure you define gc in --appstring!) - to use this you need to provide the project')
        parser_rm.add_argument('-o', '--globalproject', default=None, help='Scope: Name of GC project (make sure you define gc in --appstring!)')
        parser_rm.add_argument('-l', '--localconfiguration', default=None, help='Scope: Name of local config - you need to provide the project - defaults to the "Initial Stream" or "Initial Development" +same name as the project - if name is ambiguous specify a stream using "S:Project Initial Stream", a baseline using "B:my baseline", or changeset using "C:changesetname"')
        parser_rm.add_argument('-e', '--targetconfiguration', default=None, help='Scope: Name of target configuration when using artifact_format comparison - see description of --localconfiguration for how to disambiguate names')

        # Source Filters - only use one of these at once - all require a project and configuration!
        rmex1 = parser_rm.add_mutually_exclusive_group()
        rmex1.add_argument('-n', '--collection', default=None, help='Sub-scope: RM: Name or ID of collection - you need to provide the project and local/global config')
        rmex1.add_argument('-m', '--module', default=None, help='Sub-scope: RM: Name or ID of module - you need to provide the project and local/global config')

        rmex2 = parser_rm.add_mutually_exclusive_group()
        rmex2.add_argument('-v', '--view', default=None, help='Sub-scope: RM: Name of view - you need to provide the project and local/global config')
        rmex2.add_argument('-q', '--moduleResourceID', default=None, help='Sub-scope: RM: Comma-separated IDs of module resources - you need to provide the project and local/global config')
        rmex2.add_argument('-r', '--resourceID', default=None, help='Sub-scope: RM: Comma-separated IDs of core or module resources - you need to provide the project and local/global config')
        rmex2.add_argument('-s', '--coreResourceID', default=None, help='Sub-scope: RM: Comma-separated IDs of core resources - you need to provide the project and local/global config')
        rmex2.add_argument('-t', '--typename', default=None, help='Sub-scope: RM: Name of type - you need to provide the project and local/global config')

        # Output FILTER settings - only use one of these at once
        parser_rm.add_argument('-a', '--all', action="store_true", help="Filter: Report all resources")
        parser_rm.add_argument('-d', '--modifiedsince', default=None, help='Filter: only return items modified since this date - NOTE this is only for DCC ETL! Date must be in ISO 8601 format like 2021-01-31T12:34:26Z')
        parser_rm.add_argument('-x', '--expandEmbeddedArtifacts', action="store_true", help="Filter: Expand embedded artifacts")

        # Output controls - only use one of these at once!
        rmex3 = parser_rm.add_mutually_exclusive_group()
        rmex3.add_argument('--attributes', default=None, help="Output: Comma separated list of attribute names to report (requires specifying project and configuration)")
        rmex3.add_argument('--schema', action="store_true", help="Output: Report the schema")
        rmex3.add_argument('--titles', action="store_true", help="Output: Report titles")
        rmex3.add_argument('--linksOnly', action="store_true", help="Output: Report links only")
        rmex3.add_argument('--history', action="store_true", help="Output: Report history")
        rmex3.add_argument('--coverPage', action="store_true", help="Output: Report cover page variables")
        rmex3.add_argument('--signaturePage', action="store_true", help="Output: Report signature page variables")

    def process_represt_arguments( self, args, allapps ):
        '''
        Process above arguments, returning a dictionayt of parameters to add to the represt base URL
        NOTE this does have some dependency on thje overall

        NOTE this is called on an instance (i.e. not a class method) because by now we know which app is being queried
        '''
        queryparams = {}
        queryurl = ""
        queryheaders={}

        if not hasattr( args, 'artifact_format' ):
            raise Exception( "FAILED - you must specify an application such as rm" )

        if args.artifact_format=="comparison":
            if not args.project or not args.localconfiguration or not args.targetconfiguration:
                raise Exception( "Comparison requires a project, explicit local configuration as the source and explicit target configuration" )

#        if args.artifact_format=="views":
#            if not args.project or (not args.module and not args.resourceID and not args.moduleResourceID and not args.coreResourceID) or not args.view:
#                raise Exception( "Using artifact_format views you MUST also specify project (and config if opt-in), a view, and either a module or a resource ID" )

        gcproj = None
        gcconfiguri = None
        gcapp = allapps.get('gc',None)
        if not gcapp and args.globalconfiguration:
            raise Exception( "gc app must be specified in APPSTRINGS/-A (after the rm app) to use a global configuration - for exmaple use -A rm,gc" )

        # most queries need a project and configuration - projects queried without a config will return data from the default configuraiotn (the default component's initial stream)
        if args.all or args.collection or args.module or args.view or args.typename or args.resourceID or args.moduleResourceID or args.coreResourceID or args.schema or args.attributes or args.titles or args.linksOnly or args.history or args.artifact_format=='views':
            if not args.project:
                raise Exception( "Project and probably local or global config needed!" )

        if args.project:
            # find the project
            p = self.find_project(args.project)
            if p is None:
                raise Exception( f"Project '{args.project}' not found")

            queryparams['projectURI']=p.iid

            if p.singlemode and args.globalconfiguration:
                raise Exception( "Don't specify a global configuration for an opt-out project" )

            if p.is_optin and not args.component:
                args.component = args.project

            if args.globalconfiguration:
                # now find the configuration config
                # user can specify just an id
                if utils.isint(args.globalconfiguration):
                    # create GC URI using the id
                    gcconfiguri = gcapp.reluri( f"configuration/{args.globalconfiguration}" )
                else:
                    if args.globalconfiguration.startswith( 'http://') or args.globalconfiguration.startswith( 'https://' ):
                        if args.globalconfiguration.startswith( gcapp.reluri( "configuration" ) ):
                            # assume user specified a URI
                            gcconfiguri = args.globalconfiguration
                        else:
                            raise Exception( f"The -G globalconfiguration {args.globalconfiguration} isn't an integer id and doesn't start with the server gc path {gcapp.reluri( 'configuration' )}" )
                    else:
                        # do an OSLC query on either the GC app or the GC project
                        if args.globalproject:
                            # find the gc project to query in
                            gc_query_on = gcapp.find_project(args.globalproject)
                            if gc_query_on is None:
                                raise Exception( f"Project '{args.globalproject}' not found")
                        else:
                            print( f"No global project specified so searching for GC {args.globalconfiguration} across the GC app" )
                            gc_query_on = gcapp

                        # get the query capability base URL
                        qcbase = gc_query_on.get_query_capability_uri("oslc_config:Configuration")
                        # query for a configuration with title
                        print( f"querying for gc config {args.globalconfiguration}" )
                        conf = gc_query_on.execute_oslc_query( qcbase, whereterms=[['dcterms:title','=',f'"{args.globalconfiguration}"']], select=['*'], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'})
                        if len( conf.keys() ) == 0:
                            raise Exception( f"No GC configuration matches {args.globalconfiguration}" )
                        elif len( conf.keys() ) > 1:
                            raise Exception( f"Multiple matches for GC configuration {args.globalconfiguration} - you will have to specify the GC project using -g" )
                        gcconfiguri = list(conf.keys())[0]
                        logger.info( f"{gcconfiguri=}" )
                        logger.debug( f"{gcconfiguri=}" )
                        queryparams['oslc_config.context'] = gcconfiguri

                # check the gc config uri exists - a GET from it shouldn't fail!
                if not gcapp.check_valid_config_uri(gcconfiguri,raise_exception=False):
                    raise Exception( f"GC configuration URI {gcconfiguri} not valid!" )

            if p.singlemode and args.globalconfiguration is None:
                args.component = args.project

            if args.component:
                c = p.find_local_component(args.component)
                if not c:
                    raise Exception( f"Component '{args.component}' not found in project {args.project}" )
            else:
                c = None

            # assert the default configuration for this component if none is specified
            if not args.localconfiguration and not args.globalconfiguration and c:
                args.localconfiguration = c.initial_stream_name()
                print( f"Warning - project '{args.project}' is opt-in but for component '{args.component}' you didn't specify a local configuration - using default stream '{c.initial_stream_name()}'" )
            logger.info( f"{args.localconfiguration=}" )
            if p.is_optin:
                if ( args.localconfiguration or p.singlemode ) and args.globalconfiguration is None:
                    if p.singlemode:
                        if args.localconfiguration is None:
                            # default to the stream
                            args.localconfiguration = c.get_default_stream_name()
                    config = c.get_local_config(args.localconfiguration)
                    if config is None:
                        raise Exception( f"Configuration '{args.localconfiguration}' not found in component {args.component}" )
                    queryon = c

                elif gcconfiguri:
                    config = None
                    queryon=p
                else:
                    raise Exception( f"Project {args.project} is opt-in so you must provide a local or global configuration" )

                if args.artifact_format=='comparison' and args.targetconfiguration:
                    targetconfig = c.get_local_config(args.targetconfiguration)
                    if targetconfig is None:
                        raise Exception( f"Target configuration '{args.targetconfiguration}' not found in component {args.component}" )

                    queryparams['targetConfigUri'] = targetconfig
                    queryparams['sourceConfigUri'] = config
            else:
                if not args.localconfiguration:
                    args.localconfiguration = f"{args.project} Initial Stream"
                config = p.get_local_config(args.localconfiguration)
                queryon=p
            queryon.set_local_config(config,gcconfiguri)
            queryparams['oslc_config.context'] = config or gcconfiguri
        if args.artifact_format=='comparison' and args.targetconfiguration:
            if 'oslc_config.context' in queryparams:
                del queryparams['oslc_config.context']

        if args.module:
            # get the query capability base URL for requirements
            qcbase = queryon.get_query_capability_uri("oslc_rm:Requirement")
            # query for a title and for format=module
            modules = queryon.execute_oslc_query(
                qcbase,
                whereterms=[['dcterms:title','=',f'"{args.module}"'], ['rdf:type','=','jazz_rm:Module']],
                select=['*'],
                prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms',rdfxml.RDF_DEFAULT_PREFIX["jazz_rm"]:'jazz_rm'})

            if len(modules)==0:
                raise Exception( f"No module '{args.module}' with that name in {args.project} {args.component}" )
            elif len(modules)>1:
                for k,v in modules.items():
                    print( f'{k} {v.get("dcterms:title","")}' )
                raise Exception( "More than one module with that name in {args.project} {args.component}" )
            moduleuuid = list(modules.keys())[0].rsplit("/",1)[1]
#            print( f"Module is {list(modules.keys())[0]} {moduleuuid}" )
#            queryparams['moduleUri'] = list(modules.keys())[0]
            queryparams['moduleUri'] = moduleuuid

        if args.collection:
            raise Exception( "Not implemented yet" )
            # find the collection IDs or names
            #queryparams['collection'] = coll_u

        if args.coverPage:
            queryparams['coverpage']='true'

        if args.signaturePage:
            queryparams['signaturepage']='true'

        if args.all:
            queryurl = "*"

        if args.schema:
            queryparams['metadata']='schema'

        if args.resourceID or args.moduleResourceID or args.coreResourceID:
            if args.project is None or (args.localconfiguration is None and args.globalconfiguration is None):
                raise Exception( "To use resourceIDs you must specify project and either local or global config")
            # split into numbers and search for them
            ids = ( args.resourceID or args.moduleResourceID or args.coreResourceID ).split( ",")
            # use OSLC query to find them
            qcbase = queryon.get_query_capability_uri("oslc_rm:Requirement")
            logger.debug( f"querying for gc config {args.globalconfiguration}" )
            arts = queryon.execute_oslc_query( qcbase, whereterms=[['dcterms:identifier','in',ids]], select=['*'], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'})
            logger.debug( f"{arts=}" )
            uris = []
            for k,v in arts.items():
                logger.debug( f'{k} {v.get("dcterms:identifier","NOID")} {v.get("dcterms:title","NOTITLE")}  {v.get("rm_nav:parent","NONAV")}' )
                if args.resourceID or (args.coreResourceID and "rm_nav:parent" in v) or (args.moduleResourceID and "rm_nav:parent" not in v):
                    uris.append(k)
            if not uris:
                raise Exception( f"No resource IDs found!" )
            queryparams['resourceURI']=",".join(uris)

        if args.view:
            # find the view
            # find a view http://jazz.net/ns/rm/dng/view#View
            # get the query capability base URL
            qcbase = queryon.get_query_capability_uri("http://jazz.net/ns/rm/dng/view#View")
            # query for a configuration with title
            logger.debug( f"querying for view {args.view}" )
#                views = queryon.execute_oslc_query( qcbase, whereterms=[['dcterms:title','=',f'"{args.view}"']], select=['*'], prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'})
            # view queries don't support any oslc.where - will have to find the view by name from the results
            views = queryon.execute_oslc_query( qcbase, select=['*'])
#                logger.debug( f"{views=}" )
            theview = None
            for k,v in views.items():
#                    logger.debug( f"{k} {v['dcterms:title']}" )
                if v['dcterms:title']==args.view:
                    theview = k
            if theview is None:
                raise Exception( f"No view '{args.view}' found in {args.project} {args.component}" )

            if args.artifact_format=='views':
                queryparams['viewUri'] = theview
            else:
                queryparams['viewName'] = args.view

        if args.modifiedsince:
            # check it is a valid date!
            #yyyy-MM-ddTHH:mm:ss.SSSZ
            # TBC
            DEFAULT_DATE = datetime.datetime(datetime.MINYEAR, 1, 1)
            ts = dateutil.parser.parse(args.modifiedsince, default=DEFAULT_DATE,tzinfos=[dateutil.tz.tzlocal()])
            utc_date_time = ts.astimezone(pytz.utc)
            utc_date_time_s = utc_date_time.strftime('%G-%m-%dT%H:%M:%SZ')
            if utc_date_time_s != args.modifiedsince:
                print( f"Date-time {args.modifiedsince} normalised to {utc_date_time_s}" )
            queryparams['modifiedSince'] = utc_date_time_s

        if args.history:
            queryparams['history'] = True

        queryurl = self.reluri(self.reportablerestbase) + "/"+ args.artifact_format

        if args.all:
            queryurl += "/*"

        # check something is being requested
        if not args.all and not queryparams:
            raise Exception( "You need to specify something!" )

        return (queryurl,queryparams,queryheaders)
