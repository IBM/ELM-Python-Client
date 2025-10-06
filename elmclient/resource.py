##
## © Copyright 2025- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# THIS IS VERYT INCOMPLETE AND EXPERIMENTAL - DO NOT USE!
#
# routines to encapsulate a generic ELM resource as an object with attributes
#
# Creates the object by retrieving the RDF and using the tags to create attributes
#
# Provide PUT to update the resource in ELM
#

import argparse
import collections
import datetime
import keyword
import logging
import os
import pprint
import sys
import urllib

pp = pprint.PrettyPrinter(indent=4)

import lxml.etree as ET

from elmclient import utils
from elmclient import rdfxml
from elmclient import server

# formats for properties
XMLLITERAL = "XMLLITERAL"
RDFRESOURCE = "RDFRESOURCE"
TEXT = "TEXT"

# These encode/decode between an RDF value and the corresponding Python representation
# inherited classes implement just encoder() and decoder()
# so the generic encode and decode cna apply the same logging (or not) to all codecs
class Codec( object ):
    def __init__( self, projorcomp, shape_u, prop_u ):
#        print( "Init Codec {self=}" )
        self.projorcomp = projorcomp
        self.shape_u = shape_u
        self.prop_u = prop_u
        self.rdf_resource_tag = f"{{http://www.w3.org/1999/02/22-rdf-syntax-ns#}}resource"
        self.parse_type_tag = f"{{http://www.w3.org/1999/02/22-rdf-syntax-ns#}}parseType"
        self.datatype_tag = f"{{http://www.w3.org/1999/02/22-rdf-syntax-ns#}}datatype"
        pass
        
    def encode( self, pythonvalue ):
        # default encoding is string
#        print( f"Encode {self=} {type(self)} {pythonvalue=}" )
        thetag=rdfxml.uri_to_tag( self.prop_u )
        result_x = ET.Element( thetag )
#        result_x.text = pythonvalue
#        print( f"Encode {rdfvalue=} {result_x=} {ET.tostring( result_x )=}" )
        return result_x

    def decode( self, rdfvalue_x ):
        # default decoding is string
        result = rdfvalue_x.text
#        print( f"Decode {rdfvalue_x=} {result=} {ET.tostring( rdfvalue_x )}" )
        return result
    
    def checkonassignment( self, value ):
        print( f"Check {type(self)} on assignment value {value} does nothing!" )
        return
        
class XMLLiteralCodec( Codec ):
    def encoder( self, pythonvalue ):
        thetag=rdfxml.uri_to_tag( prop_u )
        newel_x = ET.Element( thetag, { self.parse_type_tag: 'Literal'} )
        return newel_x
    def decoder( self, x ):
        # surely there should be a less hacky way of getting the literal content?
        literal = ET.tostring(x).decode()
        pythonvalue = literal[literal.index('>')+1:literal.rindex('<')]
        return pythonvalue
        
class StringLiteralCodec( Codec ):
    def encode( self, pythonvalue ):
        # default encoding is string
        # RM typesystem doesn't seem to have any indication that a Literal is a plain string or xhtml - AFAIK xhtml is only used for the Primary Text
        # but need a way to handle this
        # bit of a hack: if the string starts with < and ends with > then it's parsed
        # direct into the element, otherwise it's assumed not to be XML and inserted as the text of the element
        thetag=rdfxml.uri_to_tag( self.prop_u )
        newel_x = ET.Element( thetag, { self.parse_type_tag: 'Literal'} )
        if pythonvalue.startswith( "<" ):
            newel_x.append( ET.XML(pythonvalue) )
        else:
            newel_x.text = pythonvalue
#        print( f"StringLiteralCodec Encode {pythonvalue=} {newel_x=} {ET.tostring( newel_x )}" )
        return newel_x

    def decode( self, rdfvalue_x ):
        # default decoding is string
        # surely there should be a less hacky way of getting the literal content?
        literal = ET.tostring(rdfvalue_x).decode()
        pythonvalue = literal[literal.index('>')+1:literal.rindex('<')]
#        print( f"StringLiteralCodec Decode {rdfvalue_x=} {pythonvalue=} {ET.tostring( rdfvalue_x )}" )
        return pythonvalue
    
class RDFResourceCodec( Codec ):
    def encode( self, pythonvalue ):
        print( f"RDFResource encode {pythonvalue=}" )
        thetag=rdfxml.uri_to_tag( self.prop_u )
        newel_x = ET.Element( thetag, { self.rdf_resource_tag: pythonvalue } )
