##
## © Copyright 2025- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# routines to encapsulate a generic ELM resource as an object with attributes
#
# Creates the object by retrieving the RDF and using the tags to create attributes
#
# Provide PUT to update the resource in ELM
#

from . import utils
from . import rdfxml

import lxml.etree as ET


import collections

# formats for properties
XMLLITERAL = 1
RDFRESOURCE = 2
TEXT = 3

# unmodifiable (system) properties
unmodifiables = [
	'accessControl',
	'component',
	'contributor',
	'created',
	'creator',
	'identifier',
	'instanceShape',
	'modified',
	'projectArea',
	'serviceProvider',
	'type',
	]

class BaseResource( collections.UserDict ):
    def __init__( self, projorcomp, resourceURL ):
        super().__init__( self )
        self._url = resourceURL
        self._projorcomp = projorcomp
        # read the resource, save the ETag
        self._prefixes = {} # key is the property name, value is the prefix for that property - used to allow the full tag name to be reconstructed from just the property name
        self._modifieds = [] # the list of modified properties
        self._formats = {} # remember the format for a property so it can be updated correctly

        self._force = True
        
        # read the resource and create/return an object
        xml, etag = self._projorcomp.execute_get_rdf_xml( self._url, return_etag=True, intent="Retrieve the artifact" )
#        print( f"{xml=}" )
        self._etag = etag
        self._xml = xml
#        self.data = {}
        
        # scan the top-level tags and convert into properties
        for child in xml.getroot()[0]:
#            print( f"Child {child.tag} {child.text}" )
            prefixedtag = child.tag
            prefix,tag = prefixedtag.split( "}", 1 )
            prefix = prefix[1:] # remove the leading {
            
            # work out what the value is
            if len(child)>0 and rdfxml.xmlrdf_get_resource_uri( child, attrib="rdf:parseType" ) == "Literal":
                # get the XML literal value by converting the whole child to a string and then strip off the start/end tags!
                # (shouldn't there be a less hacky way of doing this?)
                literal = ET.tostring(child).decode()
                value = literal[literal.index('>')+1:literal.rindex('<')]
                self._formats[tag] = XMLLITERAL
            elif child.text is None or not child.text.strip():
                # no text, try the resource URI
#                value = child.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
                value = rdfxml.xmlrdf_get_resource_uri( child )
                if value is None:
                    # no resource URI, use an empty string
                    value = ""
                # print( f"1 {value=}" )
                self._formats[tag] = RDFRESOURCE
            else:
                value = child.text,strip()
                # print( f"2 {value=}" )
                self._formats[tag] = TEXT

            # remember the prefix for this property name
            if tag in self._prefixes:
                if self._prefixes[ tag ] == prefix:
                    # same tag/prefix already there - that's OK
                    pass
                else:
                    raise Exception( "Different duplicated definition for {tag} - new one is {prefix} and original is {self._prefixes[tag]}!" )
            else:
                # remember the prefix for this tag
                self._prefixes[ tag ] = prefix
                
            print( f"{tag=} {value=}" )
            # put the value into the attribute, allowing that if multiple tags are present which become lists when the second entry is added
            if hasattr( self, tag ):
                # already got one value - may need to make or extend a list of values
                existingvalue = getattr( self, tag )
                if type( existingvalue ) != list:
                    # make the existing single value into a list with the new value added
                    setattr( self, tag, [existingvalue]+[value] )
                else:
                    # extend the existing list with the new value
                    setattr( self, tag, existingvalue+[value] )
            else:
                setattr( self, tag, value )
            newvalue = getattr( self, tag )
            self.__setitem__( tag, newvalue, force=True )
            
        print( f"{self.__dict__=}" )
        self._modifieds = []
        self._force = False

    def __repr__( self ):
        lines = [f"{k}: {super().data[k]}" for k in sorted(super().data.keys())]
        result = "\n".join( lines )
        return result
        
