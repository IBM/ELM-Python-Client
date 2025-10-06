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
from . import resource

#################################################################################################

logger = logging.getLogger(__name__)

#################################################################################################


class BuildDefinitionResource         (resource.Resource):
    pass
class BuildRecordResource(resource.Resource):
    pass
class KeywordResource                 (resource.Resource):
    pass
class TestDataResource                (resource.Resource):
    pass
class TestPhaseResource            (resource.Resource):
    pass
class TestSuiteResource             (resource.Resource):
    pass
class TestSuiteExecutionRecordResource(resource.Resource):
    pass
class TestSuiteResultResource         (resource.Resource):
    pass
class TestCaseResource                (resource.Resource):
    pass
class TestExecutionRecordResource     (resource.Resource):
    pass
class TestPlanResource                (resource.Resource):
    pass
class TestResultResource                (resource.Resource):
    pass
class TestScriptResource             (resource.Resource):
    pass

class QMEnumCodec( resource.Codec ):
    def encode( self, pythonvalue ):
        # decode an enumeration name to the corresponding URL
        # scan the enum urls in this property
        enumvalue_u = None
        for enum_u in self.properties[self.prop_u]['enums']:
            if self.enums[enum_u]['name']==pythonvalue:
                enumvalue_u = enum_u
        if enumvalue_u is None:
            burp
        thetag=rdfxml.uri_to_tag( self.prop_u )
        result_x = ET.Element( thetag, { self.rdf_resource_tag: enumvalue_u } )
#        print( f"Encode {pythonvalue=} {result_x=} {ET.tostring( result_x )=}" )
        return result_x

    def decode( self, rdfvalue_x ):
        print( f"{rdfvalue_x=} {ET.tostring( rdfvalue_x )}" )
        enumvalue_u = rdfxml.xmlrdf_get_resource_uri(rdfvalue_x)
        print( f"{enumvalue_u=}" )
        enumdef = self.projorcomp.enums[self.projorcomp.sameas.get(enumvalue_u,enumvalue_u)]
        result = enumdef['name']
        # default decoding is string
        print( f"Decode {rdfvalue_x=} {result=}" )
        return result

class QMResourceCodec( resource.Codec ):
    def encode( self, targetid ):
        print( f"QMResourceCodec {targetid=}" )
        # encode id to the target URL
        # use query to look up the artifact
        target_u = self.projorcomp.queryCoreArtifactByID( targetid )
        if target_u is None:
            raise Exception( f"target id '{targetid}' not found" )
        thetag=rdfxml.uri_to_tag( self.prop_u )
        result_x = ET.Element( thetag, { self.rdf_resource_tag: target_u } )
#        print( f"Encode {targetid=} {result_x=} {ET.tostring( result_x )=}" )
        return result_x
        
    def decode( self, linkurl_x ):
        linkurl = rdfxml.xmlrdf_get_resource_uri( linkurl_x )
        print( f"QMResourceCodec Decode {linkurl=}" )
        # decode to the target id
        # GET the reqt
        try:
            art_x = self.projorcomp.execute_get_rdf_xml( linkurl, cacheable=True )
            # find dcterms.identifier
            pythonvalue = rdfxml.xmlrdf_get_resource_text( art_x, './/dcterms:identifier')
        except:
            pythonvalue = linkurl
#        print( f"Decode {linkurl} {pythonvalue=}" )
        return pythonvalue

class QMLinkCodec( resource.Codec ):
    def encode( self, targetid ):
        print( f"QMLinkCodec {targetid=}" )
        # encode id to the target URL
        # use query to look up the artifact
        target_u = self.projorcomp.queryCoreArtifactByID( targetid )
        if target_u is None:
            raise Exception( f"target id '{targetid}' not found" )
        thetag=rdfxml.uri_to_tag( self.prop_u )
        result_x = ET.Element( thetag, { self.rdf_resource_tag: target_u } )
#        print( f"Encode {targetid=} {result_x=} {ET.tostring( result_x )=}" )
        return result_x
        
    def decode( self, linkurl_x ):
        linkurl = rdfxml.xmlrdf_get_resource_uri( linkurl_x )
        print( f"QMLinkCodec Decode {linkurl=}" )
        # decode to the target id
        # GET the reqt
        try:
            art_x = self.projorcomp.execute_get_rdf_xml( linkurl, cacheable=True )
            # find dcterms.identifier
            pythonvalue = rdfxml.xmlrdf_get_resource_text( art_x, './/dcterms:identifier')
        except:
            pythonvalue = linkurl
