##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


#################################################################################################

# GCM API documentation https://jazz.net/gc/doc/scenarios

#
# This is a skeleton implementation for GC - just enough to support finding a GC configuration (using OSLC query to GC) either in a project or across all projects
#

#################################################################################################

import logging

import requests
import lxml.etree as ET
import tqdm

from . import _app
from . import _project
from . import _typesystem
from . import oslcqueryapi
from . import rdfxml
from . import server
from . import utils

logger = logging.getLogger(__name__)

#################################################################################################

# hook to adapt OSLC query parameters needed for GC - no orderBy, prefixes must NOT include dcterms
def _hook_beforequery(querydetails):
    # remove orderby
    if 'orderBy' in querydetails:
        del querydetails['orderBy']
    # make sure dcterms and oslc not in prefix
    if 'dcterms=' in querydetails.get('oslc.prefix',"") or 'oslc' in querydetails.get('oslc.prefix',"") or 'rdf' in querydetails.get('oslc.prefix',""):
        oldprefix = querydetails['oslc.prefix']
        prefixes = oldprefix.split(",")
        newprefixes = [p for p in prefixes if not p.startswith("dcterms=") and not p.startswith("oslc=") and not p.startswith("rdf=")]
        querydetails['oslc.prefix'] = ",".join(newprefixes)
        newprefix = querydetails['oslc.prefix']
    return querydetails

#################################################################################################

class _GCMProject(_project._Project):
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=True):
        super().__init__(name, project_uri, app, is_optin,singlemode, defaultinit=False)
        self.hooks = [_hook_beforequery]
        self._components = None  # will become a dict keyed on component uri
        self._configurations = None # keyed on the config name
        self.default_query_resource = 'oslc_config:Configuration'

        # nonstandard initialisation - difference is in finding the services XML for the project - for
        # some reason GCM uses oslc:serviceProvider and doesn't include the project name whereas at
        # least RM uses oslc:ServiceProvider! and does include the project name - that's what the default initialisation assumes

        # we could retrieve each of these to check the title, but using the project iid to find the correct services xml URL works well enough

        # get the app oslc catalog (this is different from the other apps!)
        appcatalog_xml = self.app.retrieve_oslc_catalog_xml()
        self.services_uri = None
        for sp in rdfxml.xml_find_elements(appcatalog_xml, ".//oslc:serviceProvider"):
            spuri = rdfxml.xmlrdf_get_resource_uri( sp )
            if spuri.endswith( self.iid):
                self.services_uri = spuri
                break

        if not self.services_uri:
            raise Exception( "Service provide not found!" )
        if self.services_uri:
            self.services_xml = self.app.execute_get_rdf_xml( self.services_uri, intent="Retrieve project services xml" )
        else:
            self.services_xml = None

    def find_local_component(self, name_or_uri):
        self.load_components_and_configurations()
        for compuri, compdetail in self._components.items():
            logger.info( f"Checking {name_or_uri} {compdetail}" )
            if compuri == name_or_uri or compdetail['name'] == name_or_uri:
                return compdetail['component']
        return None

    def load_components_and_configurations(self,force=False):
        if self._components is not None and self._configurations is not None and not force:
            return
        self._components = {}
        self._configurations = {}
        ncomps = 0
        nconfs = 0
        # retrieve components and configurations for this project
        # use OSLC query to get all components in this project
        comps = self.do_complex_query( "http://open-services.net/ns/config#Component", querystring=None, select='dcterms:title', show_progress=False, verbose=False )

        logger.debug( f"{comps=}" )

        for compu,v in comps.items():
            self._components[compu] = {'name': v['dcterms:title'], 'configurations': {}}
            logger.debug( f"{self._components[compu]=}" )

        # now create the "components"
        for cu, cd in self._components.items():
            logger.debug( f"{cu=} {cd=}" )
            cname = cd['name']
            c = self
            c._configurations = self._components[cu]['configurations']
            self._components[cu]['component'] = c
        return (ncomps, nconfs)

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

            pbar = tqdm.tqdm(initial=0, total=len(shapes_to_load),smoothing=1,unit=" results",desc="Loading GCM project shapes")

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

    def _generic_load_type_from_resource_shape(self, el, supershape=None):
        logger.debug( "Starting a shape")
        uri = rdfxml.xmlrdf_get_resource_uri(el)
        try:
            if not self.is_known_shape_uri(uri):
                logger.info( f"Starting shape {uri} =======================================" )
                logger.debug( f"Getting {uri}" )
                shapedef = self._get_typeuri_rdf(uri)
                # find the title
                name_el = rdfxml.xml_find_element(shapedef, f'.//rdf:Description[@rdf:about="{uri}"]/dcterms:title[@xml:lang="en"]')
                if name_el is None:
                    name_el = rdfxml.xml_find_element(shapedef, f'.//rdf:Description[@rdf:about="{uri}"]/dcterms:title')
                if name_el is None:
                    name = uri.rsplit('#',1)[1]
                    logger.info( f"MADE UP NAME {name}" )
                else:
#                    print( "NO NAME",ET.tostring(shapedef) )
#                    raise Exception( "No name element!" )
                    name = name_el.text
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

        n = 0
        # find the list of attributes
        thisshapedef = rdfxml.xml_find_element( shapedef,f'.//rdf:Description[@rdf:about="{uri}"]' )
        if thisshapedef is None:
            raise Exception( f"Shape definition for {uri} not found!" )
#        print( f"thisshapedef=",ET.tostring(thisshapedef) )
        title = rdfxml.xmlrdf_get_resource_text(thisshapedef,'./dcterms:title[@xml:lang="en"]')
        if title is None:
            title = rdfxml.xmlrdf_get_resource_text(thisshapedef,'./dcterms:title')

#        logger.info( f"shape {title} xml={ET.tostring(thisshapedef)}" )
        # scan the attributes
        for propel in rdfxml.xml_find_elements( thisshapedef,'./oslc:property' ):
            logger.info( "Starting a property")
            propnodeid = rdfxml.xmlrdf_get_resource_uri(propel,attrib="rdf:nodeID")
            logger.info( f"{propnodeid=}" )
            real_propel = rdfxml.xml_find_element(shapedef, f'.//rdf:Description[@rdf:nodeID="{propnodeid}"]')
            logger.info( f"{real_propel=}" )
#            print( "XML==",ET.tostring(real_propel) )
            # dcterms:title xml:lang="en"
            property_title_el = rdfxml.xml_find_element(real_propel, './dcterms:title[@xml:lang="en"]')
            if property_title_el is None:
                property_title_el = rdfxml.xml_find_element(real_propel, './dcterms:title')
            logger.info( f"{property_title_el=}" )
            if property_title_el is None:
                logger.info( "Skipping shape with no title!" )
                continue
            property_title = property_title_el.text
            logger.info( f"{property_title=}" )
            if rdfxml.xmlrdf_get_resource_text(propel,"oslc:hidden") == "true":
                logger.info( f"Skipping hidden property {property_title}" )
                continue
            valueshape_uri = rdfxml.xmlrdf_get_resource_uri(real_propel,'./oslc:valueShape')
            if valueshape_uri is not None:
                logger.info( f"vs {valueshape_uri}" )
                # register this property with a fake URI using the node id
                propu = f"{uri}#{propnodeid}"
                self.register_property( property_title, propu, shape_uri=uri )
                if valueshape_uri.startswith( self.app.baseurl):
                    # this shape references another shape - need to load this!
                    vs_xml = self._get_typeuri_rdf(valueshape_uri)
                    subshape_x = rdfxml.xml_find_element( vs_xml,f'.//rdf:Description[@rdf:about="{valueshape_uri}"]' )
                    if subshape_x is None:
#                        print( f"\n\nSUBSHAPE_X=",ET.tostring( vs_xml),"\n\n" )
                        logger.info( f"SubShape definition for {valueshape_uri} not found!" )
                        continue
                    # recurse to load this shape!
                    self._load_type_from_resource_shape( subshape_x, supershape=(property_title,propu))
                else:
                    logger.info( f"SKIPPED external shape {valueshape_uri=}" )
            else:
                logger.debug( f"{valueshape_uri=}" )
