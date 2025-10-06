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
        self.enumdefs = {}
        self.sameas = {} # maps a value to it's owl:sameAs

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
        elif uri.startswith( '{' ):
            uri = rdfxml.tag_to_prefix( uri )
            result = rdfxml.tag_to_uri( uri )
            logger.info( f"tag_to_uri1 {uri=} {result=}" )
        elif ':' in uri:
            result = rdfxml.tag_to_uri( uri )
            logger.info( f"tag_to_uri2 {uri=} {result=}" )
        else:
            if exception_if_name:
                raise Exception( f"Expecting a uri but this doesn't look like a URI {uri}" )
            print( f"Warning: Expecting a uri but this doesn't look like a URI {uri} - assuming it's a name" )
#            burp
            result = uri
        return result
        
#    def register_enumsameas( self, enumname, enumuri, enumtitle, enumid, enumsameas ):
#        if enumuri in self.enumders:
#            return
#        
#        self.enumdefs[enumuri] = { 'name':enumname, 'title':enumtitle, 'id':enumid, 'sameas': enumsameas }
#        return
        
    def is_known_shape_uri(self,shape_uri ):
        logger.info( f"is_known_shape_uri {shape_uri=}" )
        shape_uri = self.tosameas( self.normalise_uri( shape_uri ) )
        result = self.shapes.get( self.sameas.get( shape_uri, shape_uri ) )
        logger.info( f"is_known_shape_uri {shape_uri=} returning {result=}" )
        return result

    def is_known_linktype_uri( self, uri ):
        logger.info( f"is_known_linktype_uri {uri=}" )
        uri = self.tosameas( self.normalise_uri( uri ) )
        result = self.linktypes.get(uri)
        logger.info( f"is_known_linktype_uri {uri=} returning {result=}" )
        return result

    def register_shape( self, shape_name, shape_uri, *, rdfuri=None, shape_formats=None ):
        logger.info( f"register_shape {shape_name=} {shape_uri=}" )
#        print( f"register_shape {shape_name=} {shape_uri=}" )
        shape_uri = self.tosameas( self.normalise_uri( shape_uri) )
        if shape_uri in self.shapes:
            raise Exception( f"Shape {shape_uri} already defined!" )
        # add the URI as the main registration for the shape
        self.shapes[shape_uri] = {'name':shape_name,'shape':shape_uri, 'sameas': rdfuri, 'shape_formats': shape_formats, 'properties':[], 'linktypes':[]}
#        print( f"\nSSSS\n{self.shapes}\n\n" )

    def get_shape_uri( self, shape_name ):
        logger.info( f"get_shape_uri {shape_name=}" )
        shapes = [k for k,v in self.shapes.items()  if v['name']==shape_name ]
        if len(shapes)==1:
            result = shapes[0]
        else:
            print( f"Warning more than one shape has name '{shape_name}'" )
            result = None
        return result

    def get_shape_name( self, shape_uri ):
        shape_uri = self.tosameas( self.normalise_uri( shape_uri) )
        result = self.shapes.get(shape_uri)
        return result

#    def is_known_property_uri( self, property_uri, *, shape_uri=None, raiseifnotfound=True ):
    def is_known_property_uri( self, property_uri, *, raiseifnotfound=True ):
        logger.info( f"is_known_property_uri {property_uri=}" )
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        uri1 = self.sameas.get( property_uri, property_uri )
#        print( f"*** {property_uri=} {uri1=} {property_uri==uri1}" )
#        print( f"{uri1=} {self.properties.get(uri1)=}" )
#        print( f"{self.properties=}" )
        result = self.properties.get( self.sameas.get( property_uri, property_uri ) ) is not None
#        print( f"{self.properties.get( uri1 )=}" )
#        shape_uri = self.normalise_uri( shape_uri )
#        if shape_uri is None and property_uri in self.properties:
#            if self.properties[property_uri]['shape']==shape_uri:
#                result = True
#            else:
#                if raiseifnotfound:
#                    raise Exception( f"Property {property_uri} not registered with shape {shape_uri}" )
#                result = False
#        else:
#            result = False
        logger.info( f"is_known_property_uri {property_uri=} returning {result=}" )
