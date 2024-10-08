##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# typesystem support for typesdiff
#

import datetime
import logging
import re
import sys
import time

import anytree
import dateutil.parser
import dateutil.tz
import lxml.etree as ET
import requests
import tqdm
import pytz

from . import _app
from . import _config
from . import _project
from . import _typesystem
from . import oslcqueryapi
from . import rdfxml
from . import server
from . import utils




#################################################################################################

logger = logging.getLogger(__name__)

#################################################################################################


# typesdiff info
CHECKERROR   = "ERROR"
CHECKWARNING = "WARNING"
CHECKINFO    = "INFO"

# NOTE these are scope-sensitive to where they are invoked because of variable expansions at runtime which must be available!
# just don't put anything too exotic in the template!
OT_RENAMED                 = ( CHECKINFO,  "Artifact Type {a.name} was renamed after '{self.config_name}' to {b.name} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
OT_URI_ADDED               = ( CHECKINFO,  "Artifact Type {a.name} didn't have a URI in '{self.config_name}' and URI {b.uri} was added in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
OT_URI_REMOVED             = ( CHECKERROR, "Artifact Type {a.name} had a URI {a.uri} in '{self.config_name}' which has been removed in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
OT_URI_CHANGED             = ( CHECKERROR, "Artifact Type {a.name} had a URI {a.uri} in '{self.config_name}' which has been changed to {b.uri} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
OT_AD_REMOVED              = ( CHECKERROR, "Artifact Type {a.name} had attribute(s) {inanotb} in '{self.config_name}' which have been removed in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
OT_AD_ADDED                = ( CHECKERROR, "Artifact Type {a.name} had attribute(s) {inbnota} added after '{self.config_name}' into '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AD_RENAMED                 = ( CHECKINFO,  "Attribute Definition {a.name} was renamed after '{self.config_name}' to {b.name} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AD_URI_ADDED               = ( CHECKINFO,  "Attribute Definition {a.name} didn't have a URI in '{self.config_name}' and URI {b.uri} was added in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AD_URI_REMOVED             = ( CHECKERROR, "Attribute Definition {a.name} had a URI {a.uri} in '{self.config_name}' which has been removed in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AD_URI_CHANGED             = ( CHECKERROR, "Attribute Definition {a.name} had a URI {a.uri} in '{self.config_name}' which has been changed to {b.uri} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AD_WAS_MULTIVALUED         = ( CHECKERROR, "Attribute Definition {a.name} was multivalued in '{self.config_name}' and has been changed to not multivalued in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AD_BECAME_MULTIVALUED      = ( CHECKERROR, "Attribute Definition {a.name} was not multivalued in '{self.config_name}' and has been changed to multivalued in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AD_BASE_TYPE_URL_CHANGED   = ( CHECKERROR, "Attribute Definition {a.name} had base type changed from {a.basetypeurl} in '{self.config_name}' to {b.basetypeurl} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_RENAMED                 = ( CHECKINFO,  "Attribute Type {a.name} was renamed after '{self.config_name}' to {b.name} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_URI_ADDED               = ( CHECKINFO,  "Attribute Type {a.name} had no URI in '{self.config_name}' and a URI {b.uri} was added in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_URI_REMOVED             = ( CHECKERROR, "Attribute Type {a.name} had a URI {a.uri} in '{self.config_name}' which has been removed in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_URI_CHANGED             = ( CHECKERROR, "Attribute Type {a.name} had a URI {a.uri} in '{self.config_name}' which has been changed to {b.uri} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_BASE_TYPE_URL_CHANGED   = ( CHECKERROR, "Attribute Type {a.name} had base type changed from {a.basetypeurl} in '{self.config_name}' to {b.basetypeurl} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_ENUM_REMOVED            = ( CHECKERROR, "Attribute Type {a.name} was an enum in '{self.config_name}' which has been changed to not an enum in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_ENUM_ADDED              = ( CHECKERROR, "Attribute Type {a.name} was not an enum in '{self.config_name}' which has been changed to an enum in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_ENUMVALUE_REMOVED       = ( CHECKERROR, "Attribute Type {a.name} had enum {e.name} value {e.value} uri {e.uri} in '{self.config_name}' which has been removed in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_ENUMVALUE_ADDED         = ( CHECKERROR, "Attribute Type {a.name} had enum added {e.name} value {e.value} uri {e.uri} after '{self.config_name}' added in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_ENUMVALUE_RENAMED       = ( CHECKERROR, "Attribute Type {a.name} enum value {a.enumurls[e].name} renamed after '{self.config_name}' to {b.enumurls[e].name} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_ENUMVALUE_URI_CHANGED   = ( CHECKERROR, "Attribute Type {a.name} enum value {a.enumurls[e].name} had uri changed from {a.enumurls[e].name} in '{self.config_name}' to {b.enumurls[e].name} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
AT_ENUMVALUE_VALUE_CHANGED = ( CHECKERROR, "Attribute Type {a.name} enum value {a.enumurls[e].name} had value changed from {a.enumurls[e].value} in '{self.config_name}' to {b.enumurls[e].value} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )

LT_RENAMED                 = ( CHECKINFO,  "Attribute Type {a.name} was renamed after '{self.config_name}' to {b.name} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
LT_URI_ADDED               = ( CHECKINFO,  "Attribute Type {a.name} had no URI in '{self.config_name}' and a URI {b.uri} was added in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
LT_URI_REMOVED             = ( CHECKERROR, "Attribute Type {a.name} had a URI {a.uri} in '{self.config_name}' which has been removed in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )
LT_URI_CHANGED             = ( CHECKERROR, "Attribute Type {a.name} had a URI {a.uri} in '{self.config_name}' which has been changed to {b.uri} in '{theothertypesystem.config_name}'! - change was by {b.modifiedBy} on {b.modified}" )

OT_URI_MISSING              = ( CHECKWARNING, "Artitact Type {a.name} does not have a RDF URI" )
AD_URI_MISSING              = ( CHECKWARNING, "Attribute Definition {a.name} does not have a RDF URI" )
AT_URI_MISSING              = ( CHECKWARNING, "Attribute Type {a.name} does not have a RDF URI" )
AT_ENUMVALUE_URI_MISSING    = ( CHECKWARNING, "Enumeration value {a.name} does not have a RDF URI" )
LT_URI_MISSING              = ( CHECKWARNING, "Link Type {a.name} does not have a RDF URI" )

# within a snapshot (stream or baseline)
DUPLICATED_NAME = ( CHECKERROR, "Type name is used twice or more in stream/baseline" )

# within a component
#duplicated name with different URI
#duplicated name with different type
#name used differently


# GC-related (multiple streams/contributions)
OT_RDFURI_NOT_IN_ALL_STREAMS = ( CHECKERROR,"TBC ( when it's present in at least one contributions) (can't know which type it should be on but can show the names of types where it's present)(might be deliberate, e.g. because different types are in different contributions)" )
AD_RDFURI_NOT_IN_ALL_STREAMS = ( CHECKERROR,"TBC when it's present in at least one contributions) (can't know which type it should be on but can show the names of types where it's present)(might be deliberate, e.g. because different types are in different contributions)" )
AT_RDFURI_NOT_IN_ALL_STREAMS = ( CHECKERROR,"TBC # (when it's present in at least one contributions) (can't know which type it should be on but can show the names of types where it's present)(might be deliberate, e.g. because different types are in different contributions)" )
AT_ENUMVALUE_RDFURI_NOT_IN_ALL_STREAMS = ( CHECKERROR,"TBC # (when it's present in at least one contributions) (can't know which type it should be on but can show the names of types where it's present)(might be deliberate, e.g. because different types are in different contributions)" )
LT_RDFURI_NOT_IN_ALL_STREAMS = ( CHECKERROR,"TBC # (when it's present in at least one contributions) (can't know which type it should be on but can show the names of types where it's present)(might be deliberate, e.g. because different types are in different contributions)" )

# rdf uri used on a different thing (type URI is different) between two streams


# question about checking GC - should the check happen on all GC baselines and streams?




class _TypeChecker( object ):
    pass
class OTChecker( _TypeChecker ):
    pass
class ADChecker( _TypeChecker ):
    pass
class ATChecker( _TypeChecker ):
    pass
    

class _DNType( object ):
    URL = None
    URI = None
    name = None
    isused = False
    title = "Generic type"
    def __init__( self, url, uri, name, component, isused=False, modified=None, modifiedBy=None ):
        self.url = url
        self.uri = uri
        self.name = name
        self.isused = isused
        self.modified = modified
        self.modifiedBy = modifiedBy
        self.component = component
    def __repr__( self ):
        return f"{vars(self)}"

class OT( _DNType ):
    attriburls = []
    title = "OT"
    def __init__( self, url, uri, name, component, attriburls, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, component, modified=modified, modifiedBy=modifiedBy, isused=isused )
        self.attriburls = attriburls

class AD( _DNType ):
    aturl = None
    ismultivalued = False
    title = "AD"
    def __init__( self, url, uri, name, component, aturl, ismultivalued, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, component, modified=modified, modifiedBy=modifiedBy, isused=isused )
        self.basetypeurl = aturl
        self.ismultivalued = ismultivalued

class AT( _DNType ):
    basetypeurl = None
    isenum = False
    enumurls = {}
    title = "AT"
    def __init__( self, url, uri, name, component, basetypeurl, isenum, enumurls=None, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, component, isused=isused, modified=modified, modifiedBy=modifiedBy )
        self.basetypeurl = basetypeurl
        self.isenum = isenum
        # this is keyed by the enum URL and contains an ET
        self.enumurls = enumurls or {}

# this is only used inside and AT!
class EnumValue( _DNType ):
    def __init__( self, enum_u, label, value, sameas ):
        self.url = enum_u
        self.name = label
        self.value = value
        self.uri = sameas

class LT( _DNType):
    title = "LT"
    def __init__( self, url, uri, name, component, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, component, isused=isused, modified=modified, modifiedBy=modifiedBy )
    pass

class TypeSystem(object):
    # has a definition of a concrete point-in-time type system. i.e. in a single local config doesn't natter if it's a stream or baseline
    ots = {} # these are keyed by the type URL
    ads = {} # these are keyed by the type URL
    ats = {} # these are keyed by the type URL
    lts = {} # these are keyed by the type URL
    config_u = None
    config_name = None

    def __init__( self, config_name, config_u ):
        logger.debug( f"Creating typesystem for {config_u=}" )
        self.config_u = config_u
        self.config_name = config_name
        self.ots = {}
        self.ads = {}
        self.ats = {}
        self.lts = {}

    def __repr__( self ):
        members = []
#        for o in list(self.ots.items())+list(self.ads.items())+list(self.ats.items())+list(self.lts.items()):
        merged = self.ots|self.ads|self.ats|self.lts
        for o in [v for k,v in merged.items()]:
            members.append( o.__repr__() )
        return "\n".join(members)

    def load_ot( self, serverconnection, url, iscacheable=True, isused=False ):
        if url in self.ots:
#            raise Exception( f"OT definition for {url} already present!" )
            print( f"OT definition for {url} already present!" )
            return
        # get the URI and process all the attributes
        content_x = serverconnection.execute_get_xml( url, params={'oslc_config.context':serverconnection.local_config},headers={'Configuration-Context': None},  cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
        label = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
#        print( f"{label=}" )
        ot_sameas = rdfxml.xmlrdf_get_resource_uri( content_x,'.//owl:sameAs' )
#        print( f"{ot_sameas=}" )
        atts_x = rdfxml.xml_find_elements(content_x, './/dng_types:hasAttribute')
        atturls = []
        for att_x in atts_x:
#            print( f"att_x={ET.tostring(att_x)=}" )
            att_u = rdfxml.xmlrdf_get_resource_uri( att_x, exceptionifnotfound=True )
#            print( f"{att_u=}" )
            if not serverconnection.app.is_server_uri( att_u ):
                # ignore system attributes
                continue
            atturls.append( att_u )
            self.load_ad( serverconnection, att_u, None, isused=isused )
        self.ots[url] = OT( url, ot_sameas, label, component, atturls, modified=modified, modifiedBy=modifiedBy, isused=isused)

    def load_ad( self, serverconnection, url, iscacheable=True, isused=False ):
        if url in self.ads:
#            print( f"AD definition for {url} already present!" )
            return
        # get the URI and process all the attributes
        content_x = serverconnection.execute_get_xml( url, params={'oslc_config.context':serverconnection.local_config},headers={'Configuration-Context': None}, cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
        label = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
#        print( f"{label=}" )
        sameas = rdfxml.xmlrdf_get_resource_uri( content_x,'.//owl:sameAs' )
#        print( f"{sameas=}" )

        # these two are for an enumeration
        ismultivalued = rdfxml.xmlrdf_get_resource_text( content_x, './/dng_types:multiValued' ) or False
        aturl = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dng_types:range' )

        self.load_at( serverconnection, aturl, isused=isused )

        self.ads[url] = AD( url, sameas, aturl, label, component, ismultivalued, modified=modified, modifiedBy=modifiedBy, isused=isused )

    def load_at( self, serverconnection, url, iscacheable=True, isused=False ):
        if url in self.ats:
#            print( f"AT definition for {url} already present!" )
            return
        if not serverconnection.app.is_server_uri( url ):
            print( f"AT Ignoring non-server URL {url}" )
            return
        content_x = serverconnection.execute_get_xml( url, params={'oslc_config.context':serverconnection.local_config},headers={'Configuration-Context': None}, cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
        label = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
#        print( f"{label=}" )
        basetype_u = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dng_types:valueType', exceptionifnotfound=True )
#        print( f"{basetype_u=}" )
        sameas = rdfxml.xmlrdf_get_resource_uri( content_x,'.//owl:sameAs' )
#        print( f"{sameas=}" )
        # get the rdf:Description - these are the enum names/value/uri
#          <rdf:Description rdf:about="http://ibm.com/v0">
#               <rdfs:label>value0</rdfs:label>
#               <rdf:value>0</rdf:value>
#         </rdf:Description>
        enums_x = rdfxml.xml_find_elements(content_x, './/rdf:Description')
        enumurls = {}
        isenum = False
        if enums_x:
            # load enum values!
            isenum = True
            for enum_x in enums_x:
#                print( f"enum_x={ET.tostring(enum_x)=}" )
                enum_u = rdfxml.xmlrdf_get_resource_uri( enum_x, exceptionifnotfound=True )
#                print( f"{enum_u=}" )
                label = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
                value = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdf:value', exceptionifnotfound=True )
                # this enum value doesn't have a URI if its rdf:about is a server-local URL
                if serverconnection.app.is_server_uri( enum_u ):
                    # if the enum url is a server URL, then it's not an RDF URI, which means there isn't a uri
                    esameas = None
                else:
                    # else it is an RDF URI, same as the enum url
                    esameas = enum_u
                enumurls[ enum_u ] = EnumValue( enum_u, label, value, esameas )

        self.ats[url] = AT( url, sameas, label, component, basetype_u, isenum, enumurls, modified=modified, modifiedBy=modifiedBy, isused=isused )

    def load_lt( self, serverconnection, url, iscacheable=True, isused=False ):
        if url in self.lts:
#            print( f"LT definition for {url} already present!" )
            return
        content_x = serverconnection.execute_get_xml( url, params={'oslc_config.context':serverconnection.local_config},headers={'Configuration-Context': None}, cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
        label = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
#        print( f"{label=}" )
        sameas = rdfxml.xmlrdf_get_resource_uri( content_x,'.//owl:sameAs' )
#        print( f"{sameas=}" )

        self.lts[url] = LT( url, sameas, label, component, modified=modified, modifiedBy=modifiedBy, isused=isused )

    def checkinternalconsistency():
        # could check for e.g. no repeated URIs, no repeated names
        pass

    def checkagainstothertypesystem( self, theothertypesystem, verbose=False ):
        # fudge to allowed deferred evaluation of an f-string - derived from https://stackoverflow.com/a/49884004
        def fstr(template):
            import inspect
            frame = inspect.currentframe().f_back.f_back
            try:
#                fstr = 'f"""' + fstr + '"""'
                return eval('f"""' + template + '"""', frame.f_globals, frame.f_locals)
            finally:
                del frame            
            return "UNKNOWN"
        def expand( error ):
            errorcode,template = error
            return ( errorcode, fstr( template ) )

        # compares self (A) with other (B)
        results = []
        # checks e.g. that types with the same UUID have the same URI

        # Artifact Types
        aots = self.ots.keys()
        bots = theothertypesystem.ots.keys()
        for aurl in aots:
            # for all the types in A
            print( f"{aurl=}" )
            if aurl in bots:
                # if the type is also in B, we can compare
                print( f"matched {aurl=}" )
                a = self.ots[aurl]
                b = theothertypesystem.ots[aurl]
                # check URI is consistent
                print( f"{a.uri=} {b.uri=}" )
                print( f"{a=}\n{b=}" )
                # check for changed name
                if a.name != b.name:
                    results.append( expand( OT_RENAMED ) )
                # check for dropped URI
                if a.uri and not b.uri:
                    # b doesn't have a URI
                    results.append( expand( OT_URI_REMOVED ) )
                if a.uri and b.uri and a.uri != b.uri:
                    results.append( expand( OT_URI_CHANGED ) )
#                if not a.uri and b.uri:
                # check all attribs present in both A and B with no differences
                inanotb = set(a.attriburls) - set(b.attriburls)
                inbnota = set(b.attriburls) - set(a.attriburls)
                inaandb = set(a.attriburls) & set(b.attriburls)
                if inanotb:
                    results.append( expand( OT_AD_REMOVED ) )
                if inbnota:
                    results.append( expand( OT_AD_ADDED ) )
                # confirm the attribs in both are identical - this will be completed during at checking
#                for at in sorted(inaandb,key=lambda a: a.ats[a].name ):

        # Attribute Definitions
        aads = self.ads.keys()
        bads = theothertypesystem.ads.keys()
        for aurl in aads:
            # for all the types in A
            print( f"{aurl=}" )
            if aurl in bads:
                # if the type is also in B, we can compare
                print( f"matched {aurl=}" )
                a = self.ads[aurl]
                b = theothertypesystem.ads[aurl]
                # check URI is consistent
                print( f"{a.uri=} {b.uri=}" )
                print( f"{a=}\n{b=}" )
                # check for changed name
                if a.name != b.name:
                    results.append( expand( AD_RENAMED ) )
                # check for dropped URI
                if a.uri and not b.uri:
                    # b doesn't have a URI
                    results.append( expand( AD_URI_REMOVED ) )
                if a.uri and b.uri and a.uri != b.uri:
                    results.append( expand( AD_URI_CHANGED ) )
                if a.ismultivalued and not b.ismultivalued:
                    results.append( expand( AD_WAS_MULTIVALUED ) )
                if not a.ismultivalued and b.ismultivalued:
                    results.append( expand( AD_BECAME_MULTIVALUED ) )
                if a.basetypeurl != b.basetypeurl:
                    results.append( expand( AD_BASE_TYPE_URL_CHANGED ) )

        # Attribute Types
        aats = self.ats.keys()
        bats = theothertypesystem.ats.keys()
        for aurl in aats:
            # for all the types in A
            print( f"{aurl=}" )
            if aurl in bats:
                # if the type is also in B, we can compare
                print( f"matched {aurl=}" )
                a = self.ats[aurl]
                b = theothertypesystem.ats[aurl]
                # check URI is consistent
                print( f"{a.uri=} {b.uri=}" )
                print( f"{a=}\n{b=}" )
                # check for changed name
                if a.name != b.name:
                    results.append( expand( AT_RENAMED ) )
                # check for dropped URI
                if a.uri and not b.uri:
                    # b doesn't have a URI
                    results.append( expand( AT_URI_REMOVED ) )
                if a.uri and b.uri and a.uri != b.uri:
                    results.append( expand( AT_URI_CHANGED ) )
                if a.isenum and not b.isenum:
                    results.append( expand( AT_ENUM_ADDED ) )
                if not a.isenum and b.isenum:
                    results.append( expand( AT_ENUM_REMOVED ) )
                if a.isenum and b.isenum:
                    # compare the enum values
#                    self.ats[url] = AT( url, sameas, label, component, basetype_u, isenum, enumurls, modified=modified, modifiedBy=modifiedBy, isused=isused )
#                    enumurls[ enum_u ] = {"name": label, "value": value, "sameas": sameas}
                    eas = a.enumurls
                    ebs = b.enumurls
                    einanotbs = set(eas) - set(ebs)
                    einbnotas = set(ebs) - set(eas)
                    einandbs  = set(eas) & set( ebs )
                    for e in einanotbs:
                        results.append( expand( AT_ENUMVALUE_REMOVED ) )
                    for e in einbnotas:
                        results.append( expand( AT_ENUMVALUE_ADDED ) )
                    for e in einandbs: # these are URLs
                        print( f"{e=}" )
                        print( f"{a.enumurls=}" )
                        # compare the nums for same ename/value/uri
                        if a.enumurls[e].name != b.enumurls[e].name:
                            results.append( expand( AT_ENUMVALUE_RENAMED ) )
                        if a.enumurls[e].uri != b.enumurls[e].uri:
                            results.append( expand( AT_ENUMVALUE_URI_CHANGED ) )
                        if a.enumurls[e].value != b.enumurls[e].value:
                            results.append( expand( AT_ENUMVALUE_VALUE_CHANGED ) )

#        print( f"{'\n'.join(results)}" )
        print( f"{repr(results)=}" )
        return results

class ComponentTypeSytem( object ):
    # has a local config tree of TypeSystem objects
    localconfigtree = None
    pass

class GCTypeSystem( object ):
    gcconfigtree = None
    # has  gc tree of ComponentTypeSystems
    pass