#        print( f"Decode {linkurl} {pythonvalue=}" )
        return pythonvalue


valuetypetoresource = {
    'http://jazz.net/ns/qm/rqm#BuildDefinition':             BuildDefinitionResource ,
    'http://jazz.net/ns/qm/rqm#BuildRecord':                 BuildRecordResource ,
    'http://jazz.net/ns/qm/rqm#Keyword':                     KeywordResource,
    'http://jazz.net/ns/qm/rqm#TestData':                    TestDataResource ,
    'http://jazz.net/ns/qm/rqm#TestPhase':                   TestPhaseResource ,
    'http://jazz.net/ns/qm/rqm#TestSuite':                   TestSuiteResource ,
    'http://jazz.net/ns/qm/rqm#TestSuiteExecutionRecord':    TestSuiteExecutionRecordResource ,
    'http://jazz.net/ns/qm/rqm#TestSuiteResult':             TestSuiteResultResource ,
    'http://open-services.net/ns/qm#TestCase':               TestCaseResource ,
    'http://open-services.net/ns/qm#TestExecutionRecord':    TestExecutionRecordResource ,
    'http://open-services.net/ns/qm#TestPlan':               TestPlanResource ,
    'http://open-services.net/ns/qm#TestResult':             TestResultResource ,
    'http://open-services.net/ns/qm#TestScript':             TestScriptResource ,
}

valueTypeToCodec = {
        # oslc:valueType
        'http://www.w3.org/2001/XMLSchema#boolean':                 resource.BooleanCodec,
        'http://www.w3.org/2001/XMLSchema#dateTime':                resource.DateTimeCodec,
        'http://www.w3.org/2001/XMLSchema#integer':                 resource.IntegerCodec,
        'http://www.w3.org/2001/XMLSchema#string':                  resource.StringCodec,
        'http://www.w3.org/2001/XMLSchema#float':                   resource.FloatCodec,          
        'http://www.w3.org/1999/02/22-rdf-syntax-ns#XMLLiteral':    resource.XMLLiteralCodec,             
        # oslc:range
        'http://xmlns.com/foaf/0.1/Person':                     resource.UserCodec,
        'http://open-services.net/ns/core#Resource':            QMResourceCodec,
        'http://open-services.net/ns/rm#Requirement':           QMResourceCodec,
        'http://open-services.net/ns/rm#RequirementCollection': QMResourceCodec,
        'http://open-services.net/ns/core#AnyResource':       QMResourceCodec,       
        
        'http://jazz.net/ns/qm/rqm#scriptStepCount':    resource.IntegerCodec,
        'http://www.w3.org/2001/XMLSchema#long':        resource.IntegerCodec,
}

class RMLinkCodec( resource.Codec ):
    def encode( self, targetid ):
#        print( f"{targetid=}" )
        # encode id to the target URL
        # use query to look up the artifact
        target_u = self.projorcomp.queryCoreArtifactByID( targetid )
        if target_u is None:
            raise Exception( f"target id '{targetid}' not found" )
        thetag=rdfxml.uri_to_tag( self.prop_u )
        result_x = ET.Element( thetag, { self.rdf_resource_tag: target_u } )
#        print( f"Encode {targetid=} {result_x=} {ET.tostring( result_x )=}" )
        return result_x
        
    def decode( self, linkurl_x ):
        linkurl = rdfxml.xmlrdf_get_resource_uri( linkurl_x )
#        print( f"Decode {linkurl=}" )
        # decode to the target id
        # GET the reqt
        art_x = self.projorcomp.execute_get_rdf_xml( linkurl, cacheable=True )
        # find dcterms.identifier
        pythonvalue = rdfxml.xmlrdf_get_resource_text( art_x, './/dcterms:identifier')
#        print( f"Decode {linkurl} {pythonvalue=}" )
        return pythonvalue




