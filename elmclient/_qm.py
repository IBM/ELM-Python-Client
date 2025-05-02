##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


# RQM OSLC API https://jazz.net/wiki/bin/view/Main/RqmOslcQmV2Api

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
from . import _qmrestapi

#################################################################################################

logger = logging.getLogger(__name__)

#################################################################################################


class QMProject(_project._Project, _qmrestapi.QM_REST_API_Mixin):
    # A QM project
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True):
        super().__init__(name, project_uri, app, is_optin,singlemode,defaultinit=defaultinit)
        self._components = None  # keyed on component uri
        self._configurations = None # keyed on the config name
        self._folders = None
        self._foldersnotyetloaded = None
        self.is_singlemode = False # this is only true if config enabled is true and single mode is true
        self.gcconfiguri = None
        self.default_query_resource = "oslc_qm:TestCaseQuery"
        self._confs_to_load = []

    def load_components_and_configurations(self,force=False):
        if self._components is not None and self._configurations is not None and not force:
            return
        self._components = {}
        self._configurations = {}
        ncomps = 0
        nconfs = 0
        # retrieve components and configurations for this project
        if not self.is_optin:
            # for QM, no configs to load!
            return
        elif self.singlemode:
            
            # xmlns:ns3="http://open-services.net/ns/core#
            # <ns3:details ns4:resource="https://jazz.ibm.com:9443/qm/process/project-areas/_AzVy8LOJEe6f6NR46ab0Iw"/>
            logger.debug( f"{self.singlemode=}" )
            self.singlemode=False
            self.is_optin=False
            return
            #get the single component from a QueryCapability
            # <oslc:QueryCapability>
            #    <oslc_config:component rdf:resource="https://mb02-calm.rtp.raleigh.ibm.com:9443/rm/cm/component/_ln_roBIOEeumc4tx0skHCA"/>
            #    <oslc:resourceType rdf:resource="http://jazz.net/ns/rm/dng/view#View"/>
            #    <oslc:queryBase rdf:resource="https://mb02-calm.rtp.raleigh.ibm.com:9443/rm/views_oslc/query?componentURI=https%3A%2F%2Fmb02-calm.rtp.raleigh.ibm.com%3A9443%2Frm%2Fcm%2Fcomponent%2F_ln_roBIOEeumc4tx0skHCA"/>
            #    <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">View Definition Query Capability</dcterms:title>
            # </oslc:QueryCapability>

            px = self.execute_get_xml( self.project_uri, intent="Retrieve project definition" )

            sx = self.get_services_xml()
            assert sx is not None, "sx is None"
            compuri = rdfxml.xmlrdf_get_resource_uri(sx, ".//oslc:details")
            assert compuri is not None, "compuri is None"
            ncomps += 1
            self._components[compuri] = {'name': self.name, 'configurations': {}, 'confs_to_load': []}
            configs = self.execute_get_xml( compuri+"/configurations", intent="Retrieve all project/component configurations (singlemode)" )
            for conf in rdfxml.xml_find_elements(configs,'.//rdfs:member'):
                confu = rdfxml.xmlrdf_get_resource_uri(conf)
                thisconfx = self.execute_get_xml( confu, intent="Retrieve a configuration definition (singlemode)" )
                conftitle= rdfxml.xmlrdf_get_resource_text(thisconfx,'.//dcterms:title')
                # e.g. http://open-services.net/ns/config#Stream
                isstr = rdfxml.xml_find_element( thisconfx,'.//oslc_config:Stream' )
                if isstr is None:
                    conftype = "Baseline"
                else:
                    conftype = "Stream"
                self._components[compuri]['configurations'][confu] = {'name': conftitle, 'conftype': conftype, 'confXml': thisconfx}
                self._configurations[confu] = self._components[compuri]['configurations'][confu]
                nconfs += 1
            self._configurations = self._components[compuri]['configurations']
        else: # full optin
            logger.debug( f"full optin" )
            cmsp_xml = self.app.retrieve_cm_service_provider_xml()
            logger.info( f"cmsp=",ET.tostring(cmsp_xml) )