#        print( f"is_known_property_uri {self=} {property_uri=} returning {result=}" )
        return result

    def tosameas( self, uri ):
        return self.sameas.get( uri, uri )

    def register_prop_to_shape( self, property_uri, shape_uri ):
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        shape_uri = self.tosameas( self.normalise_uri( shape_uri ) )
        if shape_uri not in self.shapes:
            burp
        if property_uri not in self.properties:
            burp
        if property_uri not in self.shapes[shape_uri]['properties']:
            self.shapes[shape_uri]['properties'].append( property_uri )
                
#    def register_property( self, property_name, property_uri, *, property_value_type=None, shape_uri=None, altname = None, do_not_overwrite=True, property_definition_uri=None, isMultiValued=False, typeCodec=None ):
    def register_property( self, property_name, property_uri, *, shape_uri=None, property_value_type=None, altname = None, do_not_overwrite=True, property_definition_uri=None, isMultiValued=False, typeCodec=None ):
        logger.info( f"register_property {self=} {property_name=} {property_uri=} {shape_uri=} {isMultiValued=} {typeCodec=}" )
#        print( f"register_property {self=} {property_name=} {property_uri=} {shape_uri=} {isMultiValued=} {typeCodec=}" )
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        shape_uri = self.tosameas( self.normalise_uri( shape_uri ) )
        if property_uri in self.properties:
#            print( f"Property {property_uri} already defined {self.properties[property_uri]=}" )
            burp
            pass
        if property_uri is None:
            burp
        if property_uri in self.properties and typeCodec and type(typeCodec) != type(self.properties[property_uri]['typeCodec']):
#            print( f"{self.properties[property_uri]=}" )
            raise Exception( f"Codec for {property_name} {property_uri} already set to {self.properties[property_uri]['typeCodec']} so can't set again to {codec}!" )

        if not do_not_overwrite or property_uri not in self.properties:
#            self.properties[property_uri] = {'name': property_name, 'shape': shape_uri, 'enums': [], 'value_type': property_value_type, 'altname':altname, 'isMultiValued':isMultiValued, 'typeCodec': typeCodec }
            self.properties[property_uri] = {'name': property_name, 'enums': [], 'value_type': property_value_type, 'altname':altname, 'isMultiValued':isMultiValued, 'typeCodec': typeCodec }
#        else:
#            burp
        if altname and property_definition_uri and ( not do_not_overwrite or property_definition_uri not in self.properties):
            self.properties[property_definition_uri] = {'name': altname, 'enums': [], 'value_type': property_value_type, 'altname':None, 'isMultiValued':isMultiValued, 'typeCodec': typeCodec }
            self.properties[rdfxml.uri_to_default_prefixed_tag(property_definition_uri)] = {'name': altname, 'enums': [], 'value_type': property_value_type, 'altname':None, 'isMultiValued':isMultiValued, 'typeCode': typeCodec }
        if shape_uri is not None and property_uri not in self.shapes[shape_uri]['properties']:
            self.shapes[shape_uri]['properties'].append(property_uri)
            
#        print( f"\nPPPP\n{self.properties}\nSSSSS\n{self.shapes[shape_uri]}\n\n" )

#    def register_property_codec( self, property_name, property_uri, codec, shape_uri=None ):
    def register_property_codec( self, property_name, property_uri, codec ):
#        print( f"rpc {property_name=} {property_uri=} {codec=}" )
        if property_uri not in self.properties:
#            print( f"{self.properties=}" )
            raise Exception()
        if self.properties[property_uri].get('typeCodec'):
            if type(codec) != type(self.properties[property_uri]['typeCodec']):
                raise Exception( f"Codec for {property_name} {property_uri} already set to {self.properties[property_uri]['typeCodec']} so can't set again to {codec}!" )
        else:
            self.properties[property_uri]['typeCodec'] = codec
    
