##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import logging

import lxml.etree as ET
import requests

from . import _typesystem
from . import httpops
from . import oslcqueryapi
from . import rdfxml
from . import utils

logger = logging.getLogger(__name__)

#################################################################################################

@utils.mixinomatic
class _Project( oslcqueryapi._OSLCOperations_Mixin, _typesystem.Type_System_Mixin, httpops.HttpOperations_Mixin ):
    'A generic Jazz application project'

    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True):
        logger.info( f'Creating generic project instance {name} {project_uri=} {app=} {is_optin=} {singlemode=} {defaultinit=}' )
        self.app = app
        self.name = name
        self.is_optin = is_optin
        self.singlemode=singlemode
        self.supports_components = False
        self.localconfig = None
        self.project_uri = project_uri  # the project (or component) URI
        self.local_config = None  # the current local config (implies the component)
        self.global_config = None  # the current global config
        self.accept_language = None
        self.headers = {}
        self.component_project = None  # this is set in an RM component, to point at the project
        self._folders = None
        self.services_xml = None
        self.services_uri = None
        self.appcatalog_xml = None
        self.hooks = []
        self.configTree = None # for a walkable tree of configs, alternating baseline->stream->baseline->... - the name property is the UUID, the textname is the visible name, configURL, ismutable, children
        # copy the server from the app - this is so OSLC query can be done on either a project including component) or app
        self.server = app.server
#        self.default_query_sort_property = None

        if defaultinit:
            # get the app oslc catalog
            self.appcatalog_xml = self.app.retrieve_oslc_catalog_xml()
            # if this name is in the catalog, retrieve the services document
            r1 = rdfxml.xml_find_element(self.appcatalog_xml, ".//oslc:ServiceProvider", "./dcterms:title/#text", name)
            logger.info( f"Setting services_uri to {r1=}" )
            self.services_uri = rdfxml.xmlrdf_get_resource_uri( r1 )
            # the services.xml will be retrieved later when needed, because the config to retrieve it in isn't currently known there's no point retrieving it now
        return

    def listmembers( self ):
        pass

    def load_types(self):
        self._load_types()

    # this is a local cache only for the typesystem retrieval
    # the cache deliberately strips off the fragment because it's irrelevant for the GET
    # this makes a lot of the URIs repeats so they are cached
    def _get_typeuri_rdf(self,uri):
        # strip off the fragment as it does nothing
        realuri = uri.rsplit( '#',1 )[0]
        if realuri not in self._gettypecache.keys():
            logger.info( f"Retrieving {uri}" )
#            print( f"Retrieving {uri}" )
            logger.info( utils.callers() )
            try:
                # try to retrieve the rdf using no_error_log=True becase some urls don't exist and we don't really mind if it can't be retrieved, e.g. /jts/users/unassigned which never exits in JTS
                self._gettypecache[realuri] = self.execute_get_rdf_xml(uri, intent="Retrieve type definition", no_error_log=True) if uri.startswith( "https://") else None
                logger.info( f"Retrieved:" )
            except ET.XMLSyntaxError:
                 self._gettypecache[realuri] = None
                 logger.info( "Bad result - ignoring" )
            except requests.HTTPError:
                 self._gettypecache[realuri] = None
                 logger.info( "Bad result - ignoring" )
                
