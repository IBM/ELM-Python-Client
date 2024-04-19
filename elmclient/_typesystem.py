##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import logging

from . import rdfxml
from . import utils

logger = logging.getLogger(__name__)

#################################################################################################

class No_Type_System_Mixin():
    def __init__(self,*args,**kwargs):
        self.has_typesystem=False

class Type_System_Mixin():
    def __init__(self,*args,**kwargs):
        self.typesystem_loaded = False
        self.has_typesystem=True
        self.clear_typesystem()

    def clear_typesystem(self):
        self.shapes = {}
        self.properties = {}
        self.linktypes = {}
        self.enums = {}
        self.values = {}
        self.typesystem_loaded = False
        self._gettypecache = {}

    def textreport(self):

        def quote(s):
            if " " in s:
                return f"'{s}'"
            else:
                return s

        rows = []
        report = ""

        def addtoreport(s, end='\n'):
            nonlocal report
            report += s + end

        reportedproperties = []
        reportedlinktypes = []
        # print a nicely sorted report with shapes at left, then properties (with type, if defined) in that shape, then enumerations in that property
        for shapeuri in sorted(self.shapes.keys(),key=lambda k: self.shapes[k]['name'].lower()):
            rows.append( [f"{quote(self.shapes[shapeuri]['name']):25}"] )
            # properties
            for propertyuri in sorted(self.shapes[shapeuri]['properties'], key=lambda k: self.properties[k]['name'].lower()):
                reportedproperties.append(propertyuri)
                rows.append( [ "",f"{quote(self.properties[propertyuri]['name'])}"] )
                if self.properties[propertyuri]['altname'] is not None:
                    rows[-1].append( f"{self.properties[propertyuri]['altname']}" )
                else:
                    rows[-1].append("")
                rows[-1].append( f"{rdfxml.uri_to_default_prefixed_tag(propertyuri)}" )
                if self.properties[propertyuri].get('value_type'):
                    rows[-1].append( f"{self.properties[propertyuri]['value_type']}" )
                else:
                     rows[-1].append( "" )
                newrowlen = len(rows[-1])-3
                # add enums as additional rows
                for enum_uri in sorted(self.properties[propertyuri]['enums'],key=lambda k:self.enums[k]['name'].lower()):
                    eid = self.enums[enum_uri].get('id') or enum_uri
                    rows.append( [""]*newrowlen+[f"{quote(self.enums[enum_uri]['name'])}",eid,enum_uri ] )
                    logger.info( f"appended for enum {rows[-1]}" )
            # linktypes not reported on the shape as they're common to all shapes
#            # link types
#            for linktypeuri in sorted(self.shapes[shapeuri].get('linktypes',[]), key=lambda k: self.linktypes[k]['name'].lower()):
#                reportedlinktypes.append(linktypeuri)
#                rows.append( [ "",f"{quote(self.linktypes[linktypeuri]['name'])}"] )
#                rows[-1].append( f"{rdfxml.uri_to_default_prefixed_tag(linktypeuri)}" )
#                if self.linktypes[linktypeuri]['rdfuri'] is not None:
#                    rows[-1].append( f"{rdfxml.uri_to_default_prefixed_tag(self.linktypes[linktypeuri]['rdfuri'])}" )
#                else:
#                    rows[-1].append("")
#                rows[-1].append( f"{self.linktypes[linktypeuri]['label']}" )
#                rows[-1].append( f"{self.linktypes[linktypeuri]['inverselabel']}" )
                
                newrowlen = len(rows[-1])-3
            
        if len(rows)>0:
            addtoreport( "<h2>Shapes<h2>\n" )
            report += utils.print_in_html( rows,['Shape','Property Name','Property label','URI'] )

        # now report properties without shape
        rows = []
        for propertyuri in sorted(self.properties, key=lambda k: self.properties[k]['name'].lower()):
            if propertyuri not in reportedproperties:
                rows.append( [ f"{quote(self.properties[propertyuri]['name'])}" ] )
                if self.properties[propertyuri]['altname'] is not None:
                    rows[-1].append( f"{self.properties[propertyuri]['altname']}" )
                else:
                    rows[-1].append("")
                rows[-1].append( f"{rdfxml.uri_to_default_prefixed_tag(propertyuri)}" )