#  <rdf:Description rdf:nodeID="A4">
#    <oslc:resourceType rdf:resource="http://open-services.net/ns/config#Component"/>
#    <oslc:queryBase rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/resources/com.ibm.team.vvc.Component"/>
#    <oslc:resourceShape rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/resourceShapes/com.ibm.team.vvc.Component"/>
#    <dcterms:title rdf:parseType="Literal">Default query capability for Component</dcterms:title>
#    <rdf:type rdf:resource="http://open-services.net/ns/core#QueryCapability"/>
#  </rdf:Description>

            components_uri = rdfxml.xmlrdf_get_resource_uri(cmsp_xml, './/rdf:Description/rdf:type[@rdf:resource="http://open-services.net/ns/core#QueryCapability"]/../oslc:resourceType[@rdf:resource="http://open-services.net/ns/config#Component"]/../oslc:queryBase')
            logger.info( f"{components_uri=}" )
#            print( f"{components_uri=}" )
            # get all components
            crx = self.execute_get_xml( components_uri, intent="Retrieve component definition" )
            logger.info( f"{crx=}" )
#      <oslc_config:Component rdf:about="https://jazz.ibm.com:9443/qm/oslc_config/resources/com.ibm.team.vvc.Component/_iw4s4EB3Eeus6Zk4qsm_Cw">
#        <dcterms:title rdf:parseType="Literal">SGC Agile</dcterms:title>
#        <oslc:instanceShape rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/resourceShapes/com.ibm.team.vvc.Component"/>
#        <dcterms:identifier>_iw4s4EB3Eeus6Zk4qsm_Cw</dcterms:identifier>
#        <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2020-12-17T14:52:54.318Z</dcterms:modified>
#        <oslc_config:configurations rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/resources/com.ibm.team.vvc.Component/_iw4s4EB3Eeus6Zk4qsm_Cw/configurations"/>
#        <acc:accessContext rdf:resource="https://jazz.ibm.com:9443/qm/acclist#_rikP0EB1Eeus6Zk4qsm_Cw"/>
#        <process:projectArea rdf:resource="https://jazz.ibm.com:9443/qm/process/project-areas/_rikP0EB1Eeus6Zk4qsm_Cw"/>
#        <oslc:serviceProvider rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/serviceProviders/configuration"/>
#        <dcterms:relation rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/resources/_rikP0EB1Eeus6Zk4qsm_Cw/component/_iw4s4EB3Eeus6Zk4qsm_Cw"/>
#      </oslc_config:Component>

            for component_el in rdfxml.xml_find_elements(crx, f'.//oslc_config:Component/process:projectArea[@rdf:resource="{self.project_uri}"]/..'):
                logger.info( f"{component_el=}" )
                compu = rdfxml.xmlrdf_get_resource_uri(component_el)
                comptitle = rdfxml.xmlrdf_get_resource_text(component_el, './/dcterms:title')
                logger.info( f"Found component {comptitle}" )
                ncomps += 1
                confu = rdfxml.xmlrdf_get_resource_uri(component_el, './/oslc_config:configurations')
                self._components[compu] = {'name': comptitle, 'configurations': {}, 'confs_to_load': [confu]}
                
                configs_xml = self.execute_get_rdf_xml( confu, intent="Retrieve all project/component configuration definitions" )
                # Each config:     <ldp:contains rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/resources/com.ibm.team.vvc.Configuration/_qT1EcEB4Eeus6Zk4qsm_Cw"/>

                for confmemberx in rdfxml.xml_find_elements(configs_xml, './/ldp:contains'):
                    thisconfu = rdfxml.xmlrdf_get_resource_uri( confmemberx )
                    try:
                        thisconfx = self.execute_get_rdf_xml( thisconfu, intent="Retrieve a configuration definition" )
                        conftitle = rdfxml.xmlrdf_get_resource_text(thisconfx, './/dcterms:title')
                        conftype = rdfxml.xmlrdf_get_resource_uri(thisconfx, './/rdf:type')
                        logger.info( f"Found config {conftitle} {conftype} {thisconfu}" )
                        self._components[compu]['configurations'][thisconfu] = {'name': conftitle, 'conftype': conftype,
                                                                                'confXml': thisconfx}
                        self._configurations[thisconfu] = self._components[compu]['configurations'][thisconfu]
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
            c._confs_to_load = self._components[cu]['confs_to_load']
            self._confs_to_load.extend(self._components[cu]['confs_to_load'])
            self._components[cu]['component'] = c
        return (ncomps, nconfs)

    def get_local_config(self, name_or_uri, global_config_uri=None):
        if global_config_uri:
            if not name_or_uri:
                raise Exception( "can't find a local config in a GC if config name not provided" )
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
            return config_uri
        else:
            for cu, cd in self._configurations.items():
                logger.debug( f"{cu=} {cd=} {name_or_uri=}" )
                if cu == name_or_uri or cd['name'] == name_or_uri:
                    return cu
        return None

    def load_configs(self):
        # load configurations
        while self._confs_to_load:
            confu = self._confs_to_load.pop()
            if not confu:
                # skip None in list
                continue
            logger.debug( f"Retrieving config {confu}" )
            try:
                configs_xml = self.execute_get_rdf_xml(confu, intent="Retrieve a configuration definition")
            except:
                logger.info( f"Config ERROR {thisconfu} !!!!!!!" )
                continue
            confmemberx = rdfxml.xml_find_elements(configs_xml, './/rdfs:member[@rdf:resource]')
            if confmemberx:
                #  a list of members
                for confmember in confmemberx:
                    thisconfu = confmember.get("{%s}resource" % rdfxml.RDF_DEFAULT_PREFIX["rdf"])
                    self._confs_to_load.append(thisconfu)
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
                if thisconfu not in self._configurations:
                    logger.debug( f"Adding {conftitle}" )
                    self._configurations[thisconfu] = {
                                                                                'name': conftitle
                                                                                , 'conftype': conftype
                                                                                ,'confXml': confmember
                                                                                ,'created': created
                                                                            }