#        print( f"Returning {realuri} {self._gettypecache[realuri]} {ET.tostring(self._gettypecache[realuri])}" )
        return self._gettypecache[realuri]

    def report_type_system( self ):
        self.load_types()
        qcdetails = self.get_query_capability_uris()
        report = "<HTML><BODY>\n"
        report += "<H1>Type system report</H1>\n"

        if self.app.has_typesystem:
            report += "<H2>Application Queryable Resource Types, short name and URI</H2>\n"
            app_qcdetails = self.app.get_query_capability_uris()
            rows = []
            for k in sorted(app_qcdetails.keys()):
                shortname = k.split('#')[-1]
                shortname +=  " (default)" if self.app.default_query_resource is not None and k==rdfxml.tag_to_uri(self.app.default_query_resource) else ""
                rows.append( [shortname,k,app_qcdetails[k]])
            # print in a nice table with equal length columns
            logger.info( f"{rows=}" )
            report += utils.print_in_html(rows,['Short Name', 'URI', 'Query Capability URI'])

        report += "<H2>Project Queryable Resource Types, short name and URI</H2>\n"
        rows = []
        for k in sorted(qcdetails.keys()):
            shortname = k.split('#')[-1]
            shortname +=  " (default)" if self.default_query_resource is not None and k==rdfxml.tag_to_uri(self.default_query_resource) else ""
            rows.append( [shortname,k,qcdetails[k]])
        # print in a nice table with equal length columns
        report += utils.print_in_html(rows,['Short Name', 'URI', 'Query Capability URI'])
        
        report += "<H2>Project Factory Resource Types, short name and URI</H2>\n"
        factorydetails = self.get_factory_uris()
        rows = []
        for k in sorted(factorydetails.keys()):
            shortname = k.split('#')[-1]
            shortname +=  " (default)" if self.default_query_resource is not None and k==rdfxml.tag_to_uri(self.default_query_resource) else ""
            rows.append( [shortname,k,factorydetails[k]])
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

    def get_services_xml(self, headers=None, force=False):
        logger.info( f"get_services_xml {self.name=} {self.project_uri=} {self=} {self.services_uri=}" )
        if force or self.services_xml is None:
            if self.services_uri:
                self.services_xml = self.execute_get_rdf_xml(self.services_uri, headers=headers, intent="Retrieve project's services XML")
                logger.info( f"{self.services_uri=}" )
            elif self.component_project:
                logger.debug( f"component sx not retrieved - need a config" )
            else:
                raise Exception("No services URI")
        return self.services_xml

    def get_query_capability_uri(self,resource_type=None,context=None):
        context = context or self
        resource_type = resource_type or context.default_query_resource
#        print( f"{resource_type=}" )
        return self.app.get_query_capability_uri_from_xml(capabilitiesxml=context.get_services_xml(), resource_type=resource_type,context=context)

    def get_query_capability_uris(self,resource_type=None,context=None):
        context = context or self
        resource_type = resource_type or context.default_query_resource
        return self.app.get_query_capability_uris_from_xml(capabilitiesxml=context.get_services_xml(), context=context)

    def get_factory_uri(self,resource_type=None,context=None, return_shapes=False):
        context = context or self
        resource_type = resource_type or context.default_query_resource
        return self.app.get_factory_uri_from_xml(factoriesxml=context.get_services_xml(), resource_type=resource_type,context=context, return_shapes=return_shapes)

    def get_factory_uris(self,resource_type=None,context=None):
        context = context or self
        resource_type = resource_type or context.default_query_resource
        return self.app.get_factory_uris_from_xml(factoriesxml=context.get_services_xml(),context=context)

    def load_type_from_resource_shape(self, el):
        raise Exception( "This must be provided by the inheriting class!" )

    # get local headers
    def _get_headers(self, headers=None):
        logger.info( f"project_gh" )
        result = {}
        result.update(self.app._get_headers())
        result.update(self._get_oslc_headers())
        # assert the owning context which is the project uri
        result['net.jazz.jfs.owning-context'] = self.project_uri
        if self.local_config or self.global_config:
            # delete the owning context project - use the local configuration instead
            result['net.jazz.jfs.owning-context'] = None
            if self.global_config:
                result['Configuration-Context'] = self.global_config
            else:
                result['Configuration-Context'] = self.local_config
        if self.accept_language:
            result['Accept-Language'] = self.accept_language
        if headers:
            result.update(headers)
        logger.info( f"project_gh {result}" )
        return result

    # get a request with local headers
    def _get_request(self, verb, reluri='', *, params=None, headers=None, data=None):
        fullheaders = self._get_headers()
        if headers is not None:
            fullheaders.update(headers)
        sortedparams = None if params is None else {k:params[k] for k in sorted(params.keys())}
        request = httpops.HttpRequest( self.app.server._session, verb, self.reluri(reluri), params=sortedparams, headers=fullheaders, data=data )
        return request

    @property
    def iid(self):
        return self.project_uri[self.project_uri.rfind('/') + 1:]

    def _get_oslc_headers(self, headers=None):
        result = {
                    'Accept': 'application/rdf+xml',
                    'Referer': self.reluri('web'),
                    'OSLC-Core-Version': '2.0'
                  }
        if headers:
            result.update(headers)
        return result

    def reluri(self, reluri=''):
        return self.app.reluri(reluri)

    def find_config(self, name, nowarning=False):
        return self._do_find_config_by_name(name, nowarning)

    def _do_find_config_by_name(self, name_or_uri, nowarning=False, allow_workspace=True, allow_snapshot=True, allow_changeset=False):
        raise Exception( 'Subclass must implement this method.' )
        
    def get_gc_contributions(self,gcuri):
        result = self.execute_get_json(self.reluri("gcsdk-api/flatListOfContributionsForGcHierarchy"), params={'configurationUri':gcuri,'include':'*'} )