#        print( f"{newel_x=} {ET.tostring( newel_x )}" )
        return newel_x
    def decode( self, rdfvalue_x ):
        print( f"RDFResource decode {rdfvalue_x=}" )
        value_u = rdfxml.xmlrdf_get_resource_uri(rdfvalue_x)
        return value_u
        
    pass
class ResourceCodec( Codec ):
    pass
class ServiceProviderCodec( RDFResourceCodec ):
    pass
class AccessControlCodec( RDFResourceCodec ):
    pass
    
class ComponentCodec( RDFResourceCodec ):
    def encode( self, pythonvalue ):
        thetag=rdfxml.uri_to_tag( self.prop_u )
        newel_x = ET.Element( thetag, { self.rdf_resource_tag: pythonvalue } )
#        print( f"{newel_x=} {ET.tostring( newel_x )}" )
        return newel_x
    def decode( self, rdfvalue_x ):
        comp_u = super().decode( rdfvalue_x )
        # get the component to get its name
        comp_x = self.projorcomp._get_typeuri_rdf( comp_u )
        compname = rdfxml.xmlrdf_get_resource_text( comp_x, ".//dcterms:title" )
        return compname

class ProjectAreaCodec( ComponentCodec ):
    # codec between PA name and PA url
    pass
    
    
# data type codecs
class BooleanCodec( StringLiteralCodec ):
    # codec between true/false and True/False
    def encode( self, pythonvalue ):
        if pythonvalue==True:
            result = "true"
        elif pythonvalue == False:
            result = "false"
        else:
            raise Exception( f"Not true or false '{pythonvalue}'" )
        thetag=rdfxml.uri_to_tag( self.prop_u )
        newel_x = ET.Element( thetag, { self.datatype: "http://www.w3.org/2001/XMLSchema#boolean" } )
        newel_x.text = result
#        print( f"{newel_x=} {ET.tostring( newel_x )}" )
        return newel_x
        
    def decode( self, rdfvalue_x ):
        trueness = rdfvalue_x.text
        if trueness=="true":
            return True
        if trueness=="false":
            return False
        raise Exception( f"Not a valid boolean '{trueness}'" )

class DateCodec( Codec ):
    pass
    
class DateTimeCodec( Codec ):
    def encode( self, pythonvalue ):
        if type( pythonvalue ) == str:
            # try to convert to a DateTime
            try:
                dt = datetime.datetime.fromisoformat( pythonvalue )
            except:
                raise Exception( f"Not a valid DateTime string: '{pythonvalue}'" )
        else:
            dt = pythonvalue
        if type( pythonvalue ) != datetime.datetime:
            raise Exception( f"Not a datetime.datetime object '{pythonvalue}'" )
    # <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2024-12-02T14:01:07.627Z</dcterms:created>
        result = dt.isoformat(sep=":",timespec='milliseconds')+"Z"
        #( "%Y-%d-%M:%H:%M:%SZ" )
        thetag=rdfxml.uri_to_tag( self.prop_u )
        newel_x = ET.Element( thetag, { self.datatype: "http://www.w3.org/2001/XMLSchema#dateTime" } )
        newel_x.text = result
#        print( f"{newel_x=} {ET.tostring( newel_x )}" )
        return newel_x
        
    def decode( self, rdfvalue_x ):
        rawvalue = rdfvalue_x.text
        result = datetime.datetime.fromisoformat( rawvalue )
        return result

class TimeCodec( Codec ):
    pass

class DurationCodec( Codec ):
    pass

class FloatCodec( Codec ):
    pass

class IntegerCodec( Codec ):
    pass
    
class StringCodec( StringLiteralCodec ):
    def __init__( self, *args,**kwargs ):
#        print( "Init StringCodec {self=}" )
        super().__init__( *args, **kwargs )
    def checkonassignment( self, value ):
        # accepts a string
        return
        
    


class InstanceShapeCodec( RDFResourceCodec ):
    def encode( self, pythonvalue ):
        burp # this is never encoded!
        thetag=rdfxml.uri_to_tag( self.prop_u )
        newel_x = ET.Element( thetag, { self.rdf_resource_tag: pythonvalue } )
#        print( f"{newel_x=} {ET.tostring( newel_x )}" )
        return newel_x
    def decode( self, rdfvalue_x ):
        shape_u = super().decode( rdfvalue_x )
        # get the shape
        shape = self.projorcomp.shapes.get( shape_u )
        if shape:
            return shape['name']
        raise Exception( f"Unknown shape {shape_u}" )

class UserCodec( Codec ):
    def __init__( self, *args,**kwargs ):
#        print( "Init UserCodec {self=}" )
        super().__init__( *args, **kwargs )
        
    def encode( self, pythonvalue ):
        thetag=rdfxml.uri_to_tag( self.prop_u )
        newel_x = ET.Element( thetag, { self.rdf_resource_tag: pythonvalue } )
