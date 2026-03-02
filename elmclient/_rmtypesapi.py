##
## © Copyright 2025- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


#
# DOORS Next Types API https://jazz.net/wiki/bin/view/Main/DNGTypeAPI
#

import urllib

import lxml.etree as ET
from elmclient import utils
from elmclient import rdfxml

@utils.mixinomatic
class RMTypes_Mixin:
    def __init__(self,*args,**kwargs):
        super().__init__()
        self.basetypes = {
            'boolean':  'http://www.w3.org/2001/XMLSchema#boolean',
            'date':     'http://www.w3.org/2001/XMLSchema#date',
            'dateTime': 'http://www.w3.org/2001/XMLSchema#dateTime',
            'float':    'http://www.w3.org/2001/XMLSchema#float',
            'integer':  'http://www.w3.org/2001/XMLSchema#int',
            'string':   'http://www.w3.org/2001/XMLSchema#string',
            'time':     'http://www.w3.org/2001/XMLSchema#time',
            'user':     'http://jazz.net/ns/dng/types#User',
        }

    def providesTypeAPI( self ):
        # test the server to see if it has the types api
        # by finding the query capability; if it's present then the Types API is provided
        qcbase = self.get_query_capability_uri("dng_types:ArtifactType")
        if qcbase:
            return True
        return False

    def hasAttributeType( self, definitionname ):
        # query for the attribute type
        qcbase = self.get_query_capability_uri("dng_types:AttributeType")
        # query for a title and for format=module
        artifacts = self.execute_oslc_query(
            qcbase
            )

        print( f"{artifacts=}" )
        for at in artifacts.keys():
            print( f"Checking {at=}" )
            # check it's on this server!
            if at.startswith( self.reluri() ):
                # GET the type
                at_x = self.execute_get_xml( at ) # self will apply the needed headers :-)
                # check its rdfs:label
                label = rdfxml.xmlrdf_get_resource_text( at_x, ".//rdfs:label" )
                print( f"{label=}" )
                if label and label==definitionname:
                    return True

        return False

    def createSimpleAttributeType( self, definitionname, basetype, comment=None, uri=None ):
        comment = comment or ""
        print( f"{self.services_uri=}" )
        if self.hasAttributeType( definitionname ):
            raise Exception( f"Type {definitionname} already exists!" )
        # create the XML
        basetypeuri=self.basetypes.get(basetype)
        if not basetypeuri:
            raise Exception( f"Base type {basetype} for {definitionname} isn't valid!" )
        uritag = f"<owl:sameAs rdf:resource='{uri}' />" if uri else ""

        encodedconfig = urllib.parse.urlencode({'vvc.configuration':self.local_config})
        print( f"{encodedconfig=}" )

        xml = f"""<rdf:RDF
    xmlns:dng_types="http://jazz.net/ns/rm/dng/types#"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:jfs="http://jazz.net/xmlns/foundation/1.0/"
    xmlns:rrm="http://www.ibm.com/xmlns/rrm/1.0/"
    xmlns:acp="http://jazz.net/ns/acp#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:rrmNav="http://com.ibm.rdm/navigation#"
    xmlns:pref="http://jazz.net/xmlns/alm/rm/Preference/"
    xmlns:acc="http://open-services.net/ns/core/acc#"
    xmlns:rmTypes="http://www.ibm.com/xmlns/rdm/types/"
    xmlns:rmWorkflow="http://www.ibm.com/xmlns/rdm/workflow/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:h="http://www.w3.org/TR/REC-html40"
    xmlns:rmReqIF="http://www.ibm.com/xmlns/rdm/reqif/"
    xmlns:xs="http://schema.w3.org/xs/"
    xmlns:oslc="http://open-services.net/ns/core#"
    xmlns:oslc_config="http://open-services.net/ns/config#"
    xmlns:rrmMulti="http://com.ibm.rdm/multi-request#"
    xmlns:owl='http://www.w3.org/2002/07/owl#'
    xmlns:rm="http://www.ibm.com/xmlns/rdm/rdf/">
    <dng_types:AttributeType rdf:about="{self.reluri('types/something')}">
    <rdfs:label>{definitionname}</rdfs:label>
    <dng_types:valueType>http://www.w3.org/2001/XMLSchema#string</dng_types:valueType>
        {uritag}
  </dng_types:AttributeType>
</rdf:RDF>

"""

        # POST it
        print( f"{xml=}" )
        factory_u = self.get_factory_uri(resource_type='AttributeType')
        print( f"{factory_u=}" )
        # get the result
