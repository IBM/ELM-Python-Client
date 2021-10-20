##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import logging
import re

import anytree
import lxml.etree as ET
import requests
import tqdm

from . import _app
from . import _project
from . import _typesystem
from . import oslcqueryapi
from . import rdfxml
from . import server
from . import utils

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

class _RMProject(_project._Project):
    # A project
    # NOTE there is a derived class RMComponent used for RM components - it doesn't offer any
    #   functionality, and is a separate class only so it's easier to see whether an instance is a component or the overall project
    # For opt-out projects the only component *is* the project, so RMComponent isn't used.
    # For full optin there are as many components as real components; for <=6.0.3 Cfgm-enabled and for >=7.0
    #   CfgM-disabled (called single mode), there's only ever a single component
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True):
        super().__init__(name, project_uri, app, is_optin,singlemode,defaultinit=defaultinit)
#        self.oslcquery = oslcqueryapi._OSLCOperations(self.app.server,self)
        self._components = None  # keyed on component uri
        self._configurations = None # keyed on the config name
        self._folders = None
        self._foldersnotyetloaded = None
        self.is_singlemode = False # this is only true if config enabled is true and single mode is true
        self.gcconfiguri = None
        self.default_query_resource = "oslc_rm:Requirement"

    #
    # load folders until name_or_uri is found (cuts loading short, remembers folders still to load) or until all loaded
    #  returns None or the matching Folder instance
    #
    # name_or_uri can be:
    #   a folder URI
    #   a folder name - BUT NOTE if the name is ambiguous the return will be None!
    #   a folder path
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
        logger.info( f"load_folders {name_or_uri=}" )
        if name_or_uri is None:
            raise Exception( "name_or_uri is None!" )

        ROOTNAME = "+-+root+-+"

        if self._folders is not None and name_or_uri in self._folders:
            if self._folders[name_or_uri] is None:
                # ambiguous
                logger.info( f"Found {name_or_uri} as Ambiguous" )
                return None
            logger.info( f"Found {name_or_uri} as {self._folders[name_or_uri]}" )
            return self._folders[name_or_uri]

        if force or self._folders is None:
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

        while len(self._foldersnotyetloaded)>0:
            logger.info( "-----------------------" )
            queryuri = self._foldersnotyetloaded.pop(0)
            parent = self._folders.get(queryuri) # parent is None for the first query for the root folder

            logger.info( f"Retrieving {queryuri=} parent {self._folders.get(queryuri)}" )
            folderxml = self.execute_get_xml(queryuri).getroot()

            # find the contained folders
            folderels = rdfxml.xml_find_elements(folderxml,'.//rm_nav:folder')

            # process the contained folders
            for folderel in folderels:
                # get this folder details - name, queryuri
                fname = rdfxml.xmlrdf_get_resource_text(folderel,'.//dcterms:title')
                folderuri = rdfxml.xmlrdf_get_resource_uri( folderel )
                logger.info( f"{fname=} {folderuri=}" )

                if parent is None:
                    # ROOT folder
                    thisfolder = _Folder(name=ROOTNAME,folderuri=folderuri)
                    self._folders[ROOTNAME] = thisfolder
                    logger.debug( f"Adding root {ROOTNAME} {thisfolder}" )
                else:
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

                # insert the subfolder query uris into the list still to be loaded
                for subel in rdfxml.xml_find_elements(folderel,'.//rm_nav:subfolders'):
                    # add the subfolder query queryuri onto the list of folders to retrieve
                    subqueryuri = rdfxml.xmlrdf_get_resource_uri( subel )
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

    def load_components_and_configurations(self,force=False):
        if self._components is not None and self._configurations is not None and not force:
            return
        self._components = {}
        self._configurations = {}
        ncomps = 0
        nconfs = 0
        # retrieve components and configurations for this project
        if not self.is_optin:
            # get the default configuration
            projx = self.execute_get_xml(self.reluri('rm-projects/' + self.iid))
            compsu = rdfxml.xmlrdf_get_resource_text( projx, './/jp06:components' )
            compsx = self.execute_get_xml(compsu)
            defaultcompu = rdfxml.xmlrdf_get_resource_uri( compsx, './/oslc_config:component' )

            # register the only component
            ncomps += 1
            self._components[defaultcompu] = {'name': self.name, 'configurations': {}}
            thisconfu = defaultcompu+"/configurations"
            configs = self.execute_get_json(thisconfu)
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
                confx = self.execute_get_xml(confu)
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

            px = self.execute_get_xml(self.project_uri)

            sx = self.get_services_xml()
            assert sx is not None, "sx is None"
            compuri = rdfxml.xmlrdf_get_resource_uri(sx, ".//oslc:QueryCapability/oslc_config:component")
            assert compuri is not None, "compuri is None"

            ncomps += 1
            self._components[compuri] = {'name': self.name, 'configurations': {}}
            configs = self.execute_get_xml(compuri+"/configurations")
            for conf in rdfxml.xml_find_elements(configs,'.//rdfs:member'):
                confu = rdfxml.xmlrdf_get_resource_uri(conf)
                thisconfx = self.execute_get_xml(confu)
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
        else: # full optin
            cmsp_xml = self.app.retrieve_cm_service_provider_xml()
            components_uri = rdfxml.xmlrdf_get_resource_uri(cmsp_xml, './/oslc:ServiceProvider')
            components_xml = self.execute_get_rdf_xml(components_uri)
            projcx = rdfxml.xml_find_element(components_xml, './/oslc:CreationFactory', 'dcterms:title', self.name)
            if projcx is None:
                # this is <= 6.0.3 with config mgmt enabled which effectively uses opt out
                # get the default configuration
                projx = self.execute_get_xml(self.reluri('rm-projects/' + self.iid))
                compsu = rdfxml.xmlrdf_get_resource_text( projx, './/jp06:components' )
                compsx = self.execute_get_xml(compsu)
                defaultcompu = rdfxml.xmlrdf_get_resource_uri( compsx, './/oslc_config:component' )

                # register the only component
                ncomps += 1
                self._components[defaultcompu] = {'name': self.name, 'configurations': {}}

                configs = self.execute_get_json(defaultcompu+"/configurations")
                if type(configs["http://www.w3.org/2000/01/rdf-schema#member"])==dict:
                    confs = [configs["http://www.w3.org/2000/01/rdf-schema#member"]]
                else:
                    confs = configs["http://www.w3.org/2000/01/rdf-schema#member"]
                for aconf in confs:
                    confu = aconf['@id']
                    confx = self.execute_get_xml(confu)
                    conftitle = rdfxml.xmlrdf_get_resource_text(confx,'.//dcterms:title')
                    conftype = 'Stream' if 'stream' in confu else 'Baseline'
                    created = rdfxml.xmlrdf_get_resource_uri(confx, './/dcterms:created')
                    self._components[defaultcompu]['configurations'][confu] = {'name': conftitle, 'conftype': conftype, 'confXml': confx, 'created': created}
                    self._configurations[defaultcompu] = self._components[defaultcompu]['configurations'][confu]
                    nconfs += 1
            else:
                # full optin
                cru = rdfxml.xmlrdf_get_resource_uri(projcx, 'oslc:creation')
                crx = self.execute_get_rdf_xml(cru)

                for component_el in rdfxml.xml_find_elements(crx, './/ldp:contains'):
                    compu = component_el.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
                    compx = self.execute_get_rdf_xml(compu)
                    comptitle = rdfxml.xmlrdf_get_resource_text(compx, './/dcterms:title')

                    self._components[compu] = {'name': comptitle, 'configurations': {}}
                    ncomps += 1
                    confu = rdfxml.xmlrdf_get_resource_uri(compx, './/oslc_config:configurations')
                    configs_xml = self.execute_get_rdf_xml(confu)
                    for confmemberx in rdfxml.xml_find_elements(configs_xml, './/rdfs:member'):
                        thisconfu = confmemberx.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
                        try:
                            thisconfx = self.execute_get_rdf_xml(thisconfu)
                            conftitle = rdfxml.xmlrdf_get_resource_text(thisconfx, './/dcterms:title')
                            conftypeuri = rdfxml.xmlrdf_get_resource_uri(thisconfx, './/rdf:type')
                            conftype = "Baseline" if "#Baseline" in conftypeuri else "Stream"
                            created = rdfxml.xmlrdf_get_resource_uri(thisconfx, './/dcterms:created')
                            self._components[compu]['configurations'][thisconfu] = {'name': conftitle, 'conftype': conftype
                                                                                    ,'confXml': thisconfx
                                                                                    ,'created': created
                                                                                    }
                            self._configurations[thisconfu] = self._components[compu]['configurations'][thisconfu]
                            baselines_u = rdfxml.xmlrdf_get_resource_uri(thisconfx, './/oslc_config:baselines')
                            logger.debug( f"{baselines_u=}" )
                            if baselines_u is not None:
                                baselines_x = self.execute_get_rdf_xml(baselines_u)
                            nconfs += 1
                        except requests.exceptions.HTTPError as e:
                            pass

        # now create the "components"
        for cu, cd in self._components.items():
            cname = cd['name']
            if not self.is_optin:
                c = self
            else:
                c = self._create_component_api(cu, cname)
            c._configurations = self._components[cu]['configurations']
            self._components[cu]['component'] = c
        return (ncomps, nconfs)

    def get_local_config(self, name_or_uri):
        for cu, cd in self._configurations.items():
            if cu == name_or_uri or cd['name'] == name_or_uri:
                return cu
        return None

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

            logger.info( f"Defining property {name}.{property_title} {propuri=} +++++++++++++++++++++++++++++++++++++++" )