#    def register_linktype( self, linktype_name, linktype_uri, label, *, inverselabel=None, rdfuri=None, shape_uri=None, isMultiValued=False, typeCodec=None ):
    def register_linktype( self, linktype_name, linktype_uri, label, *, inverselabel=None, rdfuri=None, isMultiValued=False, typeCodec=None ):
        logger.info( f"register_linktype {linktype_name=} {linktype_uri=} {label=} {inverselabel=} {rdfuri=} {typeCodec=}" )
        linktype_uri = self.tosameas( self.normalise_uri( linktype_uri ) )
#        shape_uri = self.normalise_uri( shape_uri )
        if linktype_uri not in self.linktypes:
#            self.linktypes[linktype_uri] = {'name': label, 'inverselabel': inverselabel, 'shape': shape_uri, 'rdfuri': rdfuri }
            self.linktypes[linktype_uri] = {'name': linktype_name, 'label': label, 'inverselabel': inverselabel, 'rdfuri': rdfuri, 'typeCodec': typeCodec }
#        if shape_uri is not None:
#            self.shapes[shape_uri]['linktypes'].append(linktype_uri)
        
    def get_linktype_name( self, uri ):
#        print( f"gln {uri=}" )
        uri = self.tosameas( self.normalise_uri( uri ) )
        if uri in self['linktypes']:
#            print( f"{self['linktypes'][uri]['name']=}" )
            return self['linktypes'][uri]['name']
#        print( f"gln None" )
        return None
        
#    def get_property_uri( self, property_name, *, shape_uri=None ):
    def get_property_uri( self, property_name, shape_uri=None ):
        logger.info( f"get_property_uri {property_name=}" )
#        print( f"get_property_uri {property_name=}" )
#        shape_uri = self.normalise_uri( shape_uri )
#        properties = [k for k,v in self.properties.items() if v['name']==property_name and v['shape']==shape_uri]
        if shape_uri:
            shape_uri = self.tosameas( self.normalise_uri( shape_uri ) )
            properties = [k for k,v in self.properties.items() if v['name']==property_name and k in self.shapes[shape_uri]['properties']]
#            print( f"0{self.shapes[shape_uri]['properties']=}" )
#            print( f"1 {properties=}" )
        else:
            properties = [k for k,v in self.properties.items() if v['name']==property_name]
            
#            print( f"1 {properties=}" )
            
        if len(properties)==1:
            result = properties[0]
        else:
            # try using altname
            altproperties = [k for k,v in self.properties.items() if v['altname']==property_name]
            if len(altproperties)==1:
                result = altproperties[0]
                logger.info( f"Property {property_name} found using altname" )
            else:
                if len(altproperties)>1:
                    altnames = [self.properties[k]['altname'] for k in properties]
                    raise Exception( f"Property {property_name} is ambiguous - maybe use the altname - {altnames}" )
                else:
                    # try for a property ignoring the shape - as long as all the ones with the name have the same URI after normalising to a uri if tag/prefix present
#                    properties = [k for k,v in self.properties.items() if v['name']==property_name]
#                    if len(properties)==1 or (len(properties)>1 and all([rdfxml.tag_to_uri(k)==rdfxml.tag_to_uri(properties[0]) for k in properties[1:]]) ):
#                        result = properties[0]
#                    else:
                        result = None
        logger.info( f"get_property_uri {property_name=} returning {result=}" )
        return result

    def get_property_name( self, property_uri, shape_uri=None ):
        logger.info( f"get_property_name {property_uri=} {shape_uri=}" )
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        result = self.properties.get(property_uri)
        return result
        
    def get_enum_names( self, property_uri ):
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        result = [self.enums[e]['name'] for e in self.properties[property_uri]['enums']]
#        print( f"Enum names {property_uri=} = {result=}" )
        return result
            
        
    def is_known_enum_uri( self, enum_uri ):
        enum_uri = self.tosameas( self.normalise_uri( enum_uri ) )
        result = self.enums.get( self.sameas.get( enum_uri, enum_uri ) )
        logger.info( f"is_known_enum_uri {enum_uri=} returning {result=}" )
        return result

    def register_enum( self, enum_name, enum_uri, property_uri=None, *, id=None ):
        logger.info( f"register_enum {enum_name=} {enum_uri=} {property_uri=} {id=}" )