#        print( f"{newel_x=} {ET.tostring( newel_x )}" )
        return newel_x
    def decode( self, rdfvalue_x ):
        userid_u = rdfxml.xmlrdf_get_resource_uri(rdfvalue_x)
        result = userid_u.rsplit( "/", 1 )[1]
        return result
    
class Resource( object ):
    name = "GenericResource"
    def __init__( self ):
        self.__lockdown_unmodifiables = False # unmodifiables get locked once the object initialisation from RDF has completed
        self._attribute_to_propuri={}
        
    def __setattr__( self, name, value ):
#        print( f"setattr {self=} {name=} {value=}" )
        if name.startswith( "_" ):
#            print( f"set_ {name} {value}" )
            super().__setattr__( name, value )
        else:
            if self.__lockdown_unmodifiables and name in self._projorcomp.unmodifiables and hasattr( self, name ):
                raise Exception( f"Attribute '{name}' is an unmodifiable system property!" )
#            print( f"set {name} {value}" )
            # TBC if an enumeration, check the value/values are actual enum names
            prop_u = self._attribute_to_propuri[ name ]
#            print( f"{prop_u=}" )
            
            prop = self._projorcomp.properties[prop_u]
#            print( f"{prop=}" )
            
            if self.__lockdown_unmodifiables and prop['typeCodec'] is not None:
                # if locked down, must be user code assigning value so check it
                thiscodec = prop['typeCodec']( self._projorcomp, self._shape_u, prop_u )
                thiscodec.checkonassignment( value )
                
            if prop['enums']:
                # an enum
                if type( value )==list:
                    if len( value )>1:
                        # check that the enum is multivalued
                        if not prop['isMultiValued']:
                            raise Exception( f"Property {name} is not multivalued but you tried to set it to a list with more than one element '{value}'" )
                        checkvalues = value
                else:
                    checkvalues = [value]
                    
                # check the values are in the enum and aren't repeated!
                checkeds = []
                for val in checkvalues:
                    if val not in self._projorcomp.get_enum_names( prop_u ):
                        raise Exception( f"Property {name} enum value '{val}' not a valid enumeration name - allwoed values are '{self._projorcomp.get_enum_names( prop_u )}'" )
                    if val in checkeds:
                        raise Exception( f"Property {name} value {val} appears more than once in {checkvalues}" )
                    checkeds.append( val )
                    
            if not hasattr( self, name  ) or value != getattr( self, name ):
                if not hasattr( self, "_modifieds" ):
                    self._modifieds = []
                if name not in self._modifieds:
                    # record setting or creating an attribute
                    # the attribute name must be in the allprops (which came from the typesystem for the shape)
                    self._modifieds.append( name ) 
#                    print( f"mod {name}" )

            # make sure there is an entry mapping the attribute name to its uri
            if not name in self._attribute_to_propuri:
                # need to add!
                self._attribute_to_propuri[name]=prop_u
            
            super().__setattr__( name, value )
            
    def put( self ):
        new_x = self.to_etree()
        # do the PUT
        result = self._projorcomp.execute_post_rdf_xml( self._url, data=new_x, headers={'If-Match':self._etag}, intent="Update the artifact", put=True )
        # update myself from the rdf
        self._projorcomp.resourceFactory( self._url, self._projorcomp, existingresource=self )
        
    def to_etree( self ):
        rawrdf = self._xml
        root = rawrdf.getroot()
        description = rdfxml.xml_find_element( root, 'rdf:Description[@rdf:about]' )
#        print( f"{description=}" )
#        print( f"{self._modifieds=}" )
        # scan the modifieds converting each modified to its rdf
        for attrname in self._modifieds:
#            print( f"{attrname=}" )
            # update by first removing all matching tags
            # then adding new ones - if the value is a list then add a tag for each one
            taguri = self._attribute_to_propuri.get( attrname )
#            print( f"{taguri=}" )
            prop = self._projorcomp.properties[taguri]
#            print( f"{prop=}" )
            shape_u = self._shape_u
            prefixedtag = rdfxml.uri_to_prefixed_tag( taguri )
#            print( f"{taguri=} {prefixedtag=}" )
            if taguri is None:
                burp
            for el in list( rdfxml.xml_find_elements( description, f'./{prefixedtag}' ) ):