class QMProject( _project._Project, _qmrestapi.QM_REST_API_Mixin, resource.Resources_Mixin ):
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
        self.unmodifiables = [
            'Access_Context',
            'Access_Control',
            'component',
            'Contributor',
            'Created',
            'creator',
            'Identifier',
            'Modified',
            'Relation',
            'Short_ID',
            'Short_Identifier',
            'Type',
            'projectArea',
            'serviceProvider',
            'type',
        ]

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

    # this is called by resource when a property is found in the rdf which doesn't have a definition in the typesystem.
    # if not implemented here those would be ignored
    def mapUnknownProperty( self, property_name, property_uri, shape_uri ):
#        print( f"mup {property_name=} {property_uri=} {shape_uri=}" ) 
        if property_uri in self.properties:
            raise Exception( f"Should never happen!" )
        if property_uri == "http://open-services.net/ns/rm#uses":
            # add property to shape
            self.shapes[shape_uri]['properties'].append( property_uri )
            # add type to properties
            self.register_property( property_name, property_uri, typeCodec=RMLinkCodec, isMultiValued=True, shape_uri=shape_uri )
            return True
        elif property_uri=="http://jazz.net/ns/rm/navigation#parent":
            # add property to shape
            self.shapes[shape_uri]['properties'].append( property_uri )
            # add type to properties
            self.register_property( property_name, property_uri, typeCodec=FolderCodec, isMultiValued=False, shape_uri=shape_uri )
            return True
        elif property_uri=="http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
            # add property to shape
            self.shapes[shape_uri]['properties'].append( property_uri )
            # add type to properties
            self.register_property( property_name, property_uri, typeCodec=RDFURICodec, isMultiValued=True, shape_uri=shape_uri )
            return True
        return False

    # load the typesystem using the OSLC shape resources
    def _load_types(self,force=False):
        logger.debug( f"load type {self=} {force=}" )
        print( f"load type {self=} {force=}" )
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
                # get the typesystem
                print( f"1 {el=}" )
                self._load_type_from_resource_shape(el)
                print( f"2 {el=}" )
                
                pbar.update(1)

            pbar.close()
        else:
            raise Exception( "services xml not found!" )

        self.typesystem_loaded = True

        print( "\n+++" )
        for i,p_u in enumerate( self.shapes.keys() ):
            print( f"shapes {i} {p_u} {self.shapes[p_u]}" )
        
        print( "\n---" )
        for i,p_u in enumerate( self.properties.keys() ):
            print( f"props {i} {p_u} {self.properties[p_u]}" )

        print( "\n===" )
        for i,p_u in enumerate( self.enums.keys() ):
            print( f"enums {i} {p_u} {self.enums[p_u]}" )

        print( "\n^^^" )
        for i,p_u in enumerate( self.sameas.keys() ):
            print( f"sameas {i} {p_u} {self.sameas[p_u]}" )

        print( "\n\n" )
        return None

    # pick all the attributes from a resource shape definition
    # and for enumerated attributes get all the enumeration values
    def _load_type_from_resource_shape(self, el, supershape=None):
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
#                if '/shape/resource/' not in uri:
#                    name += "_"+str(len(uri))       
                # this is so that the variant type URIs don't overwrite the /shape/resource one
                print( f"{name=} {uri=}" )
                self.register_shape( name, uri )
#                else:
#                    print( f"Ignored 1 non-resource {uri}" )
                logger.info( f"Opening shape {name} {uri}" )
            else:
                # nothing to do!
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

        # give this shape some basic props that aren't in the shape definitions
#        self.register_property( 'oslc:instanceShape', 'oslc:instanceShape', do_not_overwrite=True, typeCodec=resource.InstanceShapeCodec, shape_uri=uri )
#        self.register_property( 'acp:accessControl', 'acp:accessControl', do_not_overwrite=True, typeCodec=resource.AccessControlCodec , shape_uri=uri)
#        self.register_property( 'acp:accessContext', 'acp:accessContext', do_not_overwrite=True, typeCodec=resource.AccessControlCodec , shape_uri=uri)
#        self.register_property( 'process:projectArea', 'process:projectArea', do_not_overwrite=True, typeCodec=resource.ProjectAreaCodec , shape_uri=uri)
#        self.register_property( 'oslc:serviceProvider', 'oslc:serviceProvider', do_not_overwrite=True, typeCodec=resource.ServiceProviderCodec, shape_uri=uri )
        if not self.is_known_property_uri( "http://open-services.net/ns/config#component" ):
            self.register_property( 'Component', 'http://open-services.net/ns/config#component', do_not_overwrite=True, typeCodec=resource.ComponentCodec, shape_uri=uri )