#                    self._configurations[thisconfu] = self._components[self.project_uri]['configurations'][thisconfu]
                else:
                    logger.debug( f"Skipping {thisconfu} because already defined" )
                # add baselines and changesets
                self._confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember, './oslc_config:streams') )
                self._confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember, './oslc_config:baselines') )
                self._confs_to_load.append( rdfxml.xmlrdf_get_resource_uri(confmember, './rm_config:changesets') )


    def list_configs( self ):
        configs = []
        self.load_configs()
        for cu, cd in self._configurations.items():
            configs.append( cd['name'] )
        
        return configs

    # load the typesystem using the OSLC shape resources
    def _load_types(self,force=False):
        logger.debug( f"load type {self=} {force=}" )

        # if already loaded, try to avoid reloading
        if self.typesystem_loaded and not force:
            return

        self.clear_typesystem()

        if self.local_config:
            # get the configuration-specific services.xml
            sx = self.get_services_xml(force=True,headers={'configuration.Context': self.local_config, 'net.jazz.jfs.owning-context': None})
        else:
            # No config - get the services.xml
            sx = self.get_services_xml(force=True)
        if sx:
            shapes_to_load = rdfxml.xml_find_elements(sx, './/oslc:resourceShape')

            pbar = tqdm.tqdm(initial=0, total=len(shapes_to_load),smoothing=1,unit=" results",desc="Loading ETM shapes")

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
        return self._generic_load_type_from_resource_shape(el, supershape=None)

    # return a dictionary with all local component uri as key and name as value (so two components could have the same name?)
    def get_local_component_details(self):
        results = {}
        for compuri, compdetail in self._components.items():
            results[compuri] = compdetail['name']
        return results

    def find_local_component(self, name_or_uri):
        if self.is_optin:
            self.load_components_and_configurations()
            for compuri, compdetail in self._components.items():
                logger.info( f"Checking {name_or_uri} {compdetail}" )
                if compuri == name_or_uri or compdetail['name'] == name_or_uri:
                    return compdetail['component']
        else:
            return self
        return None

    def list_components( self ):
        # list all the component names
        self.load_components_and_configurations()
        components = []
        for compuri, compdetail in self._components.items():
            if compdetail.get('name'):
                components.append( compdetail.get('name') )
        return components

    def _create_component_api(self, component_prj_url, component_name):
        logger.info( f"CREATE QM COMPONENT {self=} {component_prj_url=} {component_name=} {self.app=} {self.is_optin=} {self.singlemode=}" )
        result = QMComponent(component_name, component_prj_url, self.app, self.is_optin, self.singlemode, defaultinit=False, project=self)
        return result


    def is_type_uri(self, uri):
        if uri and uri.startswith(self.app.baseurl) and '/types/' in uri:
            return True
        return False

    # for OSLC query, given a type URI, return its name
    # qm-specific resolution
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
                    resource_xml = self.execute_get_rdf_xml( reluri=uri, intent="Retrieve type definition to get its name")
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
        if uri and uri.startswith(self.app.baseurl) and '/reQQsources/' in uri:
            return True
        return False

    # for OSLC query, given a resource URI, return the requirement dcterms:identifier
    def resource_id_from_uri(self, uri):
        if self.is_resource_uri(uri):
            resource_xml = self.execute_get_rdf_xml(reluri=uri, intent="Retrieve resource dcterms:identifier")
            id = rdfxml.xmlrdf_get_resource_text(resource_xml, ".//dcterms:identifier")
            return id
        raise Exception(f"Bad resource uri {uri}")

    def is_folder_uri(self, uri):
        if uri and uri.startswith(self.app.baseurl) and '/folders/' in uri:
            return True
        return False

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