#        result = self.execute_post_rdf_xml( factory_u, data=xml, remove_parameters=['vvc.configuration'], remove_headers=['OSLC-Core-Version'] )
#        result = self.execute_post_rdf_xml( factory_u, data=xml, remove_parameters=['vvc.configuration'] )
        try:
            result = self.execute_post_rdf_xml( factory_u, data=xml )
        except ET.XMLSyntaxError:
            return
        print( f"{result=}" )

        burp

    # each entry in enums is a tuple of (value,name,uri)
    # value is an integer must be present and never repeated
    # name is a unique string not zero length/None
    # uri can be None or a uri
    def createEnumAttributeType( self, definitionname, basetype, comment=None, uri=None, enums=None ):
        if not enums:
            raise Exception( "No enums provided!" )
        # create the XML
        basetypeuri=self.basetypes.get(basetype)
        if not basetypeuri:
            raise Exception( f"Base type {basetype} for {definitionname} isn't valid!" )
        uritag = f"<dng_types:valueType>{uri}</dng_types:valueType>" if uri else ""
        
        encodedconfig = urllib.parse.urlencode({'vvc.configuration':self.local_config})
        print( f"{encodedconfig=}" )
        
        enumtags=""
        for enumvalue,enumlabel,enumuri in enums:
            enumuritag="<owl:sameAs>{}</owl:sameAs>\n" if enumuri else ""
            enumtags += f"""<dng_types:EnumEntry>
<dcterms:title>{label}</dcterms:title>
<rdf:value>{value}</rdf:value>
{enumuritag}</dng_types:EnumEntry>            
"""
        xml = f"""<rdf:RDF
    xmlns:dng_types="http://jazz.net/ns/rm/dng/types#"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:jfs="http://jazz.net/xmlns/foundation/1.0/"
    xmlns:rrm="http://www.ibm.com/xmlns/rrm/1.0/"
    xmlns:acp="http://jazz.net/ns/acp#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:rrmNav="http://com.ibm.rdm/navigation#"
    xmlns:pref="http://jazz.net/xmlns/alm/rm/Preference/"
    xmlns:acc="http://open-services.net/ns/core/acc#"
    xmlns:rmTypes="http://www.ibm.com/xmlns/rdm/types/"
    xmlns:rmWorkflow="http://www.ibm.com/xmlns/rdm/workflow/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:h="http://www.w3.org/TR/REC-html40"
    xmlns:rmReqIF="http://www.ibm.com/xmlns/rdm/reqif/"
    xmlns:xs="http://schema.w3.org/xs/"
    xmlns:oslc="http://open-services.net/ns/core#"
    xmlns:oslc_config="http://open-services.net/ns/config#"
    xmlns:rrmMulti="http://com.ibm.rdm/multi-request#"
    xmlns:rm="http://www.ibm.com/xmlns/rdm/rdf/"
        >
    <dng_types:AttributeType rdf:about="{self.reluri()}types/something">
        <oslc:serviceProvider>{self.services_uri}</oslc:serviceProvider>
        <oslc_config:component>{self.project_uri}</oslc_config:component>
        <rdfs:label>{definitionname}</rdfs:label>
        <dng_types:valueType>{basetypeuri}</dng_types:valueType>
        {uritag}
        <dng_types:enumEntries>
            <rdf:Seq>
            {enumtags}
            </rdf:Seq>
        </dng_types:enumEntries>
        
  </dng_types:AttributeType>
        
</rdf:RDF>
"""