#        self.register_property( 'category', 'http://jazz.net/ns/qm/rqm#category', do_not_overwrite=True, typeCodec=QMEnumCodec, shape_uri=uri )
#        self.register_property( 'script Type', 'http://jazz.net/ns/qm/rqm#scriptType', do_not_overwrite=True, typeCodec=QMEnumCodec, shape_uri=uri )


        # scan the attributes
        logger.info( f"{ET.tostring(thisshapedef_x,pretty_print=True)=}" )
        print( f"{ET.tostring(thisshapedef_x)=}"  )
        for propel in rdfxml.xml_find_elements( thisshapedef_x, './oslc:property' ):
            logger.info( "Starting a property")
            print( f"Starting a property {propel}")
            propnodeid = rdfxml.xmlrdf_get_resource_uri( propel, attrib="rdf:nodeID" )
            logger.info( f"{propnodeid=}" )
            print( f"{propnodeid=}" )
            real_propel_x = rdfxml.xml_find_element( shapedef_x, f'.//rdf:Description[@rdf:nodeID="{propnodeid}"]' )
            logger.info( f"{real_propel_x=}" )
            print( f"{real_propel_x=}" )
#            print( "XML==",ET.tostring(real_propel_x) )
            # dcterms:title xml:lang="en"
            property_title_el = rdfxml.xml_find_element( real_propel_x, './dcterms:title[@xml:lang="en"]')
            logger.info( f"1 {property_title_el=}" )
            print( f"1 {property_title_el=}" )
            if property_title_el is None:
                property_title_el = rdfxml.xml_find_element(real_propel_x, './dcterms:title[@rdf:datatype]' )
                logger.info( f"2 {property_title_el=}" )
                print( f"2 {property_title_el=}" )
            if property_title_el is None:
                property_title_el = rdfxml.xml_find_element( real_propel_x, './oslc:name')
                logger.info( f"3 {property_title_el=}" )
                print( f"3 {property_title_el=}" )
            logger.info( f"{property_title_el=}" )
            print( f"{property_title_el=}" )
            if property_title_el is None:
                logger.info( "Skipping shape with no title!" )
                print( "Skipping shape with no title!" )
                burp
                continue
            property_title = property_title_el.text
            logger.info( f"{property_title=}" )
            print( f"{property_title=}" )
#            if rdfxml.xmlrdf_get_resource_text(real_propel_x,"oslc:hidden") == "true":
#                logger.info( f"Skipping hidden property {property_title}" )
#                print( f"Skipping hidden property {property_title}" )
#                continue
            valueshape_uri = rdfxml.xmlrdf_get_resource_uri( real_propel_x,'oslc:valueShape' )
            logger.info( f"{valueshape_uri=}" )
            print( f"{valueshape_uri=}" )
            
            pd_u = rdfxml.xmlrdf_get_resource_uri( real_propel_x, 'oslc:propertyDefinition' )
            if pd_u is None:
                pd_u = valueshape_uri
            else:
                # if pd is different from vs, create a sameas mapping pd=>vs
                if valueshape_uri and pd_u != valueshape_uri:
                    # this ensures that for aexample an instance tag using the pd hasWorkflowState maps to property using the vs WorkflowState
                    self.sameas[pd_u]=valueshape_uri
                    print( f"Creating sameas for {pd_u} to {valueshape_uri}" )
                    
            print( f"{pd_u=}" )
            
            propcodec = None
            proprange = rdfxml.xmlrdf_get_resource_uri(real_propel_x,'oslc:range' ) 
            proptype = rdfxml.xmlrdf_get_resource_uri( real_propel_x,'oslc:valueType' )
            if proptype is None:
                proptype = proprange
            print( f"valuetype {pd_u} {proprange=} {proptype=}" )
            print( f"{proprange=}" )
#                propcodec = valueTypeToCodec.get( pd_u )
            propcodec = valueTypeToCodec.get( proptype )
            print( f"#1 {pd_u=} {proprange=} {propcodec=}" )

            if valueshape_uri is not None:
                logger.info( f"vs {valueshape_uri}" )
                print( f"vs {valueshape_uri}" )
                # register this property with the valueshape URI