#                print( f"To delete {el}" )
                description.remove( el )
            # check if the attr is still present - nothing to do if deleted
            if hasattr( self, attrname ):
                # add new tags encoded
                newvalues = getattr( self, attrname )
                if type( newvalues ) != list:
                    # make it a list
                    newvalues = [newvalues]
                for newvalue in newvalues:
                    thiscodec = prop['typeCodec']( self._projorcomp, shape_u, taguri )
                    newel_x = thiscodec.encode( newvalue )
                    # add this to the rawrdf
                    description.append( newel_x )
#                    
#        print( f"Result={ET.tostring( rawrdf,pretty_print=True ).decode()}" )
        return rawrdf
        
    # unmodifiables get locked once the object initialisation from RDF has completed
    def _lock_unmodifiables( self ):
        self.__lockdown_unmodifiables = True
        self._modifieds=[]
#        print( "Locked!" )
        pass

    # unmodifiables get locked once the object initialisation from RDF has completed
    def _unlock_unmodifiables( self ):
        self.__lockdown_unmodifiables = False
        self._modifieds=[]
#        print( "Unocked!" )
        pass
        
    # prints attributes that don't start with _ grouped by unmodifiable/modifiable
    def __repr__( self ):
#        print( "repr" )
        modifiablelines = [f"{k}: {self.__dict__[k]}" for k in sorted(self.__dict__.keys()) if not k.startswith( "_" ) and not k in self._projorcomp.unmodifiables ]
        unmodifiablelines = [f"{k}: {self.__dict__[k]}" for k in sorted(self.__dict__.keys()) if not k.startswith( "_" ) and k in self._projorcomp.unmodifiables]
        result = f"{type(self)} {id(self)=}\nUnmodifiable:\n  "+"\n  ".join( unmodifiablelines )+"\nModifiable:\n  "+"\n  ".join( modifiablelines )+"\n"
        return result
        
    def addCoreArtifactLink( self, linktypename, targetid ):
        # find the linktype
        lt_u = self._projorcomp.get_linktype_uri( linktypename )
#        print( f"{lt_u=}" )
        
        if lt_u is None:
            raise Exception( f"Link type '{linktypename}' not found" )
        linkattrname = makeSafeAttributeName( linktypename )
#        print( f"{linkattrname=}" )
        # find the target id
        target_u = self._projorcomp.queryCoreArtifactByID( targetid )
        if target_u is None:
            raise Exception( f"target id '{targetid}' not found" )
            
        # check link doesn't already exist
        # TBC
        
        # add the link
        setattr( self, linkattrname, targetid )
        
        pass

def makeSafeAttributeName( name, propuri ):
#    print( f"Make safe name fror {name }" )
    res = ""
    for c in name:
        if not c.isalpha():
            c = "_"
        res += c
    if keyword.iskeyword( res ) or keyword.issoftkeyword( res ):
#        print( f"unsafe {name}" )
        res = makeSafeAttributeName( rdfxml.uri_to_prefixed_tag( propuri ), propuri )
#    print( f"Make safe name fror {name } {res}" )
    return res
        
@utils.mixinomatic
class Resources_Mixin:
    def __init__(self,*args,**kwargs):
        super().__init__()
        
    def retrieveResource( self, resourceURL ):
        return self.resourceFactory( resourceURL, self )
        
    def queryCoreArtifactByID( self, id, cacheable=True ):
        
        # get the query capability base URL for requirements
        qcbase = self.get_query_capability_uri("oslc_rm:Requirement")


        ####################################################################################
        # find the FROM artifact using OSLC Query
        # query for the id
        artifacts = self.execute_oslc_query(
            qcbase,
            whereterms=[['dcterms:identifier','=',f'"{id}"']],
            select=['*'],
            prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'}, # note this is reversed - url to prefix
            cacheable=cacheable
            )
            
        if len(artifacts)==0:
            raise Exception( f"No artifact with identifier '{fromid}' found in project {proj} component {comp} configuration {conf}" )
        elif len(artifacts)>2:
            for k,v in artifacts.items():
                print( f'{k} ID {v.get("dcterms:identifier","???")} Title {v.get("dcterms:title","")}' )
            raise Exception( "More than one artifcact with that id in project {proj} component {comp} configuraition {conf}" )
        
        # find the core artifact - it has a value for rm_nav:parent
        fromartifact_u = None
        for artifact in artifacts.keys():
    #        print( f"Testing parent on {artifact=}" )
            if artifacts[artifact].get("rm_nav:parent") is not None:
                fromartifact_u = artifact
                break

        if fromartifact_u is None:
            raise Exception( f"Target id '{id}' not found" )
        
        return fromartifact_u
        
    def findResourcesPrepareQuery( self ):
        pass
    def findResourcesAddTermToQuery( self, query, prop, proptest, propvalue ):
        pass
    def executeQuery( self, query ):
        pass
        
    # this builds or updates a resource from rdf-xml containing the properties
    # the properties are turned into attributes with the human-friendly name
    def resourceFactory( self, resourceURL, projorcomp, existingresource=None ):
        # read the resource and create/return an object
        xml, etag = projorcomp.execute_get_rdf_xml( resourceURL, return_etag=True, intent="Retrieve the artifact", cacheable=False )