#                if valueshape_uri is None or not valueshape_uri.startswith( self.baseurl):
#                    if not valueshape_uri:
#                        valueshape_uri = f"{uri}#{propnodeid}"
#                    if not self.is_known_property_uri( valueshape_uri ):
#                        # define it
#                        self.register_property( property_title, valueshape_uri, shape_uri=uri )
#                        continue
#                    else:
#                        logger.debug( f"ALREADY KNOWN" )
#                        continue

                pd_u = rdfxml.xmlrdf_get_resource_uri( real_propel, 'oslc:propertyDefinition' )

                # In case of repeated identical property titles on a shape, let's create an alternative name that can (perhaps) be used to disambiguate
                # (at least these don't have duplicates AFAICT)
                altname  = pd_u[pd_u.rfind("/")+1:]
                if '#' in altname:
                    altname  = pd_u[pd_u.rfind("#")+1:]

                if pd_u is not None:
                    if not pd_u.startswith( self.app.baseurl ):
                        self.register_property(property_title,pd_u, shape_uri=uri, altname=altname)
                        logger.debug( f"+++++++Skipping non-local Property Definition {pd_u}" )
                        continue
                else:
                    logger.debug( f"~~~~~~~Ignoring non-local Property Definition {pd_u}" )

                if self.is_known_property_uri( pd_u,shape_uri=uri,raiseifnotfound=False ):
                    logger.debug( f"ALREADY KNOWN2" )
                    continue

                logger.info( f"Defining property {title}.{property_title} {altname=} {pd_u=} +++++++++++++++++++++++++++++++++++++++" )
                self.register_property(property_title,pd_u, shape_uri=uri, altname=altname)
                # check for any allowed value
                allowedvalueu = rdfxml.xmlrdf_get_resource_uri(real_propel, ".//oslc:allowedValue" )
                if allowedvalueu is not None:
                    logger.info( "FOUND ENUM" )
                    # this has enumerations - find them and record them
                    # retrieve each definition
                    nvals = 0
                    for allowedvaluex in rdfxml.xml_find_elements( real_propel,'.//oslc:allowedValue'):
                        allowedvalueu = rdfxml.xmlrdf_get_resource_uri(allowedvaluex )

                        thisenumx = rdfxml.xml_find_element( shapedef,f'.//rdf:Description[@rdf:about="{allowedvalueu}"]' )

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

                    if nvals==0:
                        raise Exception( f"Enumeration {valueshape_uri} with no values loaded" )
        logger.debug( "Finished loading typesystem")
        return n

    # this is a local cache only for the typesystem retrieval
    # the cache deliberately strips off the fragment because it's irrelevant for the GET
    # this makes a lot of the URIs repeats so they are cached
    def _get_typeuri_rdf(self,uri):
        # strip off the fragment as it does nothing
        realuri = uri.rsplit( '#',1 )[0]
        if realuri not in self._gettypecache.keys():
            self._gettypecache[realuri] = self.execute_get_rdf_xml( uri, intent="Retrieve project/component type definition to cache it" )
        return self._gettypecache[realuri]

    # for OSLC query, given a type URI, return its name
    # gcm-specific resolution
    def app_resolve_uri_to_name(self, uri):
        result = None
        return result

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


#################################################################################################

class _GCMComponent(_GCMProject):
    pass

#################################################################################################

@utils.mixinomatic
class GCMApp(_app._App, oslcqueryapi._OSLCOperations_Mixin, _typesystem.Type_System_Mixin):
    domain = 'gc'
    project_class = _GCMProject
    supports_configs = False
    supports_components = True
    supports_reportable_rest = False

    relprefixes = (
            ('acclist','acclist#')
            ,('serviceProvider','oslc-config/serviceProvider/')
            ,('component','component/')
            ,('configuration','configuration/')
            ,('part','part/')
        )
    identifier_name = 'Short ID'
    identifier_uri = 'Identifier'

    def __init__(self, server, contextroot, jts=None):
        super().__init__(server, contextroot, jts=jts)

        self.rootservices_xml = self.execute_get_xml(self.reluri('rootservices'), intent="Retrieve GCM application rootservices" )
        self.serviceproviders = 'gc:globalConfigServiceProviders'
        self.default_query_resource = 'oslc_config:Configuration'
        # load all projects and components?
        # register some app-specific namespaces
        for prefix,reluri in self.relprefixes:
            rdfxml.addprefix(prefix,self.baseurl+reluri)
        self.hooks = [_hook_beforequery]
        self.iid = None