#                    addtoreport( f"{INDENT}{propertyuri}", end="" )
                if self.properties[propertyuri].get('value_type'):
                    rows[-1].append( f"{self.properties[propertyuri]['value_type']}" )
                else:
                    rows[-1].append( "" )
                newrowlen = len(rows[-1])-3
                # add enums as additional rows
                for enum_uri in sorted(self.properties[propertyuri]['enums'],key=lambda k:self.enums[k]['name'].lower()):
                    eid = self.enums[enum_uri].get('id') or enum_uri
                    rows.append( [""]*newrowlen+[f"{quote(self.enums[enum_uri]['name'])}",eid,enum_uri ] )
                    logger.info( f"appended for enum {rows[-1]}" )
        if len(rows)>0:
            addtoreport( "<h2>Properties with no shape</h2>\n" )
            report += utils.print_in_html( rows,['Shape','Property Name','Property label','URI'] )
            
        # now report link types
        rows = []
        for linktypeuri in sorted(self.linktypes, key=lambda k: self.linktypes[k]['name'].lower()):
            rows.append( [ f"{quote(self.linktypes[linktypeuri]['name'])}"] )
            rows[-1].append( f"{rdfxml.uri_to_default_prefixed_tag(linktypeuri)}" )
            if self.linktypes[linktypeuri]['rdfuri'] is not None:
                rows[-1].append( f"{rdfxml.uri_to_default_prefixed_tag(self.linktypes[linktypeuri]['rdfuri'])}" )
            else:
                rows[-1].append("")
            rows[-1].append( f"{self.linktypes[linktypeuri]['label']}" )
            rows[-1].append( f"{self.linktypes[linktypeuri]['inverselabel']}" )
                
        if len(rows)>0:
            addtoreport( "<h2>Link Types</h2>\n" )
            report += utils.print_in_html( rows,['Name', 'URI', 'RDF URI','Label','Inverse Label'] )
            

        return report


    # normalise results to either a URI or if a tag expand it, or the name
    def normalise_uri( self, uri, exception_if_name=False ):
        if uri is None:
            result = None
        elif uri.startswith( 'http://') or uri.startswith( 'https://'):
            result = uri
        elif ':' in uri:
            result = rdfxml.tag_to_uri( uri )
            logger.info( f"tag_to_uri {uri=} {result=}" )
        else:
            if exception_if_name:
                raise Exception( f"Expecting a uri but this doesn't look like a URI {uri}" )
            print( f"Warning: Expecting a uri but this doesn't look like a URI {uri} - assuming it's a name" )
            result = uri
        return result

    def is_known_shape_uri(self,shape_uri ):
        logger.info( f"is_known_shape_uri {shape_uri=}" )
        shape_uri = self.normalise_uri( shape_uri )
        result = self.shapes.get(shape_uri) is not None
        logger.info( f"is_known_shape_uri {shape_uri=} returning {result=}" )
        return result

    def register_shape( self, shape_name, shape_uri ):
        logger.info( f"register_shape {shape_name=} {shape_uri=}" )
        shape_uri = self.normalise_uri( shape_uri)
        if shape_uri in self.shapes:
            raise Exception( f"Shape {shape_uri} already defined!" )
        # add the URI as the main registration for the shape
        self.shapes[shape_uri] = {'name':shape_name,'shape':shape_uri,'properties':[], 'linktypes':[]}
        self.loaded = True

    def get_shape_uri( self, shape_name ):
        logger.info( f"get_shape_uri {shape_name=}" )
        shapes = [k for k,v in self.shapes.items()  if v['name']==shape_name ]
        if len(shapes)==1:
            result = shapes[0]
        else:
            result = None
        return result

    def get_shape_name( self, shape_uri ):
        shape_uri = self.normalise_uri( shape_uri)
        result = self.shapes.get(shape_uri)
        return result

    def is_known_property_uri( self, property_uri, *, shape_uri=None, raiseifnotfound=True ):
        logger.info( f"is_known_property_uri {property_uri=} {shape_uri=}" )
        property_uri = self.normalise_uri( property_uri )
        shape_uri = self.normalise_uri( shape_uri )
        if property_uri in self.properties:
            if self.properties[property_uri]['shape']==shape_uri:
                result = True
            else:
                if raiseifnotfound:
                    raise Exception( f"Property {property_uri} not registered with shape {shape_uri}" )
                result = False
        else:
            result = False
        logger.info( f"is_known_property_uri {property_uri=} {shape_uri=} returning {result=}" )
        return result

    def register_property( self, property_name, property_uri, *, property_value_type=None, shape_uri=None, altname = None, do_not_overwrite=True, property_definition_uri=None ):
        logger.info( f"register_property {property_name=} {property_uri=} {shape_uri=}" )
        property_uri = self.normalise_uri( property_uri )
        shape_uri = self.normalise_uri( shape_uri )
        if not do_not_overwrite or property_uri not in self.properties:
            self.properties[property_uri] = {'name': property_name, 'shape': shape_uri, 'enums': [], 'value_type': property_value_type, 'altname':altname}
        if altname and property_definition_uri and ( not do_not_overwrite or property_definition_uri not in self.properties):
            self.properties[property_definition_uri] = {'name': altname, 'shape': shape_uri, 'enums': [], 'value_type': property_value_type, 'altname':None}
            self.properties[rdfxml.uri_to_default_prefixed_tag(property_definition_uri)] = {'name': altname, 'shape': shape_uri, 'enums': [], 'value_type': property_value_type, 'altname':None}
        if shape_uri is not None:
            self.shapes[shape_uri]['properties'].append(property_uri)
        self.loaded = True

    def register_linktype( self, linktype_name, linktype_uri, label, *, inverselabel=None, rdfuri=None, shape_uri=None ):
        logger.info( f"register_linktype {linktype_name=} {linktype_uri=} {label=} {inverselabel=} {rdfuri=}" )
        linktype_uri = self.normalise_uri( linktype_uri )
        shape_uri = self.normalise_uri( shape_uri )
        if linktype_uri not in self.linktypes:
#            self.linktypes[linktype_uri] = {'name': label, 'inverselabel': inverselabel, 'shape': shape_uri, 'rdfuri': rdfuri }
            self.linktypes[linktype_uri] = {'name': linktype_name, 'label': label, 'inverselabel': inverselabel, 'rdfuri': rdfuri }
        if shape_uri is not None:
            self.shapes[shape_uri]['linktypes'].append(linktype_uri)
        self.loaded = True

    def get_property_uri( self, property_name, *, shape_uri=None ):
        logger.info( f"get_property_uri {property_name=} {shape_uri=}" )
        shape_uri = self.normalise_uri( shape_uri )
        properties = [k for k,v in self.properties.items() if v['name']==property_name and v['shape']==shape_uri]
        if len(properties)==1:
            result = properties[0]
        else:
            # try using altname
            altproperties = [k for k,v in self.properties.items() if v['altname']==property_name and v['shape']==shape_uri]
            if len(altproperties)==1:
                result = altproperties[0]
                logger.info( f"Property {property_name} found using altname" )
            else:
                if len(altproperties)>1:
                    altnames = [self.properties[k]['altname'] for k in properties]
                    raise Exception( f"Property {property_name} is ambiguous - maybe use the altname - {altnames}" )
                else:
                    # try for a property ignoring the shape - as long as all the ones with the name have the same URI after normalising to a uri if tag/prefix present
                    properties = [k for k,v in self.properties.items() if v['name']==property_name]
                    if len(properties)==1 or (len(properties)>1 and all([rdfxml.tag_to_uri(k)==rdfxml.tag_to_uri(properties[0]) for k in properties[1:]]) ):
                        result = properties[0]
                    else:
                        result = None
        logger.info( f"get_property_uri {property_name=} {shape_uri=} returning {result=}" )
        return result

    def get_property_name( self, property_uri, shapeuri=None ):
        logger.info( f"get_property_name {property_uri=} {shape_uri=}" )
        property_uri = self.normalise_uri( property_uri )
        result = self.properties.get(property_uri)
        return result

    def is_known_enum_uri( self, enum_uri ):
        enum_uri = self.normalise_uri( enum_uri )
        result = self.enums.get(enum_uri)
        logger.info( f"is_known_enum_uri {enum_uri=} returning {result=}" )
        return result

    def register_enum( self, enum_name, enum_uri, property_uri, *, id=None ):
        logger.info( f"register_enum {enum_name=} {enum_uri=} {property_uri=} {id=}" )
        # add the enum  to the property
        enum_uri = self.normalise_uri( enum_uri )
        property_uri = self.normalise_uri( property_uri )
        self.enums[enum_uri] = {'name': enum_name, 'id':id, 'property': property_uri}
        if id:
            self.enums[id] = {'name': enum_name, 'id':id, 'property': property_uri}
        
        self.properties[property_uri]['enums'].append(enum_uri)
        self.loaded = True

    def get_enum_uri(self, enum_name, property_uri):
        property_uri = self.normalise_uri( property_uri )
        result = None
        for enumuri in self.properties[property_uri]['enums']:
            if self.enums[enumuri]['name']==enum_name:
                result = enumuri
                break
        return result

    def get_enum_name( self, enum_uri ):
        property_uri = self.normalise_uri( property_uri )
        return self.enums[enum_uri]['name']

    def get_enum_id( self, enum_name, property_uri ):
        logger.info( f"get_enum_id {enum_name=} {property_uri=}" )
        property_uri = self.normalise_uri( property_uri )
        result = None
        logger.info( f"{self.properties[property_uri]=}" )
        logger.info( f"{self.properties[property_uri]['enums']=}" )
        for enum_uri in self.properties[property_uri]['enums']:
            if self.enums[enum_uri]['name']==enum_name:
                result = self.enums[enum_uri]['id'] or enum_uri
                result = enum_uri
                break
        logger.info( f"get_enum_id {enum_name=} {property_uri=} {result=}" )
        return result

    # generic uri/name

    def is_known_uri( self, uri ):
        logger.debug( f"iku {uri}" )
        uri = self.normalise_uri( uri )
        result =  ( self.shapes.get(uri) or self.properties.get(uri) or self.enums.get(uri) or self.values.get(uri) ) is not None
        logger.info( f"is_known_uri {uri=} returning {result=} s={self.shapes.get(uri)} p={self.properties.get(uri)} e={self.enums.get(uri)} v={self.values.get(uri)}" )
        return result

    def register_name( self, name, uri ):
        uri = self.normalise_uri( uri )
        self.values[uri]={'name': name }
        self.loaded = True

    def get_uri_name( self, uri ):
        uri = self.normalise_uri( uri )
        result = self.shapes.get(uri) or self.properties.get(uri) or self.enums.get(uri) or self.values.get(uri)
        if result is not None:
            result = result['name']
        logger.info( f"get_uri_name {uri=} returning {result=}" )
        return result

    def get_name_uri( self, name ):
        result = self.get_shape_uri(name) or self.get_property_uri(name) or self.get_enum_uri(name) or self.get_value_uri(name) or self.get_linktype_uri(name)
        return result

    def get_linktype_uri( self, name ):
        linktypes = [k for k,v in self.linktypes.items() if v['name']==name]
        if len(linktypes) > 1:
            raise Exception( f"Multiple link types with same name '{name}'" )
        if len(linktypes) == 0:
            return None
            
        return linktypes[0]
        