#        print( f"{result=}" )
        return result
    
    # get contributions and component details for just this app
    def get_our_contributions(self, gcuri):
        gc_contribs = self.get_gc_contributions(gcuri)
        results = []
        for contrib in gc_contribs['configurations']:
            if contrib['configurationUri'].startswith(self.reluri()):
                results.append( [contrib['configurationUri'],contrib['componentUri'] ] )
#                print( f"Included {contrib['configurationUri']}" )
            else:
#                print( f"Skipped {contrib['configurationUri']}" )
                pass
#        print( f"{results=}" )
        return results
        
    def set_local_config(self, name_or_uri, global_config_uri=None):
        if name_or_uri:
            if global_config_uri is None:
                config_uri = self._do_find_config_by_name(name_or_uri)
            else:
                # gc and local config both specified - try to avoid loading all the local configs by using the gc tree to locate the local config
                gc_contribs = self.get_gc_contributions(global_config_uri)
                # find the contribution for this component
                config_uri = None
                for config in gc_contribs['configurations']:
#                    print( f"Checking {config=} for {self.project_uri=}" )
                    if config['componentUri'] == self.project_uri:
                        config_uri = config['configurationUri']
            if not config_uri:
                raise Exception( 'Cannot find configuration [%s] in project [%s]' % (name_or_uri, self.uri))
        else:
            config_uri = None

        # set config to this client
        self.local_config = config_uri
        self.global_config = global_config_uri
        # for a component, setting the config is when we can load the services xml!
        if self.component_project:
            # retrieve the services.xml in the current config!
            self.services_xml = self.execute_get_rdf_xml(self.component_project.services_uri, intent="Retrieve project's services.xml")

    # create a changeset in the current config (must be a stream)
    def create_changeset( self, name ):
        raise Exception( "Can't create a changeset on a project!" )
        
    def discard_changeset( self ):
        raise Exception( "Can't discard a changeset on a project!" )
        
    def deliver_changeset( self ):
        raise Exception( "Can't deliver a changeset on a project!" )
        
    def _load_types(self,force=False):
        logger.info( f"{self=}" )
        raise Exception( "This must be implemented by the app-specific project class!" )

    def resolve_shape_name_to_uri(self, name, exception_if_not_found=True):
        logger.info( f"resolve_shape_name_to_uri {name=}" )
        result = self.get_shape_uri(name)
        logger.info( f"resolve_shape_name_to_uri {name=} {result=}" )
        return result

    # for OSLC query, given an attribute (property) name return its type URI
    # the context is the shape definition - can be None, needed to be specified ultimately by the user when property names aren't unique
    def resolve_property_name_to_uri(self, name, shapeuri=None, exception_if_not_found=True):
        logger.info( f"resolve_property_name_to_uri {name=} {shapeuri=}" )
#        result = self.get_property_uri(name,shape_uri=shapeuri) or self.get_linktype_uri(name,shape_uri=shapeuri)
        result = self.get_property_uri(name, shape_uri=shapeuri) or self.get_linktype_uri(name)
        logger.info( f"resolve_property_name_to_uri {name=} {shapeuri=} {result=}" )
        return result

    # for OSLC query, given an enumeration value name in and context (property uri), return its URI
    # the context is the attribute definition - needed to be specified ultimately by the user when enumeration value names aren't unique
    def resolve_enum_name_to_uri(self, name, propertyuri=None, exception_if_not_found=True):
        logger.info( f"resolve_enum_name_to_uri {name=} {propertyuri=}" )
        result = self.get_enum_id(name,propertyuri)
        logger.info( f"resolve_enum_name_to_uri {name=} {propertyuri=} {result=}" )
        return result

    # for OSLC query, given a type URI, return its name
    def resolve_uri_to_name(self, uri, trytouseasid=False):
        logger.debug( f"rutn {uri}" )
        if not uri:
            result = None
            return result
        if not uri.startswith('http://') and not uri.startswith('https://'):
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
        if not trytouseasid and not uri.startswith( "http://" ) and not uri.startswith( "https://" ):
            # not a URI so return it unmodified
            return uri
        if uri.startswith( self.reluri() ) and not self.is_known_uri(uri):
            logger.debug( f"iku" )
            if not uri.startswith(self.app.baseurl) and self.app.server.jts.is_user_uri(uri):
                result = self.app.server.jts.user_uritoname_resolver(uri)
                logger.debug(f"returning user")
                return result
            if ( result := self.app_resolve_uri_to_name(uri) ) is None:
                # why not just retrieve it
                logger.debug( f"iku1" )
                name = self.get_missing_uri_title(uri)
                result = name if name is not None else uri
                logger.debug( f"LOOKUP {uri=} {result=}" )
            else:
                logger.debug( f"iku2" )
                logger.info( f"{result=}" )