#            self.register_property(property_title,propuri, shape_uri=uri)
            self.register_property(property_title,propuri)

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

    def find_local_component(self, name_or_uri):
        self.load_components_and_configurations()
        for compuri, compdetail in self._components.items():
            if compuri == name_or_uri or compdetail['name'] == name_or_uri:
                return compdetail['component']
        return None

    def _create_component_api(self, component_prj_url, component_name):
        logger.info( f"CREATE RM COMPONENT {self=} {component_prj_url=} {component_name=} {self.app=} {self.is_optin=} {self.singlemode=}" )
        result = _RMComponent(component_name, component_prj_url, self.app, self.is_optin, self.singlemode, defaultinit=False, project=self)
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
                    resource_xml = self.execute_get_rdf_xml(reluri=uri)
                    # check for a rdf label (used for links, maybe other things)
                    id = rdfxml.xmlrdf_get_resource_text(resource_xml,".//rdf:Property/rdfs:label") or rdfxml.xmlrdf_get_resource_text(resource_xml,".//oslc:ResourceShape/dcterms:title") or rdfxml.xmlrdf_get_resource_text(resource_xml,f'.//rdf:Description[@rdf:about="{uri}"]/rdfs:label')
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
            resource_xml = self.execute_get_rdf_xml(reluri=uri)
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
        logger.debug( f"{results=}" )
        if len( results.keys() ) == 0:
            requris = None
        else:
            # need to find the entrs with a empty rm_nav:parent - these are module artifacts
            requris = []
            for k in results.keys():
                if results[k].get('rm_nav:parent',None) is None:
                    requris.append(k)
        return requris

    def resolve_uri_to_reqid( self, requri ):
        pass

    def folder_nametouri_resolver(self, path_or_uri):
        logger.debug( f"Finding uri {path_or_uri}" )
        if self.is_folder_uri(path_or_uri):
            return path_or_uri
        name = self.load_folders(path_or_uri)
        if name is not None:
            return name
        if path_or_uri in self._folders:
            return self._folders[path_or_uri].folderuri
        raise Exception(f"Folder name {path_or_uri} not found")

    def folder_uritoname_resolver(self,uri):
        logger.debug( f"Finding name {uri}" )
        if not self.is_folder_uri(uri):
            raise Exception( "Folder uri isn't a uri {uri}" )
        thisfolder = self.load_folders(uri)
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