#        print( f"\n\n{resourceURL=}" )
        # the type discriminator hopefully knows how to decide what type of resource this thing is
        if existingresource is None:
            res = projorcomp.resourcetypediscriminator( xml )
        else:
            res = existingresource
            # clean down the existing resource - in particulatr remove all attributes
            res._unlock_unmodifiables()
            # remove all attributes
            for attr in res._attribute_to_propuri.keys():
                delattr( res, attr )
#            
#        print( f"{res=}" )
        res._xml = xml
        res._etag = etag
        res._url = resourceURL
        res._projorcomp = projorcomp
        res._attribute_to_propuri = {} # key is the property name, value is the prefixed for that property - used to allow the full tag name to be reconstructed from just the property name
#        res._formats = {} # remember the format for a property so it can be updated correctly when generating rdf-xml to PUT to update the resource
#        res._types = {} # the Type for each property - used to encode/decode between a python object and and RDF value
        
        # make sure typesystem is loaded for this component
        projorcomp.load_types()

        # extract the shape for this object
        shapeurl = rdfxml.xmlrdf_get_resource_uri( xml, './/oslc:instanceShape' )
        res._shape_u = shapeurl
        print( f"{shapeurl=}" )
        
        # look up the shape in typesystem
        shape = projorcomp.is_known_shape_uri( shapeurl )
        print( f"{shape=}" )
        shapename = shape['name']
        print( f"{shapename=}" )

        maintag = rdfxml.xml_find_element( xml.getroot(), ".//rdf:Description[@rdf:about]" )
        if maintag is None:
            burp
        # scan the top-level tags and convert into attributes on res
        for child in maintag:
            print( f"Child {child.tag} {child.text}" )
            print( f"{ET.tostring( child )=}" )
            prefixedtag = child.tag
            taguri = rdfxml.tag_to_uri( child.tag )
            print( f"{taguri=} {child.tag=}" )
            prefix,tag = prefixedtag.split( "}", 1 )
            prefix = prefix[1:] # remove the leading {
#            if tag in ['type','accessControl','parent','serviceProvider']:
            if tag in ['accessControl','serviceProvider']:
                continue
                
            # get the property name
            nameuri = rdfxml.tag_to_uri(prefixedtag)
#            print( f"{nameuri=}" )
            propname = projorcomp.resolve_uri_to_name( nameuri )
#            print( f"{propname=}" )
            if propname.startswith( "http" ):
                # no friendly name so use just the tag
                propname = tag
#                print( f"Using tag {tag} for {propname}" )
            else:
#                print( f"No http for {propname}" )
                pass
                
            # make the property name a safe Python attribute name
            propname = makeSafeAttributeName( propname, taguri )
#            print( f"safe {propname=}" )

            # work out what format the thing is from the typesystem, using the tag of the child
            propdef = self.properties.get( taguri )
            if not propdef:
#                print( f"\nNo Property!\n{self.properties}" )
                # unknown property - ask the application if it wants to map it to a dummy property (!)
                if not self.mapUnknownProperty( propname, taguri, shapeurl ):
                    raise Exception( f"Unkown property in RDF! {propname} {taguri} {shapeurl}" )
                propdef = self.properties.get( taguri )
                
            # make sure there is an entry mapping the safe attribute name to its uri
            if not propname in res._attribute_to_propuri:
                # need to add!
                res._attribute_to_propuri[propname]=taguri        
#                print( f"{res._attribute_to_propuri=}" )
                
#            print( f"{propdef=}" )
            # use the codec to decode the value
            thecodec = propdef['typeCodec']
            if thecodec is None:
                raise Exception( f"No codec for {propdef['name']} {taguri}!" )
            else:
                thiscodec = thecodec( projorcomp, shapeurl, taguri )
#            print( f"{thiscodec=}" )
            
            value = thiscodec.decode( child )
            