#        print( f"register_enum {enum_name=} {enum_uri=} {property_uri=} {id=}" )
        # add the enum  to the property
        enum_uri = self.tosameas( self.normalise_uri( enum_uri ) )
        if property_uri is not None:
            property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        self.enums[enum_uri] = {'name': enum_name, 'id':id, 'property': property_uri}
        if id:
            self.enums[id] = {'name': enum_name, 'id':id, 'property': property_uri}
        if property_uri and enum_uri not in self.properties[property_uri]['enums']:
            self.properties[property_uri]['enums'].append(enum_uri)
#        print( f"\nEEEE\n{self.properties[property_uri]['enums']}\n{self.properties[property_uri]}\n\n" )

    def get_enum_uri(self, enum_name, property_uri):
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        result = None
        for enumuri in self.properties[property_uri]['enums']:
            if self.enums[enumuri]['name']==enum_name:
                result = enumuri
                break
        return result

    def get_enum_name( self, enum_uri ):
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        return self.enums[enum_uri]['name']

    def get_enum_id( self, enum_name, property_uri ):
        logger.info( f"get_enum_id {enum_name=} {property_uri=}" )
        print( f"get_enum_id {enum_name=} {property_uri=}" )
        property_uri = self.tosameas( self.normalise_uri( property_uri ) )
        result = None
        logger.info( f"{self.properties[property_uri]=}" )
        print( f"{self.properties[property_uri]=}" )
        logger.info( f"{self.properties[property_uri]['enums']=}" )
        print( f"{self.properties[property_uri]['enums']=}" )
        for enum_uri in self.properties[property_uri]['enums']:
            if self.enums[enum_uri]['name']==enum_name:
                result = self.enums[enum_uri]['id'] or enum_uri
#                result = enum_uri # this makes ccm queries for e.g. rc:cm:type=Defect not work - ccm doens't like getting a URI - # unfortunately I can't remember why I added this line :-(
                break
        logger.info( f"get_enum_id {enum_name=} {property_uri=} {result=}" )
        return result

    # generic uri/name

    def is_known_uri( self, uri ):
        logger.debug( f"iku {uri}" )
        uri = self.tosameas( self.normalise_uri( uri ) )
        result =  ( self.shapes.get(uri) or self.properties.get(uri) or self.enums.get(uri) or self.values.get(uri) or self.linktypes.get(uri) ) is not None
        logger.info( f"is_known_uri {uri=} returning {result=} s={self.shapes.get(uri)} p={self.properties.get(uri)} e={self.enums.get(uri)} v={self.values.get(uri)}" )
        return result

    def register_name( self, name, uri ):
        uri = self.tosameas( self.normalise_uri( uri ) )
        self.values[uri]={'name': name }

    def get_uri_name( self, uri ):
        uri = self.tosameas( self.normalise_uri( uri ) )
        result = self.shapes.get(uri) or self.properties.get(uri) or self.enums.get(uri) or self.values.get(uri) or self.linktypes.get(uri)
        if result is not None:
            result = result['name']
        logger.info( f"get_uri_name {uri=} returning {result=}" )
        print( f"get_uri_name {uri=} returning {result=}" )
        return result

    def get_name_uri( self, name ):
        result = self.get_shape_uri(name) or self.get_property_uri(name) or self.get_enum_uri(name) or self.get_value_uri(name) or self.get_linktype_uri(name)
        return result

#    def get_linktype_uri( self, name, shape_uri=None ):
    def get_linktype_uri( self, name ):
        linktypes = [k for k,v in self.linktypes.items() if v['name']==name]
        if len(linktypes) > 1:
            raise Exception( f"Multiple link types with same name '{name}'" )
        if len(linktypes) == 0:
            return None
            
        return linktypes[0]
        