##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import logging
import urllib

import requests.exceptions

from . import rdfxml
from . import oslcqueryapi
from . import utils
from . import httpops

logger = logging.getLogger(__name__)

#################################################################################################
# a generic jazz application

class _App( httpops.HttpOperations_Mixin ):
    'A generic Jazz application'
    domain = 'UNSPECIFIED APP DOMAIN'
    project_class = None
    artifact_formats = [] # For RR
    reportablerest_baseurl = "publish"
    supports_reportable_rest = False
    reportable_rest_status = "Not supported by application"
    majorVersion = None
    version = None

    def __init__(self, server, contextroot, *, jts=None):
        super().__init__()
        logger.info( f'Creating app {contextroot} {server=}' )
        self.contextroot = contextroot
        self.baseurl = urllib.parse.urljoin(server.baseurl, contextroot) + "/"
        self.jts = jts
        self.server = server
        self.project_areas_xml = None
        self._projects = None
        self.headers = {}
        self.cmServiceProviders = 'oslc_config:cmServiceProviders'
        self.iid=None # app has a dummy (empty) iid
        self.hooks = []
        self.default_query_resource = None

    def retrieve_cm_service_provider_xml(self):
        cm_service_provider_uri = rdfxml.xmlrdf_get_resource_uri(self.rootservices_xml,
                                                                     self.cmServiceProviders)
        rdf = self.execute_get_rdf_xml(cm_service_provider_uri, intent="Retrieve application CM Service Provider" )
        return rdf

    def retrieve_oslc_catalog_xml(self):
        oslccataloguri = rdfxml.xmlrdf_get_resource_uri(self.rootservices_xml, self.serviceproviders)
        if oslccataloguri is None:
            return None
        return self.execute_get_rdf_xml(oslccataloguri, intent="Retrieve application OSLC Catalog (list of projects)")

    # get local headers
    def _get_headers(self, headers=None):
        logger.info( f"app_gh" )
        result = {'X-Requested-With': 'XMLHttpRequest', 'Referer': self.reluri('web'),'OSLC-Core-Version':'2.0'}
        if self.headers:
            result.update(self.headers)
        result.update(self._get_oslc_headers())
        if headers:
            result.update(headers)
        logger.info( f"app_gh {result}" )
        return result

    # get a request with local headers
    def _get_request(self, verb, reluri='', *, params=None, headers=None, data=None):
        fullheaders = self._get_headers()
        if headers is not None:
            fullheaders.update(headers)
        sortedparams = None if params is None else {k:params[k] for k in sorted(params.keys())}
        request = httpops.HttpRequest( self.server._session, verb, self.reluri(reluri), params=sortedparams, headers=fullheaders, data=data)
        return request

    def _get_oslc_headers(self, headers=None):
        result = {
            'Accept': 'application/rdf+xml'
            , 'Referer': self.reluri('web')
            , 'OSLC-Core-Version': '2.0'
        }
        if headers:
            result.update(headers)
        return result

    def find_projectname_from_uri(self,name_or_uri):
        self._load_projects()
            
        if self.is_project_uri(name_or_uri):
            # find the project
            if name_or_uri in self._projects:
                return self._projects[name_or_uri]['name']
        else:
            return name_or_uri

    def is_project_uri(self, uri):
        if uri.startswith(self.baseurl) and '/process/project-areas/' in uri:
            return True
        return False

    # return an absolute URL for a url relative to this app
    # NOTE if reluri has a leading / this will be relative to the serverhostname:port
    # i.e. the app context root will be removed.
    # So if you want an app-relative URL don't use a leading /
    def reluri(self, reluri=''):
        return urllib.parse.urljoin(self.baseurl,reluri)

    # load the projects from the project areas XML - doesn't create any project classes, this is done later when finding a project to open
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
            logger.info( f"{projectname=} {projectu=} {is_optin=} {singlemode=}" )

            self._projects[projectu] = {'name':projectname, 'project': None, 'projectu': projectu, 'is_optin': is_optin, 'singlemode': singlemode }
            self._projects[projectname] = projectu

    # get an instance for a specific project
    def find_project(self, projectname_or_uri, include_archived=False):
        logger.info( f"Find project {projectname_or_uri}")
        self._load_projects()
        if self.is_project_uri(projectname_or_uri):
            if projectname_or_uri in self._projects:
                res = self._projects[projectname_or_uri]['project']
                if res is None:
                    # create the project instance
                    res = self.project_class(self._projects[projectname_or_uri]['name'], self._projects[projectname_or_uri]['projectu'], self, is_optin=self._projects[projectname_or_uri]['is_optin'],singlemode=self._projects[projectname_or_uri]['singlemode'])
            else:
                res = None
        else:
            # must be a name
            projectu = self._projects.get(projectname_or_uri)
            if projectu is None:
                res = None
            else:
                res = self._projects[projectu]['project']
                if res is None:
                    # create the project instance
                    res = self.project_class(self._projects[projectu]['name'], self._projects[projectu]['projectu'], self, is_optin=self._projects[projectu]['is_optin'],singlemode=self._projects[projectu]['singlemode'])
        logger.info( f'Project {projectname_or_uri} found {projectu} {res}' )
        return res
        
    def is_uri( self, name_or_uri ):
        if name_or_uri.startswith('http://') or name_or_uri.startswith('https://'):
            return True
        return False
        
    def list_projects( self ):
        self._load_projects()
        projects = [p for p in self._projects if not self.is_uri(p)]
        return projects
        
    def report_type_system( self ):
        qcdetails = self.get_query_capability_uris()
        report = "<HTML><BODY>\n"
        report += f"<H1>Type system report for application {self.domain}</H1>\n"
        report += "<H2>Application Queryable Resource Types, short name and URI</H2>\n"
        rows = []
        for k in sorted(qcdetails.keys()):
            shortname = k.split('#')[-1]
            shortname +=  " (default)" if self.default_query_resource is not None and k==rdfxml.tag_to_uri(self.default_query_resource) else ""
            rows.append( [shortname,k,qcdetails[k]])
        # print in a nice table with equal length columns
        report += utils.print_in_html(rows,['Short Name', 'URI', 'Query Capability URI'])
        report += self.textreport()

        rows = []
        for prefix in sorted(rdfxml.RDF_DEFAULT_PREFIX.keys()):
            rows.append([prefix,rdfxml.RDF_DEFAULT_PREFIX[prefix]] )
        report += "<H2>Prefixes</H2>\n"
        report += utils.print_in_html(rows,['Prefix', 'URI'])
        report += "</BODY></HTML>\n"
        return report

    def get_query_capability_uri(self,resource_type=None,context=None):
        context = context or self
        resource_type = resource_type or context.default_query_resource
        return self.get_query_capability_uri_from_xml(capabilitiesxml=context.retrieve_cm_service_provider_xml(), resource_type=resource_type,context=context)

    def get_query_capability_uris(self,resource_type=None,context=None):
        context = context or self
        resource_type = resource_type or context.default_query_resource
        return self.get_query_capability_uris_from_xml(capabilitiesxml=context.retrieve_cm_service_provider_xml(),context=context)

    def get_query_capability_uri_from_xml(self,capabilitiesxml,resource_type,context):
        logger.info( f"get_query_capability_uri_from_xml {self=} {resource_type=} {capabilitiesxml=}" )
        if resource_type is None:
            raise Exception( "You must provide a resource type" )
        # ensure we have a URI for the resource type
        resource_type_u = rdfxml.tag_to_uri(resource_type)
        # get list of [resourcetype,uri]
        qcs = self.get_query_capability_uris_from_xml(capabilitiesxml=capabilitiesxml,context=context)
        if resource_type_u.startswith( 'http' ):
            # looking for a complete precise URI
            if resource_type_u in qcs:
                return qcs[resource_type_u]
            raise Exception( f"Resource type {resource_type} not found" )
        # didn't specify a URI - find the first match at the end of the resouce type
        for k,v in qcs.items():
            if k.endswith(resource_type):
                return v
        raise Exception( f"Query capability {resource_type} {resource_type_u} not found!" )

    # returns a dictionary of resource type to query capability URI
    # this is used when the XML doesn't have references off to other URLs (like GCM does)
    def get_query_capability_uris_from_xml(self,capabilitiesxml,context):
        logger.info( f"get_query_capability_uris_from_xml {self=} {capabilitiesxml=}" )
        qcs = {}
        #<oslc:QueryCapability>
        #    <oslc:resourceType rdf:resource="http://open-services.net/ns/cm#ChangeRequest"/>
        #    <oslc:queryBase rdf:resource="https://jazz.ibm.com:9443/ccm/oslc/contexts/_2H-_4OpoEemSicvc8AFfxQ/workitems"/>
        # find a queryBase and it's the containing tag that has the info
        for qcx in rdfxml.xml_find_elements(capabilitiesxml,'.//oslc:queryBase/..'):
            for qcrtx in rdfxml.xml_find_elements( qcx, 'oslc:resourceType'):
                qcs[rdfxml.xmlrdf_get_resource_uri(qcrtx)] = rdfxml.xmlrdf_get_resource_uri(qcx, "oslc:queryBase")
                logger.debug( f"{rdfxml.xmlrdf_get_resource_uri(qcrtx)=}" )
        return qcs

    def get_factory_uri_from_xml(self,factoriesxml,resource_type,context, return_shapes=False ):
        logger.info( f"get_factory_uri_from_xml {self=} {resource_type=} {factoriesxml=} {return_shapes=}" )
        if resource_type is None:
            raise Exception( "You must provide a resource type" )
        # ensure we have a URI for the resource type
        resource_type_u = rdfxml.tag_to_uri(resource_type)
        # get list of [resourcetype,uri]
        qcs = self.get_factory_uris_from_xml(factoriesxml=factoriesxml,context=context)
        result = None
        if resource_type_u.startswith( 'http' ):
            # looking for a complete precise URI
            if resource_type_u in qcs:
                result = qcs[resource_type_u]
            else:
                raise Exception( f"Factory for resource type {resource_type} not found" )
        else:
            # didn't specify a URI - find the first match at the end of the resouce type
            for k,v in qcs.items():
                if k.endswith(resource_type):
                    result = v
        if result is None:
            raise Exception( f"QFactory {resource_type} {resource_type_u} not found!" )
        if return_shapes:
            shapeuris = []
            # get the shapes from this factory capability
            # find the factory capability xml