#            print( f"{value=}" )

            if False:
                # work out what the attribute name will be - from the type!
                # work out what type the value is, and what it's value is
                if len(child)>0 and parsetype == "Literal":
                    # get the XML literal value by converting the whole child to a string and then strip off the start/end tags!
                    # (shouldn't there be a less hacky way of doing this?)
                    literal = ET.tostring(child).decode()
                    value = literal[literal.index('>')+1:literal.rindex('<')]
        #            print( f"0 {prefixedtag}  {value=}" )
                    res._formats[tag] = XMLLITERAL
                elif child.text is None or not child.text.strip():
                    # no text, try the resource URI
                    rawvalue = rdfxml.xmlrdf_get_resource_uri( child )
                    if rawvalue is None:
                        # no resource URI, use an empty string
                        value = ""
                    else:
                        value = projorcomp.resolve_uri_to_name( rawvalue )
#                        print( f"Value name={value}" )
        #            print( f"1 {prefixedtag}  {value=}" )
                    res._formats[tag] = RDFRESOURCE
                else:
                    rawvalue = child.text.strip()
                    if datatype == "http://www.w3.org/2001/XMLSchema#dateTime":
                        # convert to datetime object from 2025-07-07T08:25:18.624Z
                        value = datetime.datetime.fromisoformat( rawvalue )
                    elif utils.isint( rawvalue ):
                        value = int( rawvalue )
                    else:
                        value = rawvalue
        #            print( f"2 {prefixedtag} {value=}" )
                    res._formats[tag] = TEXT

            # remember the property uri for this attribute name
            if taguri in res._attribute_to_propuri:
                if res._attribute_to_propuri[ propname ] == taguri:
                    # same tag/prefix already there - that's OK
                    pass
                else:
                    raise Exception( "Different duplicated definition for {taguri} - new one is {propname} and original is {self._attribute_to_propuri[taguri]}!" )
            else:
                # remember the prefix for this tag
                res._attribute_to_propuri[ propname ] = taguri
#                print( f"Saved prefix {tag} {prefix} {propname}" )
                
    #        print( f"Setting {propname=} {value=}" )
            # put the value into the attribute, allowing that if there's already a value this becomes a list when the second entry is added
            if hasattr( res, propname ):
                # already got one value - may need to make or extend a list of values
                existingvalue = getattr( res, propname )
    #            print( f"{existingvalue=}" )
                if type( existingvalue ) != list:
                    # make the existing single value into a list with the new value added
                    setattr( res, propname, [existingvalue]+[value] )
    #                print( f"A {getattr(res,propname)}" )
                else:
                    # extend the existing list with the new value
                    setattr( res, propname, existingvalue+[value] )
    #                print( f"B {getattr(res,propname)}" )
            else:
                setattr( res, propname, value )
    #            print( f"C {getattr(res,propname)}" )
    #            newvalue = getattr( self, tag )
    #            self.__setitem__( tag, newvalue )
            # TBD handle the links!
            
    #    pp.pprint( res.__dict__ )
        res._lock_unmodifiables()
#        burp
        return res
        
        def resourceToObject( self ):
            raise Exception( "Save not implemented yet" )
            # convert self into a specific type of resource
            pass

        