class QMComponent(QMProject):
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True, project=None):
        if not project:
            raise Exception( "You mist provide a project instance when creating a component" )
        super().__init__(name, project_uri, app, is_optin,singlemode,defaultinit=defaultinit)
        self.component_project = project


#################################################################################################

@utils.mixinomatic
class QMApp(_app._App, oslcqueryapi._OSLCOperations_Mixin, _typesystem.Type_System_Mixin):
    domain = 'qm'
    project_class = QMProject
    supports_configs = True
    supports_components = True
    supports_reportable_rest = True
    reportable_rest_status = "Application supports Reportable REST but not implemented here yet"
    reportablerestbase='service/com.ibm.rqm.integration.service.IIntegrationService'
    artifactformats = [ # For RR
            '*'
            ,'collections'
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
    identifier_name = 'Short ID'
    identifier_uri = 'Identifier'

    def __init__(self, server, contextroot, jts=None):
        super().__init__(server, contextroot, jts=jts)
        self.rootservices_xml = self.execute_get_xml(self.reluri('rootservices'), intent="Retrieve QM application rootservices")
        self.serviceproviders = 'oslc_qm_10:qmServiceProviders'
        self.default_query_resource = "oslc_config:Configuration"

        self.version = rdfxml.xmlrdf_get_resource_text(self.rootservices_xml,'.//rqm:version')
        self.majorversion = rdfxml.xmlrdf_get_resource_text(self.rootservices_xml,'.//rqm:majorVersion')
        logger.info( f"Versions {self.majorversion} {self.version}" )

    def _get_headers(self, headers=None):
        result = super()._get_headers()
        result['net.jazz.jfs.owning-context'] = self.baseurl
        if headers:
            result.update(headers)
        return result

    # load the projects from the project areas XML - doesn't create any project classes, this is done later when finding a project to open
    # this is specific to QM so that projects enabled for baselines are treated as opt-out (which means you can't query baselines!)
    def _load_projects(self,include_archived=False,force=False):
        if self.project_class is None:
            raise Exception(f"projectClass has not been set on {self}!")
        if self._projects is not None and not force:
            return
        logger.info( "Loading projects")
        self._projects = {}
        uri = rdfxml.xmlrdf_get_resource_uri(self.rootservices_xml, 'jp06:projectAreas')
        params = {}
        if include_archived:
            params['includeArchived'] = 'true'
        self.project_areas_xml = self.execute_get_xml(uri, params=params, intent="Retrieve all project area definitions" )
        logger.debug( f"{self.project_areas_xml=}" )
        for projectel in rdfxml.xml_find_elements(self.project_areas_xml,".//jp06:project-area" ):
            logger.debug( f"{projectel=}" )
            projectu = rdfxml.xmlrdf_get_resource_text(projectel,".//jp06:url")
            projectname = rdfxml.xmlrdf_get_resource_uri(projectel,attrib='jp06:name')
            logger.debug( f"{projectname=}" )
            is_optin = False
            singlemode = False
            if self.supports_configs:
                en = rdfxml.xmlrdf_get_resource_text(projectel,'.//jp:configuration-management-enabled')
                is_optin = ( rdfxml.xmlrdf_get_resource_text(projectel,'.//jp:configuration-management-enabled') == "true" )
                singlemode = ( rdfxml.xmlrdf_get_resource_text(projectel,'.//jp:configuration-management-mode') == "SINGLE" )
                if singlemode:
                    # for QM, treat opt-in SINGLE as opt-out
                    is_optin = False
                    singlemode = False
            logger.info( f"{projectname=} {projectu=} {is_optin=} {singlemode=}" )

            self._projects[projectu] = {'name':projectname, 'project': None, 'projectu': projectu, 'is_optin': is_optin, 'singlemode': singlemode }
            self._projects[projectname] = projectu



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

            pbar = tqdm.tqdm(initial=0, total=len(shapes_to_load),smoothing=1,unit=" results",desc="Loading ETM shapes")

            for el in shapes_to_load:
                self._load_type_from_resource_shape(el)
                pbar.update(1)

            pbar.close()
        else:
            raise Exception( "services xml not found!" )

        self.typesystem_loaded = True
        return None

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
        if not uri.startswith(self.baseurl):
            if self.server.jts.is_user_uri(uri):
                result = self.server.jts.user_uritoname_resolver(uri)
                logger.debug(f"returning user")
                return result
            uri1 = rdfxml.uri_to_prefixed_tag(uri,noexception=True)
            logger.debug(f"No app base URL {self.baseurl=} {uri=} {uri1=}")
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
        parser_qm = subparsers.add_parser('qm', help='ETM Reportable REST actions', parents=[common_args])
        
        parser_qm.add_argument('artifact_format', choices=cls.artifact_formats, default=None, help=f'CCM artifact format - possible values are {", ".join(cls.artifact_formats)}')

        # SCOPE settings
        parser_qm.add_argument('-p', '--project', default=None, help='Scope: Name of project - required when using module/collection/view/resource/typename ID/typename as a filter')

        parser_qm.add_argument('-r', '--report', action='store_true', help='Report the fields available')

#        # Source Filters - only use one of these at once - all require a project and configuration!
#        rmex1 = parser_qm.add_mutually_exclusive_group()
#        rmex1.add_argument('-c', '--collection', default=None, help='Sub-scope: RM: Name or ID of collection - you need to provide the project and local/global config')
#        rmex1.add_argument('-m', '--module', default=None, help='Sub-scope: RM: Name or ID of module - you need to provide the project and local/global config')
#        rmex1.add_argument('-v', '--view', default=None, help='Sub-scope: RM: Name of view - you need to provide the project and local/global config')
#        rmex1.add_argument('-r', '--resourceIDs', default=None, help='Sub-scope: RM: Comma-separated IDs of resources - you need to provide the project and local/global config')
#        rmex1.add_argument('-t', '--typename', default=None, help='Sub-scope: RM: Name of type - you need to provide the project and local/global config')
        
#        # Output FILTER settings - only use one of these at once
#        parser_qm.add_argument('-a', '--all', action="store_true", help="Filter: Report all resources")
#        parser_qm.add_argument('-d', '--modifiedsince', default=None, help='Filter: only return items modified since this date in format 2021-01-31T12:34:26Z')
        parser_qm.add_argument('-f', '--fields', default=None, help="Filter using xpath")
#        parser_qm.add_argument('-x', '--expandEmbeddedArtifacts', action="store_true", help="Filter: Expand embedded artifacts")
        
#        # various options
#    #    parser_qm.add_argument('--forever', action='store_true', help="TESTING UNFINISHED: save web data forever (used for regression testing against stored data, may not need the target server if no requests fail)" )
#        parser_qm.add_argument('--nresults', default=-1, type=int, help="TESTING UNFINISHED: Number of results expected (used for regression testing against stored data, doesn't need the target server - use -1 to disable checking")
#        parser_qm.add_argument('--pagesize', default=100, type=int, help="Page size for results paging (default 100)")    
        
#        # Output controls - only use one of these at once!
        rmex2 = parser_qm.add_mutually_exclusive_group()
#        rmex2.add_argument('--attributes', default=None, help="Output: Comma separated list of attribute names to report (requires specifying project and configuration)")
        rmex2.add_argument('--schema', action="store_true", help="Output: Report the schema")
#        rmex2.add_argument('--titles', action="store_true", help="Output: Report titles")
#        rmex2.add_argument('--linksOnly', action="store_true", help="Output: Report links only")
#        rmex2.add_argument('--history', action="store_true", help="Output: Report history")
#        rmex2.add_argument('--coverPage', action="store_true", help="Output: Report cover page variables")
#        rmex2.add_argument('--signaturePage', action="store_true", help="Output: Report signature page variables")
#    #    rmex2.add_argument('--size', action="store_true", help="Output: Set size (required for ???)")

    def process_represt_arguments( self, args, allapps ):
        '''
        Process above arguments, returning a dictionayt of parameters to add to the represt base URL
        NOTE this does have some dependency on thje overall 
        
        NOTE this is called on an instance (i.e. not a class method) because by now we know which app is being queried
        '''
        queryparams = {}
        queryurl = ""
        queryheaders={}
        
        if args.schema:
            queryparams['metadata'] = 'schema'
            
        queryurl = self.reluri(self.reportablerestbase) + "/"+ args.artifact_format
            
        if args.report:
            typestodo = []
            # get the schema, walk it building the tree of fields
            schema_x = self.execute_get_xml(queryurl+"?metadata=schema", intent="Retrieve Reportable REST schema").getroot()
#            print( f"{schema_x.tag=}" )
#            print( f"{schema_x=}" )
            el_x = rdfxml.xml_find_element( schema_x, "./xs:element" )
            typestodo=[el_x.get('type')]
            knowntypes={el_x.get('type'):[el_x.get('type')]} # contains path to [parent
            fieldlist = []
            while typestodo:
#                print( f"{knowntypes=}" )
                typetofind = typestodo.pop(0)
                type_x = rdfxml.xml_find_element( schema_x, f'.//xs:complexType[@name="{typetofind}"]' )
#                print( f"Finding {typetofind=} {type_x=}" )
                if type_x is not None:
                    seq_x = rdfxml.xml_find_element( type_x, './xs:sequence' )
                    type_name = type_x.get('name')
                    name_name = type_x.get('type')
    #                print( f"{type_name=}" )
                    if seq_x is not None:
#                        print( f"{typetofind=} {type_name=} {name_name=}" )
                        for subel_x in rdfxml.xml_find_elements(seq_x,'./xs:element'):
                            subeltype = subel_x.get('type')
                            subelname = subel_x.get('name')
    #                        print( f"{subeltype=}" )
    #                        print( f"{subelname=}" )
                            typestr = ""
                            if subeltype.startswith( "xs:"):
#                                print( f"Type {typetofind} Found endpoint {subelname} {subeltype}" )
                                typestr = " "+subeltype                            
                                fieldpath = "/".join(knowntypes[type_name]+[subelname]) + typestr
                                if fieldpath not in fieldlist:
#                                    print( f"Adding {fieldpath}" )
                                    fieldlist.append(fieldpath)
                                
                            elif subeltype not in knowntypes:
                                typestodo.append(subeltype) 
#                                print( f"Type {typetofind} Queued {subelname=} {subeltype=}" )
                                knowntypes[subeltype] = knowntypes[type_name]+[subelname]
    #                        print( f'{"/".join(knowntypes[subeltype]+[subelname])}' )
                                
                    else:
                        raise Exception( f"xs:sequence not found in schema for type {typetofind}" )
            print( "\n".join(sorted(fieldlist) ) )

        if args.fields:
            queryparams['fields'] = args.fields

        return (queryurl,queryparams,queryheaders)