#                propu = f"{uri}#{propnodeid}"
#                if '/shape/resource/' in uri:
#                    print( f"a register_prop {property_title} {valueshape_uri} {uri}" )
#                    self.register_property( property_title, valueshape_uri, shape_uri=uri )
#                else:
#                    logger.info( f"Ignored 2 non-resource {uri}" )
#                    print( f"Ignored 2 non-resource {uri}" 
#                propcodec = propcodec
#                print( f"#2 {pd_u=} {propcodec=}" )
                if not self.is_known_property_uri( pd_u ):
                    self.register_property( property_title, pd_u, shape_uri=uri, typeCodec=propcodec )
                    
                if valueshape_uri.startswith( self.app.baseurl ) and valueshape_uri != uri:
                    # this shape references another shape - need to load this!
                    vs_xml = self._get_typeuri_rdf(valueshape_uri)
                    subshape_x = rdfxml.xml_find_element( vs_xml,f'.//rdf:Description[@rdf:about="{valueshape_uri}"]' )
                    if subshape_x is None:
                        logger.info( f"SubShape definition for {valueshape_uri} not found!" )
                        print( f"SubShape definition for {valueshape_uri} not found!" )
                        print( f"{ET.tostring(vs_xml)=}" )
#                        burp
                        continue
                    # recurse to load this shape!
                    logger.info( f"SUBSHAPE_X={valueshape_uri}" )
                    print( f"SUBSHAPE_X={valueshape_uri}" )
                    self._load_type_from_resource_shape( subshape_x, supershape=( property_title, valueshape_uri ) )
                    print( f"DONE SUBSHAPE_X={valueshape_uri}" )
                else:
                    logger.info( f"SKIPPED external shape {valueshape_uri=}" )
#                logger.debug( f"{valueshape_uri=}" )
#                if not valueshape_uri.startswith( self.app.baseurl):
#                    logger.info( f"Shape definition isn't local to the app {self.app.baseurl=} {uri=}" )
#                    continue

#                propuri = rdfxml.xmlrdf_get_resource_uri( real_propel_x, 'oslc:propertyDefinition')
        #            print( f"{pd_u=}" )
            # prefer range over valueType (doesn't nmatter for rm but does for qm which has both in a property definition)
            # lookup the codec, if there is one
            print( f"{pd_u} {proptype=} {propcodec=}" )

            if self.is_known_property_uri( pd_u ):
                logger.debug( f"ALREADY KNOWN {pd_u}" )
                print( f"ALREADY KNOWN {property_title} {pd_u} {propcodec}" )
                # register it again only so it gets added the shape's list of properties
                self.register_prop_to_shape( pd_u, uri )
                
                continue
                
            # work out if multivalued
            mvtext_x = rdfxml.xmlrdf_get_resource_uri( real_propel_x, "oslc:occurs" )            
            isMultiValued = mvtext_x=="http://open-services.net/ns/core#Zero-or-many"






            # In case of repeated identical property titles on a shape, let's create an alternative name that can (perhaps) be used to disambiguate
            # (at least these don't have duplicates AFAICT)
            altname  = pd_u[pd_u.rfind("/")+1:]
            if '#' in altname:
                altname  = pd_u[pd_u.rfind("#")+1:]

            if pd_u is not None:
                if not pd_u.startswith( self.app.baseurl ):
                    if '/shape/resource/' in uri:
                        print( f"c register_prop {property_title} {pd_u} {uri} {propcodec=}" )
                        if not self.is_known_property_uri( pd_u ):
                            self.register_property( property_title, pd_u, altname=altname, shape_uri=uri, typeCodec=propcodec )
                    else:
                        logger.info( f"Ignored 3 non-resource {uri}" )
                        print( f"Ignored 3 non-resource {uri}" )
                else:
                    if not self.is_known_property_uri( pd_u ):
                        self.register_property( property_title, pd_u, altname=altname, shape_uri=uri, typeCodec=propcodec )
                        
                    logger.debug( f"+++++++NOT Skipping non-local Property Definition {pd_u}" )
#                        continue
            else:
                logger.debug( f"~~~~~~~Ignoring non-local Property Definition {pd_u}" )