class _RMComponent(_RMProject):
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True, project=None):
        if not project:
            raise Exception( "You mist provide a project instance when creating a component" )
        super().__init__(name, project_uri, app, is_optin,singlemode,defaultinit=defaultinit)
        self.component_project = project
        self.services_uri = project.services_uri    # need for reqif which wants to put the services.xml URI into created XML for new definitions


#################################################################################################

@utils.mixinomatic
class _RMApp(_app._App, _typesystem.No_Type_System_Mixin):
    domain = 'rm'
    project_class = _RMProject
    supports_configs = True
    supports_components = True
    supports_reportable_rest = True
    reportablerestbase='publish'
    artifact_formats = [ # For RR
            'collections'
            ,'comments'
            ,'comparisons'  # for 7.0.2
            ,'diff'         # for 7.0.2
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
        self.rootservices_xml = self.execute_get_xml(self.reluri('rootservices') )
        self.serviceproviders = 'oslc_rm_10:rmServiceProviders'
        self.version = rdfxml.xmlrdf_get_resource_text(self.rootservices_xml,'.//oslc_rm_10:version')
        self.majorversion = rdfxml.xmlrdf_get_resource_text(self.rootservices_xml,'.//oslc_rm_10:majorVersion')
        self.reportablerestbase = self.contextroot+'/publish'
        self.default_query_resource = None # RM doesn't provide any app-level queries

        logger.info( f"Versions {self.majorversion} {self.version}" )

    def _get_headers(self, headers=None):
        result = super()._get_headers()
        result['net.jazz.jfs.owning-context'] = self.baseurl
        if headers:
            result.update(headers)
        logger.info( f"rmapp_gh {result}" )
        return result