if __name__ == "__main__":
    # simple test harness
    # options: app, action (start/stop/status)
    
    # get some defaults from the environment (which can be overridden on the commandline or the saved obfuscated credentials)
    JAZZURL     = os.environ.get("QUERY_JAZZURL"    ,"https://jazz.ibm.com:9443" )
    USER        = os.environ.get("QUERY_USER"       ,"ibm" )
    PASSWORD    = os.environ.get("QUERY_PASSWORD"   ,"ibm" )
    JTS         = os.environ.get("QUERY_JTS"        ,"jts" )
    APPSTRINGS  = os.environ.get("QUERY_APPSTRINGS" ,"rm" )
    LOGLEVEL    = os.environ.get("QUERY_LOGLEVEL"   ,None )

    # setup arghandler
    parser = argparse.ArgumentParser(description="Test harness for resource.py")

    parser.add_argument('-c','--componentname', default=None, help='component name')
    parser.add_argument('-f','--configurationname', default=None, help='config')
    parser.add_argument('-i','--id', default=[], nargs='*', help='artifact id')
    parser.add_argument('-p','--projectname', default=None, help='project name')
    
    parser.add_argument('-A', '--appstrings', default=None, help=f'A comma-seperated list of apps, the action goes to the first entry, default "{APPSTRINGS}". Each entry must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using environemnt variable QUERY_APPSTRINGS')
    parser.add_argument("-J", "--jazzurl", default=JAZZURL, help=f"jazz server url (without the /jts!) default {JAZZURL} - Default can be set using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T EXIST")
    parser.add_argument('-L', '--loglevel', default=None,help=f'Set logging to file and (by adding a "," and a second level) to console to one of DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is {LOGLEVEL} - can be set by environment variable QUERY_LOGLEVEL')
    parser.add_argument("-P", "--password", default=PASSWORD, help=f"user password, default {PASSWORD} - Default can be set using environment variable QUERY_PASSWORD - set to PROMPT to be asked for password at runtime")
    parser.add_argument('-T', '--certs', action="store_true", help="Verify SSL certificates")
    parser.add_argument("-U", "--username", default=USER, help=f"user id, default {USER} - Default can be set using environment variable QUERY_USER")
    parser.add_argument('-V', '--verbose', action="store_true", help="Show verbose info")
    parser.add_argument('-Z', '--proxyport', default=8888, type=int, help='Port for proxy default is 8888 - used if found to be active - set to 0 to disable')
    
    # saved credentials
    parser.add_argument('-0', '--savecreds', default=None, help="Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, appstring, username and password")
    parser.add_argument('-1', '--readcreds', default=None, help="Read obfuscated credentials from file - completely overrides commandline/environment values for jazzurl, jts, appstring, username and password" )
    parser.add_argument('-2', '--erasecreds', default=None, help="Wipe and delete obfuscated credentials file" )
    parser.add_argument('-3', '--secret', default="N0tSeCret-", help="SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater security) - only affects if using -0 or -1" )
    parser.add_argument('-4', '--credspassword', action="store_true", help="Prompt user for a password to save/read obfuscated credentials (make this longer for greater security)" )

    args = parser.parse_args()

    if args.projectname is None:
        args.projectname = "rm_optin_p1"
        args.componentname = args.projectname 
        rgs.configurationname = args.projectname +" Initial Stream"
    if args.erasecreds:
        # read the file to work out length
        contentlen = len(open(args.erasecreds,"rb").read())
        # create same-length random data to overwrite
        for i in range(5):
            randomcontent = os.urandom(contentlen)
            open(args.erasecreds,"w+b").write(randomcontent)
        # and delete the file
        os.remove(args.erasecreds)

 #       print( f"Credentials file {args.erasecreds} overwritten then removed" )
        exit(0)

    if args.credspassword:
        if args.readcreds is None and args.savecreds is None:
            raise Exception( "When using -4 you must use -0 to specify a file to save credentials into, and/or -1 to specify a credentials file to read" )
        #make sure the user enters at least one character
        credspassword = ""
        while len(credspassword)<1:
            credspassword = getpass.getpass( "Password (>0 chars, longer is more secure)?" )
    else:
        credspassword = "N0tSecretAtAll"

    if args.readcreds:
#        if args.secret is None:
#            raise Exception( "You MUST specify a secret using -3 or --secret if using -0/--readcreads" )
        try:
            args.username,args.password,args.jazzurl,apps = json.loads( utils.fernet_decrypt(open(args.readcreds,"rb").read(),"=-=".join([socket.getfqdn(),os.path.abspath(args.readcreds),getpass.getuser(),args.secret,credspassword])) )
            # allow overriding appstrings stored in creads with option on commandline
            args.appstrings = args.appstrings or apps
        except (cryptography.exceptions.InvalidSignature,cryptography.fernet.InvalidToken, TypeError):
            raise Exception( f"Unable to decrypt credentials from {args.readcreds}" )
#        print( f"Credentials file {args.readcreds} read" )
        
    # if no appstring yet specified use the default
    args.appstrings = args.appstrings or APPSTRINGS
    
    if args.savecreds:
        if args.secret is None:
            raise Exception( "You MUST specify a secret using -3 or --secret if using -1/--savecreads" )
        open(args.savecreds,"wb").write(utils.fernet_encrypt(json.dumps([args.username,args.password,args.jazzurl,args.appstrings]).encode(),"=-=".join([socket.getfqdn(),os.path.abspath(args.savecreds),getpass.getuser(),args.secret,credspassword]),utils.ITERATIONS))