#                if self.is_known_property_uri( pd_u, raiseifnotfound=False ):
#                    logger.debug( f"ALREADY KNOWN2 {pd_u}" )
#                    print( f"ALREADY KNOWN2 {pd_u}" )
#                    continue
            logger.info( f"Defining property {title}.{property_title} {altname=} {pd_u=} +++++++++++++++++++++++++++++++++++++++" )
            if '/shape/resource/' in uri:
                print( f"b register_prop {property_title} {pd_u} {uri} {propcodec=}" )
                if not self.is_known_property_uri( pd_u ):
                    self.register_property( property_title, pd_u, altname=altname, shape_uri=uri, typeCodec=propcodec )
            else:
                logger.info( f"Ignored 4 non-resource {uri}" )
                print( f"c ignored 4 non-/shape/resource property {property_title} {pd_u} {uri} {propcodec=}" )
            # check for any allowed value
            allowedvalueu = rdfxml.xmlrdf_get_resource_uri(real_propel_x, "oslc:allowedValue" )
            logger.info( f"{uri=} {allowedvalueu=}" )
            print( f"{uri=} {allowedvalueu=}" )
            if allowedvalueu is not None:
                logger.info( "FOUND ENUM" )
                print( f"FOUND ENUM {allowedvalueu=}" )
                propcodec = QMEnumCodec
                # this has enumerations - find them and record them
                # retrieve each definition
                nvals = 0
                for allowedvaluex in rdfxml.xml_find_elements( real_propel_x, 'oslc:allowedValue' ):
                    allowedvalueu = rdfxml.xmlrdf_get_resource_uri( allowedvaluex )
                    # retrieve it and register the enumeration name and uri in typesystem
                    # a URL
                    thisenumx = rdfxml.xml_find_element( shapedef_x,f'.//rdf:Description[@rdf:about="{allowedvalueu}"]' )
                    print( f"{allowedvalueu=} {thisenumx=}" )
                    if thisenumx is not None:
                        enum_value_name = rdfxml.xmlrdf_get_resource_text( thisenumx, 'rdfs:label') or rdfxml.xmlrdf_get_resource_text( thisenumx, 'dcterms:title')
                        enum_id = enum_value_name
                        print( f"{allowedvalueu=} {enum_value_name=}" )
                    if allowedvalueu.startswith( 'http:' ) or allowedvalueu.startswith( 'https:' ):
                        if thisenumx is not None:
                            enum_uri = allowedvalueu
                            logger.info( f"{enum_uri=}" )
                            print( f"{enum_uri=}" )
                            nvals += 1
                            if not self.is_known_enum_uri( enum_uri ):
                                if enum_value_name is None:
                                    logger.debug( "enum xml=",ET.tostring(thisenumx) )
                                    print( f"{enum_id=} no name" )
                                    raise Exception( "Enum name not present!" )
                                logger.info( f"defining1 enum value {enum_value_name=} {enum_id=} {enum_uri=}" )
                                print( f"defining1 enum value {enum_value_name=} {enum_id=} {enum_uri=} {pd_u=}" )
                                self.register_enum( enum_value_name, enum_uri, property_uri=pd_u, id=None )
                        else:
                            enum_value_name = allowedvalueu.rsplit( '#', 1 )[1] if '#' in allowedvalueu else allowedvalueu.rsplit( '/', 1 )[1]
                            enum_id = enum_value_name
                            enum_uri = allowedvalueu
                            print( f"Asserting {enum_value_name=} {enum_uri=} {enum_uri=}" )
                            logger.info( f"defining enum value {enum_value_name=} {enum_id=} {enum_uri=}" )
                            print( f"defining enum value {enum_value_name=} {enum_id=} {enum_uri=} {pd_u=}" )
                            nvals += 1
                            self.register_enum( enum_value_name, enum_uri, property_uri=pd_u, id=None )
                    else:
                        # an enum name (not sure why QM does this)
                        logger.info( f"ENUM NAME {allowedvalueu}" )
                        print( f"ENUM NAME {allowedvalueu}" )
                        nvals += 1
                        print( f"1 defining enum value {allowedvalueu=} {pd_u=}" )
                        if not self.is_known_property_uri( pd_u ):
                            self.register_property( property_title, pd_u, shape_uri=uri )
                            
                        self.register_enum( allowedvalueu, allowedvalueu, property_uri=pd_u, id=None )
                        
                        pass
                if nvals==0:
                    raise Exception( f"Enumeration {valueshape_uri} with no values loaded" )
            else:
                print( f"Default register_property {property_title=} {pd_u=} {uri=} {propcodec=}" )
                if not self.is_known_property_uri( pd_u ):
                    self.register_property( property_title, pd_u, shape_uri=uri )
                
            print( f"rpc {property_title=} {pd_u=} {propcodec=}" )
            self.register_property_codec( property_title, pd_u, propcodec )

        # look for sameas
        print( f"REGISTERING SameAs" )
        # register enumdefs
        for enumdef in rdfxml.xml_find_elements( shapedef_x, './/rdf:Description/owl:sameAs/..' ):
            print( f"{enumdef=}" )
            value_uri = rdfxml.xmlrdf_get_resource_uri( enumdef, attrib="rdf:about" )
            sameas_uri = rdfxml.xmlrdf_get_resource_uri( enumdef, xpath='./owl:sameAs', attrib="rdf:resource" )
            print( f"{value_uri=} {sameas_uri=}" )
            self.sameas[value_uri] = sameas_uri
            
            # now create enums
            rdftype_u = rdfxml.xmlrdf_get_resource_uri( enumdef, xpath='./rdf:type', attrib="rdf:resource" )
            enumtitle = rdfxml.xmlrdf_get_resource_text( enumdef, xpath='./dcterms:title' )
            print( f"{rdftype_u=} {enumtitle=}" )
            if rdftype_u is not None:
                if not self.is_known_property_uri( rdftype_u ):
                    # make a property name from the type uri
                    propname = rdftype_u.rsplit( "#",1 )[1] if '#' in rdftype_u else rdftype_u.rsplit( "/",1 )[1]
                    self.register_property( propname, rdftype_u, shape_uri=uri, typeCodec=QMEnumCodec )
                # register this as an enum value for property of rdftype_u
                self.register_enum( enumtitle, sameas_uri, rdftype_u )
                print( f"rdf1 {enumtitle=} {sameas_uri=} {rdftype_u=}" )
            else:
                # register this as a floating enum vlaue (not associated to any property)
                self.register_enum( enumtitle, sameas_uri )
                print( f"rdf2 {enumtitle=} {sameas_uri=}" )
            
            print( f"SAMEAS {value_uri=} {sameas_uri=}" )
        print( f"FINISHED REGISTERING SameAs" )

        logger.debug( "Finished loading typesystem")
        return n
     
        
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

    def resourcetypediscriminator( self, resource_x ):
        # find all instances of rdf:type (there can be more than one! it's valid RDF)
        # check for known types in a specific order so the correct type is identified!
        # once a concrete type is identified, return a resource of that type