#            print( f"{result=}" )
            fc_rs = rdfxml.xml_find_elements( factoriesxml, f".//oslc:CreationFactory/oslc:creation[@rdf:resource='{result}']/../oslc:resourceShape" )
#            print( f"{fc_rs=}" )
            for rs in fc_rs:
                # collect the <oslc:resourceShape entries
                shapeuris.append(rdfxml.xmlrdf_get_resource_uri( rs) )
#            print( f"{shapeuris=}" )
            return result, shapeuris
        else:
            return result
    # returns a dictionary of resource type to factory URI
    # this is used when the XML doesn't have references off to other URLs (like GCM does)
    def get_factory_uris_from_xml(self,factoriesxml,context):
        logger.info( f"get_factory_uris_from_xml {self=} {factoriesxml=}" )
        qcs = {}
        #<oslc:QueryCapability>
        #    <oslc:resourceType rdf:resource="http://open-services.net/ns/cm#ChangeRequest"/>
        #    <oslc:queryBase rdf:resource="https://jazz.ibm.com:9443/ccm/oslc/contexts/_2H-_4OpoEemSicvc8AFfxQ/workitems"/>
        # find a queryBase and it's the containing tag that has the info
        for qcx in rdfxml.xml_find_elements(factoriesxml,'.//oslc:CreationFactory'):
            for qcrtx in rdfxml.xml_find_elements( qcx, 'oslc:resourceType'):
                qcs[rdfxml.xmlrdf_get_resource_uri(qcrtx)] = rdfxml.xmlrdf_get_resource_uri(qcx, "oslc:creation")
                logger.debug( f"{rdfxml.xmlrdf_get_resource_uri(qcrtx)=}" )
        return qcs

    def is_user_uri(self, uri):
        logger.info( f"{self=} {self.jts=}" )
        if uri and uri.startswith(self.jts.baseurl) and '/users/' in uri:
            return True
        return False

    def user_uritoname_resolver(self, uri):
        if self.is_user_uri(uri):
            res = uri[uri.rfind("/") + 1:]
            return res
        raise Exception(f"Bad user uri {uri}")

    def is_user_name(self, name):
        logger.info( f"Checking name {name}" )
        if not name or name.startswith( "http:") or name.startswith( "https:"):
            return False
        res = self.user_nametouri_resolver( name,raiseifinvalid=False)
        if res is not None:
            return True
        return False

    def user_nametouri_resolver(self, name, raiseifinvalid=True):
        logger.info( f"Converting name {name}" )
        if not raiseifinvalid or self.is_user_name(name):
            user_uri = self.jts.baseurl+f"users/{name}"
            # check it using whoami
            try:
                res = self.execute_get(user_uri, intent="Try to retrieve User" )
            except requests.exceptions.HTTPError as e:
                res = None
            if res:
                return user_uri
            else:
                if raiseifinvalid:
                    raise Exception( f"User {name} is not known on this server" )
                return None
        raise Exception(f"Bad user  name {name}")

    def resolve_project_nametouri(self, name, raiseifinvalid=True):
        # find project for name
        self._load_projects()
        result = self._projects.get(name)
        logger.debug( f"resolve_project_nametouri {name} {result}" )
        return result

    # return True if the uri can be accessed (used e.g. to detect archived components/configs)
    def is_accessible( self, uri ):
        try:
            res = self.execute_get( uri )
            return True
        except requests.exceptions.HTTPError as e:
            return False
            
#################################################################################################

class JTSApp(_App):
    'The JTS application'
    domain = 'jts'
    project_class = None
    supports_configs = False
    supports_components = False
    supports_reportable_rest = False

    def __init__(self, server, contextroot, jts=None):
        super().__init__(server, contextroot, jts=self)


    def find_project(self, projectname):
        raise Exception("JTS does not have projects!")