#            self.register_name(result,uri)
        elif trytouseasid:
            # assume it's an id
            result = self.enums.get(uri)            
            if not result:
                split = uri.rsplit("/",1)[-1]
                
                result = self.enums.get(uri.rsplit("/",1)[-1])            
                raise Exception( "this should not happen!" )
        else:
            result = self.get_uri_name(uri)
#            print( f"1 {uri=} {self.get_uri_name(uri)}")
#            result = rdfxml.uri_to_default_prefixed_tag( uri )
#            print( f"2 {uri=} {result=}")
            
            if result is None:
                if uri.startswith( self.reluri("/") ) or rdfxml.startswith_known_prefix( uri ):
                    if '#' in uri:
                        result = uri.rsplit( "#",1)[1]
                    elif "/" in uri:
                        result = uri.rsplit( "/",1)[1]
                    else:
                        result = rdfxml.uri_to_default_prefixed_tag( uri )
                else:
                    result = uri
        logger.debug( f"rutn {uri=} {result=}" )
        return result

    def get_missing_uri_title( self,uri):
        if uri.startswith( "http://" ) or uri.startswith( "https://" ):
            uri1 = rdfxml.uri_to_prefixed_tag(uri)
            logger.debug( f"Returning the raw URI {uri} so changed it to prefixed {uri1}" )
            uri = uri1
        result = uri
        return result


    def find_component( self, name_or_uri ):
        raise Exception("This function must nbe implemented by an app-specific class which inherits from Project")

    def load_folder(self):
        raise Exception( "Folders not supported by this type of project!" )

    def folder_nametouri_resolver(self,name_or_uri):
        raise Exception( "Folders not supported by this type of project!" )

    def folder_uritoname_resolver(self,name_or_uri):
        raise Exception( "Folders not supported by this type of project!" )

    def resolve_reqid_to_uri( self, reqid ):
        raise Exception( "ID syntax only supported for RM" )

    def resolve_uri_to_reqid( self, requri ):
        raise Exception( "ID syntax only supported for RM" )

    def initial_stream_name(self):
        return self.name+" Initial Stream"

    def report_components_and_configurations(self):
        self.load_components_and_configurations()
        return self._components

    def user_nametouri_resolver(self, name, raiseifinvalid=True):
        return self.app.user_nametouri_resolver( name, raiseifinvalid=raiseifinvalid)

    def user_uritoname_resolver(self, uri):
        return self.app.user_uritoname_resolver( uri )

    def resolve_project_nametouri(self, name, raiseifinvalid=True):
        return self.app.resolve_project_nametouri( name, raiseifinvalid=raiseifinvalid)

    def _generic_load_type_from_resource_shape(self, el, supershape=None):
        logger.debug( "Starting a shape")
        uri = rdfxml.xmlrdf_get_resource_uri(el)
        logger.info( f"Starting resource {uri}" )
        try:
            if not self.is_known_shape_uri(uri):
#                if '/shape/resource/' in uri:
#                    burp
#                if not '/shape/resource/' in uri:
#                    print( f"Skipping {uri}" )
#                    return
                logger.info( f"Starting shape {uri} =======================================" )
                logger.debug( f"Getting {uri}" )
                shapedef_x = self._get_typeuri_rdf(uri)
                # find the title
                name_el = rdfxml.xml_find_element(shapedef_x, f'.//rdf:Description[@rdf:about="{uri}"]/dcterms:title[@xml:lang="en"]')
                if name_el is None:
                    name_el = rdfxml.xml_find_element(shapedef_x, f'.//rdf:Description[@rdf:about="{uri}"]/dcterms:title[@rdf:datatype]')
                if name_el is None:
                    logger.info( f"{uri=}" )
                    if '#' in uri:
                        name = uri.rsplit('#',1)[1]
                    else:
                        logger.info( f"No #! {uri}" )
                        name = uri.rsplit('.',1)[1]
                    logger.info( f"MADE UP NAME {name}" )
                else:
#                    print( "NO NAME",ET.tostring(shapedef_x) )
#                    raise Exception( "No name element!" )
                    name = name_el.text
                if '/shape/resource/' not in uri:
                    name += "_"+str(len(uri))       
                # this is so that the variant type URIs don't overwrite the /shape/resource one
                self.register_shape( name, uri )
#                else:
#                    print( f"Ignored 1 non-resource {uri}" )
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

        for enumdef in rdfxml.xml_find_elements( shapedef_x, './/rdf:Description/owl:sameAs/..' ):
            # register enumdefs
            pass
        n = 0
        # find the list of attributes on this shape
        thisshapedefs_x = rdfxml.xml_find_elements( shapedef_x,f'.//rdf:Description[@rdf:about="{uri}"]' )
        if thisshapedefs_x is None:
            raise Exception( f"Shape definition for {uri} not found!" )
        if len(thisshapedefs_x)==0 or len(thisshapedefs_x)>1:
            raise Exception ( f"Too few/many results {len(thisshapedefs_x)}" )
        thisshapedef_x = thisshapedefs_x[0]
#        print( f"thisshapedef_x=",ET.tostring(thisshapedef_x) )
        title = rdfxml.xmlrdf_get_resource_text(thisshapedef_x,'./dcterms:title[@xml:lang="en"]')
        if title is None:
            title = rdfxml.xmlrdf_get_resource_text(thisshapedef_x,'./dcterms:title')
        logger.info( f"{title=}" )
#        logger.info( f"shape {title} xml={ET.tostring(thisshapedef_x)}" )
        # scan the attributes
        logger.info( f"{ET.tostring(thisshapedef_x)=}" )
        for propel in rdfxml.xml_find_elements( thisshapedef_x, './oslc:property' ):
            logger.info( "Starting a property")
            propnodeid = rdfxml.xmlrdf_get_resource_uri( propel, attrib="rdf:nodeID" )
            logger.info( f"{propnodeid=}" )
            logger.info( f"{propnodeid=}" )
            real_propel_x = rdfxml.xml_find_element( shapedef_x, f'.//rdf:Description[@rdf:nodeID="{propnodeid}"]' )
            logger.info( f"{real_propel_x=}" )
            logger.info( f"{real_propel_x=}" )
#            print( "XML==",ET.tostring(real_propel_x) )
            # dcterms:title xml:lang="en"
            property_title_el = rdfxml.xml_find_element( real_propel_x, './dcterms:title[@xml:lang="en"]')
            logger.info( f"1 {property_title_el=}" )
            if property_title_el is None:
                property_title_el = rdfxml.xml_find_element(real_propel_x, './dcterms:title[@rdf:datatype]' )
                logger.info( f"2 {property_title_el=}" )
            if property_title_el is None:
                property_title_el = rdfxml.xml_find_element( real_propel_x, './oslc:name')
                logger.info( f"3 {property_title_el=}" )
            logger.info( f"{property_title_el=}" )
            logger.info( f"{property_title_el=}" )
            if property_title_el is None:
                logger.info( "Skipping shape with no title!" )
                logger.info( "Skipping shape with no title!" )
                burp
                continue
            property_title = property_title_el.text
            logger.info( f"{property_title=}" )
            logger.info( f"{property_title=}" )
            if rdfxml.xmlrdf_get_resource_text(real_propel_x,"oslc:hidden") == "true":
                logger.info( f"Skipping hidden property {property_title}" )
                logger.info( f"Skipping hidden property {property_title}" )
                continue
            valueshape_uri = rdfxml.xmlrdf_get_resource_uri( real_propel_x,'./oslc:valueShape' )
            logger.info( f"{valueshape_uri=}" )
            if valueshape_uri is not None:
                logger.info( f"vs {valueshape_uri}" )
                # register this property with a fake URI using the node id
                propu = f"{uri}#{propnodeid}"
                if '/shape/resource/' in uri:
                    self.register_property( property_title, propu, shape_uri=uri )
                else:
                    logger.info( f"Ignored 2 non-resource {uri}" )
                    
                if valueshape_uri.startswith( self.app.baseurl ) and valueshape_uri != uri:
                    # this shape references another shape - need to load this!
                    vs_xml = self._get_typeuri_rdf(valueshape_uri)
                    subshape_x = rdfxml.xml_find_element( vs_xml,f'.//rdf:Description[@rdf:about="{valueshape_uri}"]' )
                    if subshape_x is None:
                        logger.info( f"SubShape definition for {valueshape_uri} not found!" )
                        continue
                    # recurse to load this shape!
                    logger.info( f"SUBSHAPE_X={valueshape_uri}" )
                    self._load_type_from_resource_shape( subshape_x, supershape=(property_title,propu))
                else:
                    logger.info( f"SKIPPED external shape {valueshape_uri=}" )
            else:
#                logger.debug( f"{valueshape_uri=}" )
#                if not valueshape_uri.startswith( self.app.baseurl):
#                    logger.info( f"Shape definition isn't local to the app {self.app.baseurl=} {uri=}" )
#                    continue
                pd_u = rdfxml.xmlrdf_get_resource_uri( real_propel_x, 'oslc:propertyDefinition' )

                # In case of repeated identical property titles on a shape, let's create an alternative name that can (perhaps) be used to disambiguate
                # (at least these don't have duplicates AFAICT)
                altname  = pd_u[pd_u.rfind("/")+1:]
                if '#' in altname:
                    altname  = pd_u[pd_u.rfind("#")+1:]

                if pd_u is not None:
                    if not pd_u.startswith( self.app.baseurl ):
                        if '/shape/resource/' in uri:
                            self.register_property(property_title,pd_u, altname=altname, shape_uri=uri )
                        else:
                            logger.info( f"Ignored 3 non-resource {uri}" )
                        logger.debug( f"+++++++Skipping non-local Property Definition {pd_u}" )
#                        continue
                else:
                    logger.debug( f"~~~~~~~Ignoring non-local Property Definition {pd_u}" )

                if self.is_known_property_uri( pd_u, raiseifnotfound=False ):
                    logger.debug( f"ALREADY KNOWN2" )
                    continue

                logger.info( f"Defining property {title}.{property_title} {altname=} {pd_u=} +++++++++++++++++++++++++++++++++++++++" )
                if '/shape/resource/' in uri:
                    self.register_property( property_title, pd_u, altname=altname, shape_uri=uri)
                else:
                    logger.info( f"Ignored 4 non-resource {uri}" )
                # check for any allowed value
                allowedvalueu = rdfxml.xmlrdf_get_resource_uri(real_propel_x, ".//oslc:allowedValue" )
                logger.info( f"{uri=} {allowedvalueu=}" )
                if allowedvalueu is not None:
                    logger.info( "FOUND ENUM" )
                    # this has enumerations - find them and record them
                    # retrieve each definition
                    nvals = 0
                    for allowedvaluex in rdfxml.xml_find_elements( real_propel_x,'.//oslc:allowedValue'):
                        allowedvalueu = rdfxml.xmlrdf_get_resource_uri(allowedvaluex )
                        if allowedvalueu.startswith( 'http:' ) or allowedvalueu.startswith( 'https:' ):
                            # a URL
                            thisenumx = rdfxml.xml_find_element( shapedef_x,f'.//rdf:Description[@rdf:about="{allowedvalueu}"]' )

                            enum_uri = allowedvalueu
                            logger.info( f"{enum_uri=}" )
                            nvals += 1
                            if not self.is_known_enum_uri( enum_uri ):
                                # retrieve it and save the enumeration name and uri in types cache
                                enum_value_name = rdfxml.xmlrdf_get_resource_text(thisenumx, 'rdfs:label')
                                enum_id = enum_value_name
                                if enum_value_name is None:
                                    logger.debug( "enum xml=",ET.tostring(thisenumx) )
                                    logger.debug( f"{enum_id=} no name" )
                                    raise Exception( "Enum name not present!" )

                                logger.info( f"defining enum value {enum_value_name=} {enum_id=} {enum_uri=}" )
                                self.register_enum( enum_value_name, enum_uri, property_uri=pd_u, id=None )
                        else:
                            # an enum name (not sure why QM does this)
                            logger.info( f"ENUM NAME {allowedvalueu}" )
                            nvals += 1
                            self.register_enum( allowedvalueu, allowedvalueu, property_uri=pd_u, id=None )
                            
                            pass
                    if nvals==0:
                        raise Exception( f"Enumeration {valueshape_uri} with no values loaded" )
        logger.debug( "Finished loading typesystem")
        return n