#        print( f"rtd {ET.tostring(resource_x)}" )
#        result = UnknownResource()
        rdftypes = rdfxml.xmlrdf_get_resource_uris( resource_x, './/rdf:type' )
        if len( rdftypes ) > 1:
            burp
        result = valuetypetoresource[rdftypes[0]]()
        return result
    
    def queryResourcesByIDs( self, identifiers, *, querytype=None, filterFunction=None, modifiedBefore=None, modifiedAfter=None, createdAfter=None ):
        # identifiers is a single id or a list of ids
        if type(identifiers) != list:
            # make identifiers a list
            identifiers = [ identifiers ]
        querytype = querytype or self.default_query_resource
#        print( f"{identifiers=}" )
        # check all the identifiers are integer strings
        identifiers = [str(i) for i in identifiers]
#        print( f"{identifiers=}" )
        for i in identifiers:
            print( f"{i=}" )
            if not utils.isint( str(i) ):
                raise Exception( "value '{i}' is not an integer!" )
                        
        # use OSLC Query then if necessary post-processes the results
        # return Resources!
        # query
            # get the query capability base URL for requirements
        qcbase = self.get_query_capability_uri(querytype)
        
        # query for the identifiers
        artifacts = self.execute_oslc_query(
            qcbase,
            whereterms=[['oslc:shortId','in',identifiers]],
#            select=['*'],
            select=[],
            prefixes={rdfxml.RDF_DEFAULT_PREFIX["oslc"]:'oslc'} # note this is reversed - url to prefix
            )
        results = []
#        print( f"{artifacts=}" )
        for art in artifacts:
            artres = self.resourceFactory( art, self )
            results.append( artres )
            
        return results


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
    identifier_uri = 'oslc:shortId'

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