#    def __getitem__(self, key):
#        pass

#    # don't allow modifying system properties
#    def __setitem__(self, key, value, force=False):
#        if not force and key in unmodifiables:
#            raise Exception( f"Key {key} is an unmodifiable system property!" )
#        super().__setitem__(key, value)
#        # remember modified properties
#        if key not in self._modifieds:
#            self._modifieds.append( key )
            
    def __getattribute__( self, name ):
        if name.startswith( "_" ):
            return super().__getattribute__( name )
        if name not in super()._prefixes:
            raise Exception( "No property {name}!" )            
        taggedname = f"{{{super()._prefixes[name]}}}:{name}"
        if taggedname not in super().data:
            raise Exception( "No property data for {name}!" )
        return super().data.get(name)
        
    def __setattr__( self, name, value ):
        if name.startswith( "_" ):
            super().__setattr__( name, value )
        else:
            if not super()._force and name in unmodifiables:
                raise Exception( f"Attribute {name} is an unmodifiable system property!" )
            if not super()._force and name not in super()._prefixes:
                raise Exception( "No property {name}!" )
            taggedname = f"{{{super()._prefixes[name]}}}:{name}"
            super().data[taggedname] = value
        
    def save( self ):
        raise Exception( "Save not implemented yet" )
        # generate rdf xml updated with the modified properties
        x = super()._xml
        for prop in super()._modifieds:
            # update x with the new value
            fulltag = f"{{{super()._prefixes[mod]}}}:{prop}"
            if super()._formats[prop] == XMLLITERAL:
                pass
            elif super()._formats[prop] == RDFRESOURCE:
                pass
            elif super()._formats[prop] == TEXT:
                pass
            else:
                burp
            tags_x = rdfxml.findelements( x, f".//{fulltag}" )
            if not tags_x:
                burp
            if type( value ) == list:
                if len( tags_x ) != len( super().__getattribute__( prop ) ):
                    raise Exception( "number of elements vs list of values is inconsistent!" )
                # add a tag for each entry/value
            else:
                # add a tag for the value
                pass
        pass
        
    def resourceToObject( self ):
        raise Exception( "Save not implemented yet" )
        # convert self into a specific type of resource
        pass
        
class BindingResource( BaseResource):
    pass
    
class ArtifactResource( BaseResource ):
    pass

class ModuleResource( BaseResource ):
    def getModuleBindings( self ):
        raise Exception( "Save not implemented yet" )
        pass

        
@utils.mixinomatic
class Resources_Mixin:
    def __init__(self,*args,**kwargs):
        super().__init__()
        
    def retrieveResource( self, resourceURL ):
        return BaseResource( self, resourceURL )
        
    def findResourcesByIDs( self, identifiers, *, returnBaseResources=True, returnBindings=True, returnModules=True, filterFunction=None ):
        # identifiers is a single id or a list of ids
        if type(identifiers) != list:
            # make identifiers a list
            identifiers = [ identifiers ]
        # use OSLC Query then if necessary post-processes the results
        # return Resources!
        # query
            # get the query capability base URL for requirements
        qcbase = c.get_query_capability_uri("oslc_rm:Requirement")

        # query for the identifiers
        artifacts = c.execute_oslc_query(
            qcbase,
            whereterms=[['dcterms:identifier','in',f'[{",".join(identifiers)}]']],
            select=['*'],
            prefixes={rdfxml.RDF_DEFAULT_PREFIX["dcterms"]:'dcterms'} # note this is reversed - url to prefix
            )
        results = []
        print( f"{artifacts=}" )
        for art in artifacts:
            if returnBaseResources:
                # check for nav:parent
                pass
            if returnBindings:
                # check for absence of nav:parent
                pass
            if returnModules:
                # check for format Module
                pass
            if filterFunction:
                if not filterFunction( art ):
                    continue
            results.append( art )
            pass
        pass
        
    