#        print( f"Credentials file {args.savecreds} created" )
        exit(0)

    # do a basic check that the target server is in fact running, this way we can give a clear error message
    # to do this we have to get the host and port number from args.jazzurl
    urlparts = urllib.parse.urlsplit(args.jazzurl)
    if ':' in urlparts.netloc:
        serverhost,serverport = urlparts.netloc.rsplit(":",1)
        serverport = int(serverport)
    else:
        serverhost = urlparts.netloc
        if urlparts.scheme=='https':
            serverport=443
        elif urlparts.scheme=='http':
            serverport=80
        else:
            raise Exception( "Unknown scheme in jazzurl {args.jazzurl}" )
            
    # now try to connect
    if not server.tcp_can_connect_to_url(serverhost, serverport, timeout=2.0):
        raise Exception( f"Server not contactable {args.jazzurl}" )

    # setup logging
    if args.loglevel is not None:
        levels = [utils.loglevels.get(l,-1) for l in args.loglevel.split(",",1)]
        if len(levels)<2:
            # if only one log level specified this is for file loggin - set console to None
            levels.append(None)
        if -1 in levels:
            raise Exception( f'Logging level {args.loglevel} not valid - should be comma-separated one or two values from DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF' )
        utils.setup_logging( filelevel=levels[0], consolelevel=levels[1] )

    logger = logging.getLogger(__name__)

    utils.log_commandline( os.path.basename(sys.argv[0]),sys.argv[1:] )

    if args.password is None or args.password=="PROMPT":
        args.password = getpass.getpass(prompt=f'Password for user {args.username}: ')

    # request proxy config if appropriate
    if args.proxyport != 0:
        server.setupproxy(args.jazzurl,proxyport=args.proxyport)

    # approots has keys of the domain and values of the context root
    approots = {}
    allapps = {} #keyed by domain
    themainappstring = args.appstrings.split(",")[0]
    themaindomain = server.JazzTeamServer.get_appstring_details(themainappstring)[0]

    for appstring in args.appstrings.split(","):
        domain,contextroot = server.JazzTeamServer.get_appstring_details(appstring)
        if domain in approots:
            raise Exception( f"Domain {domain} must not appear twice in {args.appstrings}" )
        approots[domain]=contextroot

    # assert the jts default context root if not already specified in args.appstring
    if 'jts' not in approots:
        approots['jts']='jts'

    # create our "server"
    theserver = server.JazzTeamServer(args.jazzurl, args.username, args.password, verifysslcerts=args.certs, jtsappstring=f"jts:{approots['jts']}" )

    # create all our apps (there will be a main app which is specified by the first appstrings value, the main reason for allowing more than one is when gc is needed
    for appdom,approot in approots.items():
        allapps[appdom] = theserver.find_app( f"{appdom}:{approot}", ok_to_create=True )

    # get the main app - it's the one we're going to work with - it was first in args.appstring
    themainapp = allapps[themaindomain]

    ######################################################
    # find the project and if using components find the component and configuration
    theproj = themainapp.find_project(args.projectname)

    if theproj is None:
        raise Exception( f"Project '{args.projectname}' not found")

    # assert default for the component name to be the same as the project name
    if args.componentname is None:
        if theproj.is_optin:
            print( f"Warning - project '{args.projectname}' is opt-in but you didn't specify a component - using default component '{args.projectname}'" )
        args.componentname = args.projectname

    # not all apps support components, and even if the app does this project may not be opt-in
    if themainapp.supports_components:
        if not theproj.singlemode and not args.componentname:
            raise Exception( f"Project {args.projectname} supports components so you must provide a component name" )
        if theproj.singlemode:
            args.componentname = args.projectname
        thecomp = theproj.find_local_component(args.componentname)
        if not thecomp:
            raise Exception( f"Component '{args.componentname}' not found in project {args.projectname}" )
        # assert the default configuration for this component if none is specified
        if args.configurationname is None:
            args.configurationname = thecomp.initial_stream_name()
            print( f"Warning - project '{args.projectname}' is opt-in but for component '{args.componentname}' you didn't specify a local configuration - using default stream '{thecomp.initial_stream_name()}'" )
        logger.info( f"{args.configurationname=}" )
        if theproj.is_optin:
            if args.configurationname or theproj.singlemode:
                if theproj.singlemode:
                    if args.configurationname is None:
                        # default to the stream
                        args.configurationname = thecomp.get_default_stream_name()
                config = thecomp.get_local_config(args.configurationname)
                if config is None:
                    raise Exception( f"Configuration '{args.configurationname}' not found in component {args.componentname}" )

                thecomp.set_local_config(config)
                logger.debug( f"LOCAL {config=}" )
            else:
                raise Exception( f"Project {args.projectname} is opt-in so you must provide a local configuration" )
        else:
            if args.configurationname is None:
                # default to the stream
                args.configurationname = thecomp.get_default_stream_name()
            config = thecomp.get_local_config(args.configurationname)
            if config is None:
                raise Exception( f"Configuration '{args.configurationname}' not found in component {args.componentname}" )

        thecomp.set_local_config(config)

        queryon = thecomp
    else:
        queryon = theproj

    print( f"{queryon=}" )

    mores = queryon.queryResourcesByIDs( args.id )
    print( f"{mores=}" )
    print( mores[0].Identifier )
    mores[0].Identifier = 23
    mores[0].Priority = "prime"


    # find the project
    
    # find the component
    
    # find the config
    
    # set the config
    
    # find the resource

    print( "Finished" )
    