#        self._type_system = _typesystem.Type_System()
#        self._gettypecache = {}

    def _get_headers(self, headers=None):
        result = super()._get_headers()
        result['net.jazz.jfs.owning-context'] = self.baseurl
        if headers:
            result.update(headers)
        return result

    # returns a dictionary of resource type to query capability URI
    # this is here because for the GCM app the xml is structured differently for the app
    def get_query_capability_uris_from_xml(self,capabilitiesxml,context):
        logger.info( f"GCM gqcusfx" )
        qcs = {}
        if context.iid:
            # project
            #<oslc:QueryCapability>
            #    <oslc:resourceType rdf:resource="http://open-services.net/ns/cm#ChangeRequest"/>
            #    <oslc:queryBase rdf:resource="https://jazz.ibm.com:9443/ccm/oslc/contexts/_2H-_4OpoEemSicvc8AFfxQ/workitems"/>
            # find a queryBase and it's the containing tag that has the info
            for qcx in rdfxml.xml_find_elements(capabilitiesxml,'.//oslc:queryBase/..'):
                for qcrtx in rdfxml.xml_find_elements( qcx, 'oslc:resourceType'):
                    qcs[rdfxml.xmlrdf_get_resource_uri(qcrtx)] = rdfxml.xmlrdf_get_resource_uri(qcx, "oslc:queryBase")
                    logger.debug( f"{rdfxml.xmlrdf_get_resource_uri(qcrtx)=}" )
                    logger.info( f"GCM Project get_query_capability_uris_from_xml returning {qcs=}" )
        else:
            # app
            sps = rdfxml.xml_find_elements(capabilitiesxml,".//oslc:serviceProvider")
            found=False
            for sp in sps:
                spurl = rdfxml.xmlrdf_get_resource_uri(sp)
                if spurl.endswith("serviceProvider"):
                    found=True
                    break
            if not found:
                raise Exception( "No empty service provider found!" )
            sx = self.execute_get_rdf_xml( spurl, intent="Retrieve project/component service provider definition to find query capability" )
            for qcx in rdfxml.xml_find_elements(sx,'.//oslc:queryBase/..'):
                for qcrtx in rdfxml.xml_find_elements( qcx, 'oslc:resourceType'):
                    qcs[rdfxml.xmlrdf_get_resource_uri(qcrtx)] = rdfxml.xmlrdf_get_resource_uri(qcx, "oslc:queryBase")
                    logger.debug( f"{rdfxml.xmlrdf_get_resource_uri(qcrtx)=}" )
            logger.info( f"GCM App get_query_capability_uris_from_xml returning {qcs=}" )

        return qcs

    def check_valid_config_uri( self, uri, raise_exception=True ):
        try:
            x = self.rootservices_xml = self.execute_get_xml( uri, intent="Check if configuration URL is valid (gets a response)" )
        except requests.HTTPError:
            if raiseException:
                raise
            return False
        return True


    # load the typesystem using the OSLC shape resources listed for all the creation factories and query capabilities
    def load_types(self, force=False):
        self._load_types(force)

    # load the typesystem using the OSLC shape resources listed for all the creation factories and query capabilities
    def _load_types(self,force=False):
        logger.debug( f"load type {self=} {force=}" )
        # if already loaded, try to avoid reloading
        if self.typesystem_loaded and not force:
            return

        self.clear_typesystem()

        # app
        capabilitiesxml = self.retrieve_cm_service_provider_xml()
        sps = rdfxml.xml_find_elements(capabilitiesxml,".//oslc:serviceProvider")
        found=False
        for sp in sps:
            spurl = rdfxml.xmlrdf_get_resource_uri(sp)
            if spurl.endswith("serviceProvider"):
                found=True
                break
        if not found:
            raise Exception( "No empty service provider found!" )
        sx = self.execute_get_rdf_xml( spurl, intent="Retrieve project/component service provider XML" )
        if sx:
            shapes_to_load = rdfxml.xml_find_elements(sx, './/oslc:resourceShape' )
            pbar = tqdm.tqdm(initial=0, total=len(shapes_to_load),smoothing=1,unit=" results",desc="Loading GCM app shapes")

            for el in shapes_to_load:
                self._load_type_from_resource_shape(el)
                pbar.update(1)

            pbar.close()

        else:
            raise Exception( "services xml not found!" )
        return None

    # pick all the attributes from a resource shape definition
    # and for enumerated attributes get all the enumeration values
    def _load_type_from_resource_shape(self, el, supershape=None):
        return self._generic_load_type_from_resource_shape(el, supershape=None)

    def _generic_load_type_from_resource_shape(self, el, supershape=None):
        logger.debug( "Starting a shape")
        uri = rdfxml.xmlrdf_get_resource_uri(el)
        try:
            if not self.is_known_shape_uri(uri):
                logger.info( f"Starting shape {uri} =======================================" )
                logger.debug( f"Getting {uri}" )
                shapedef = self._get_typeuri_rdf(uri)
                # find the title
                name_el = rdfxml.xml_find_element(shapedef, f'.//rdf:Description[@rdf:about="{uri}"]/dcterms:title[@xml:lang="en"]')
                if name_el is None:
                    name_el = rdfxml.xml_find_element(shapedef, f'.//rdf:Description[@rdf:about="{uri}"]/dcterms:title')
                if name_el is None:
                    name = uri.rsplit('#',1)[1]
                    logger.info( f"MADE UP NAME {name}" )
                else:
#                    print( "NO NAME",ET.tostring(shapedef) )
#                    raise Exception( "No name element!" )
                    name = name_el.text
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

        n = 0
        # find the list of attributes
        thisshapedef = rdfxml.xml_find_element( shapedef,f'.//rdf:Description[@rdf:about="{uri}"]' )
        if thisshapedef is None:
            raise Exception( f"Shape definition for {uri} not found!" )
#        print( f"thisshapedef=",ET.tostring(thisshapedef) )
        title = rdfxml.xmlrdf_get_resource_text(thisshapedef,'./dcterms:title[@xml:lang="en"]')
        if title is None:
            title = rdfxml.xmlrdf_get_resource_text(thisshapedef,'./dcterms:title')

#        logger.info( f"shape {title} xml={ET.tostring(thisshapedef)}" )
        # scan the attributes
        for propel in rdfxml.xml_find_elements( thisshapedef,'./oslc:property' ):
            logger.info( "Starting a property")
            propnodeid = rdfxml.xmlrdf_get_resource_uri(propel,attrib="rdf:nodeID")
            logger.info( f"{propnodeid=}" )
            real_propel = rdfxml.xml_find_element(shapedef, f'.//rdf:Description[@rdf:nodeID="{propnodeid}"]')
            logger.info( f"{real_propel=}" )
#            print( "XML==",ET.tostring(real_propel) )
            # dcterms:title xml:lang="en"
            property_title_el = rdfxml.xml_find_element(real_propel, './dcterms:title[@xml:lang="en"]')
            if property_title_el is None:
                property_title_el = rdfxml.xml_find_element(real_propel, './dcterms:title')
            logger.info( f"{property_title_el=}" )
            if property_title_el is None:
                logger.info( "Skipping shape with no title!" )
                continue
            property_title = property_title_el.text
            logger.info( f"{property_title=}" )
            if rdfxml.xmlrdf_get_resource_text(propel,"oslc:hidden") == "true":
                logger.info( f"Skipping hidden property {property_title}" )
                continue
            valueshape_uri = rdfxml.xmlrdf_get_resource_uri(real_propel,'./oslc:valueShape')
            if valueshape_uri is not None:
                logger.info( f"vs {valueshape_uri}" )
                # register this property with a fake URI using the node id
                propu = f"{uri}#{propnodeid}"
                self.register_property( property_title, propu, shape_uri=uri )
                if valueshape_uri.startswith( self.baseurl):
                    # this shape references another shape - need to load this!
                    vs_xml = self._get_typeuri_rdf(valueshape_uri)
                    subshape_x = rdfxml.xml_find_element( vs_xml,f'.//rdf:Description[@rdf:about="{valueshape_uri}"]' )
                    if subshape_x is None:
#                        print( f"\n\nSUBSHAPE_X=",ET.tostring( vs_xml),"\n\n" )
                        logger.info( f"SubShape definition for {valueshape_uri} not found!" )
                        continue
                    # recurse to load this shape!
                    self._load_type_from_resource_shape( subshape_x, supershape=(property_title,propu))
                else:
                    logger.info( f"SKIPPED external shape {valueshape_uri=}" )
            else:
                logger.debug( f"{valueshape_uri=}" )
#                if valueshape_uri is None or not valueshape_uri.startswith( self.baseurl):
#                    if not valueshape_uri:
#                        valueshape_uri = f"{uri}#{propnodeid}"
#                    if not self.is_known_property_uri( valueshape_uri ):
#                        # define it
#                        self.register_property( property_title, valueshape_uri, shape_uri=uri )
#                        continue
#                    else:
#                        logger.debug( f"ALREADY KNOWN" )
#                        continue

                pd_u = rdfxml.xmlrdf_get_resource_uri( real_propel, 'oslc:propertyDefinition' )

                # In case of repeated identical property titles on a shape, let's create an alternative name that can (perhaps) be used to disambiguate
                # (at least these don't have duplicates AFAICT)
                altname  = pd_u[pd_u.rfind("/")+1:]
                if '#' in altname:
                    altname  = pd_u[pd_u.rfind("#")+1:]

                if pd_u is not None:
                    if not pd_u.startswith( self.baseurl ):
                        self.register_property(property_title,pd_u, shape_uri=uri, altname=altname)
                        logger.debug( f"+++++++Skipping non-local Property Definition {pd_u}" )
                        continue
                else:
                    logger.debug( f"~~~~~~~Ignoring non-local Property Definition {pd_u}" )

                if self.is_known_property_uri( pd_u,shape_uri=uri,raiseifnotfound=False ):
                    logger.debug( f"ALREADY KNOWN2" )
                    continue
                logger.info( f"Defining property {title}.{property_title} {altname=} {pd_u=} +++++++++++++++++++++++++++++++++++++++" )
                self.register_property(property_title,pd_u, shape_uri=uri, altname=altname)
                # check for any allowed value
                allowedvalueu = rdfxml.xmlrdf_get_resource_uri(real_propel, ".//oslc:allowedValue" )
                if allowedvalueu is not None:
                    logger.info( "FOUND ENUM" )
                    # this has enumerations - find them and record them
                    # retrieve each definition
                    nvals = 0
                    for allowedvaluex in rdfxml.xml_find_elements( real_propel,'.//oslc:allowedValue'):
                        allowedvalueu = rdfxml.xmlrdf_get_resource_uri(allowedvaluex )

                        thisenumx = rdfxml.xml_find_element( shapedef,f'.//rdf:Description[@rdf:about="{allowedvalueu}"]' )

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

                    if nvals==0:
                        raise Exception( f"Enumeration {valueshape_uri} with no values loaded" )
        logger.debug( "Finished loading typesystem")
        return n

    # this is a local cache only for the typesystem retrieval
    # the cache deliberately strips off the fragment because it's irrelevant for the GET
    # this makes a lot of the URIs repeats so they are cached
    def _get_typeuri_rdf(self,uri):
        # strip off the fragment as it does nothing
        realuri = uri.rsplit( '#',1 )[0]
        if realuri not in self._gettypecache.keys():
            self._gettypecache[realuri] = self.execute_get_rdf_xml(uri,intent="Retrieve type definition" )
        return self._gettypecache[realuri]

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
        
    # for OSLC query, given an attribute (property) name return its type URI
    # the context is the shape definition - can be None, needed to be specified ultimately by the user when property names aren't unique
    def resolve_property_name_to_uri(self, name, shapeuri=None, exception_if_not_found=True):
        logger.info( f"resolve_property_name_to_uri {name=} {shapeuri=}" )
        result = self.get_property_uri(name,shape_uri=shapeuri)
        logger.info( f"resolve_property_name_to_uri {name=} {shapeuri=} {result=}" )
        return result
