##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# typesystem support for typesdiff
#

import collections
import datetime
import inspect
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

######################################################################################################
# internal checks - within a configuration (baseline or stream)

OT_URI_MISSING              = ( CHECKWARNING, "Artitact Type '{a.label}' ({a.name}) does not have a RDF URI" )
OT_DUPLICATE_URI            = ( CHECKERROR, "OT_DUPLICATE_URI" )
OT_DUPLICATE_NAME           = ( CHECKERROR, "OT_DUPLICATE_NAME" )

AD_URI_MISSING              = ( CHECKWARNING, "Attribute Definition '{a.label}' ({a.name}) does not have a RDF URI" )
AD_UNUSED                   = ( CHECKINFO,  "Attribute Definition '{a.label}' ({a.name}) isn't used in any Artifact Type" )
AD_DUPLICATE_URI            = ( CHECKERROR, "AD_DUPLICATE_URI" )
AD_DUPLICATE_NAME           = ( CHECKERROR, "AD_DUPLICATE_NAME" )
AD_BASE_TYPE_CHECK_NEEDED   = ( CHECKERROR, "AD_BASE_TYPE_CHECK_NEEDED" )

AT_UNUSED                   = ( CHECKINFO,  "Attribute Type '{a.label}' ({a.name}) isn't used in any Attribute Definition" )
AT_URI_MISSING              = ( CHECKWARNING, "Attribute Type '{a.label}' ({a.url}) does not have a RDF URI" )
AT_ENUMVALUE_URI_MISSING    = ( CHECKWARNING, "Enumeration value '{a.label}' ({a.url}) does not have a RDF URI" )
AT_DUPLICATE_URI            = ( CHECKERROR, "AT_DUPLICATE_URI" )
AT_DUPLICATE_NAME           = ( CHECKERROR, "AT_DUPLICATE_NAME" )
AT_ENUMVALUE_DUPLICATE_NAME = ( CHECKERROR, "AT_ENUMVALUE_DUPLICATE_NAME" )
AT_ENUMVALUE_DUPLICATE_URI  = ( CHECKERROR, "AT_ENUMVALUE_DUPLICATE_URI" )
AT_ENUMVALUE_DUPLICATE_VALUE= ( CHECKERROR, "AT_ENUMVALUE_DUPLICATE_VALUE" )

LT_URI_MISSING              = ( CHECKWARNING, "Link Type '{a.label}' ({a.name}) does not have a RDF URI" )
LT_DUPLICATE_URI            = ( CHECKERROR, "LT_DUPLICATE_URI" )
LT_DUPLICATE_NAME           = ( CHECKERROR, "LT_DUPLICATE_NAME" )

######################################################################################################
# evolution checks between configurations, e.g. baseline->baseline, baseline->stream

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

######################################################################################################
# compare with reference checks
OT_NOT_IN_REF               = ( CHECKERROR, "Artifact Type {a.name} not present in reference typesystem!" )
AD_NOT_IN_REF               = ( CHECKERROR, "Attribute Definition {a.name} not present in reference typesystem!" )
AT_NOT_IN_REF               = ( CHECKERROR, "Attribute Type {a.name} not present in reference typesystem!" )
LT_NOT_IN_REF               = ( CHECKERROR, "Link Type {a.name} not present in reference typesystem!" )

######################################################################################################
# inter-stream checks (within a component so type URLs are consistent

OT_URI_INCONSISTENT         = 1
OT_NAME_INCONSISTENT        = 1
OT_PRESENCE_INCONSISTENT    = 1

AD_URI_INCONSISTENT    = 1
AD_NAME_INCONSISTENT    = 1
AD_PRESENCE_INCONSISTENT    = 1

AT_URI_INCONSISTENT    = 1
AT_NAME_INCONSISTENT                    = 1
AT_PRESENCE_INCONSISTENT                = 1

AT_ENUMVALUE_URI_INSISTENT              = 1
AT_ENUMVALUE_NAME_INCONSISTENT          = 1
AT_ENUMVALUE_PRESENCE_INCONSISTENT      = 1


######################################################################################################
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
    def __init__( self, url, uri, name, label, isused=False, modified=None, modifiedBy=None ):
        self.url = url
        self.uri = uri
        self.name = name
        self.isused = isused
        self.modified = modified
        self.modifiedBy = modifiedBy
        self.label = label
    def __repr__( self ):
        return f"{vars(self)}"

class OT( _DNType ):
    attriburls = []
    title = "OT"
    def __init__( self, url, uri, name, label, attriburls, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, label, modified=modified, modifiedBy=modifiedBy, isused=isused )
        self.attriburls = attriburls

class AD( _DNType ):
    aturl = None
    ismultivalued = False
    title = "AD"
    def __init__( self, url, uri, name, label, aturl, ismultivalued, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, label, modified=modified, modifiedBy=modifiedBy, isused=isused )
        self.basetypeurl = aturl
        self.ismultivalued = ismultivalued

class AT( _DNType ):
    basetypeurl = None
    isenum = False
    enumvalues = {}
    title = "AT"
    def __init__( self, url, uri, name, label, basetypeurl, isenum, enumvalues=None, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, label, isused=isused, modified=modified, modifiedBy=modifiedBy )
        self.basetypeurl = basetypeurl
        self.isenum = isenum
        # this is keyed by the enum URL and contains an ET
        self.enumvalues = enumvalues or {}

# this is only used inside and AT!
class EnumValue( _DNType ):
    def __init__( self, enum_u, label, value, sameas ):
        self.url = enum_u
        self.name = label
        self.value = value
        self.uri = sameas

class LT( _DNType):
    title = "LT"
    def __init__( self, url, uri, name, label, modified=None, modifiedBy=None, isused=False ):
        super().__init__( url, uri, name, label, isused=isused, modified=modified, modifiedBy=modifiedBy )
    pass

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
    
def expand( errorname ):
    if type( errorname ) == str:
        error = globals()[ errorname ]
    else:
        raise Exception( f"Unconverted '{errorname}'" )
#        error = errorname
    errorcode,template = error
    return ( errorcode, errorname, fstr( template ) )

class TypeSystem(object):
    # has a definition of a concrete point-in-time type system. i.e. in a single local config (e.g. stream or baseline or changeset)
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
        content_x = serverconnection.execute_get_xml( url, params={'vvc.configuration':serverconnection.local_config},headers={'Configuration-Context': None},  cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
#        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
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
                # ignore system attributes - these don't start with the serverl external URI
                continue
            atturls.append( att_u )
            self.load_ad( serverconnection, att_u, iscacheable=iscacheable, isused=isused )
        self.ots[url] = OT( url, ot_sameas, url, label, atturls, modified=modified, modifiedBy=modifiedBy, isused=isused)

    def load_ad( self, serverconnection, url, iscacheable=True, isused=False ):
        if url in self.ads:
#            print( f"AD definition for {url} already present!" )
            return
        # get the URI and process all the attributes
        content_x = serverconnection.execute_get_xml( url, params={'vvc.configuration':serverconnection.local_config},headers={'Configuration-Context': None}, cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
#        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
        label = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
#        print( f"{label=}" )
        sameas = rdfxml.xmlrdf_get_resource_uri( content_x,'.//owl:sameAs' )
#        print( f"{sameas=}" )

        # these two are for an enumeration
        ismultivalued = rdfxml.xmlrdf_get_resource_text( content_x, './/dng_types:multiValued' ) or False
        aturl = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dng_types:range' )

        self.load_at( serverconnection, aturl, isused=isused, iscacheable=iscacheable )

        self.ads[url] = AD( url, sameas, aturl, label, aturl, ismultivalued, modified=modified, modifiedBy=modifiedBy, isused=isused )

    def load_at( self, serverconnection, url, iscacheable=True, isused=False ):
#        print( f"load_at {url=}" )
        if url in self.ats:
#            print( f"AT definition for {url} already present!" )
            return
        if not serverconnection.app.is_server_uri( url ):
#            print( f"AT Ignoring non-server URL {url}" )
            return
        content_x = serverconnection.execute_get_xml( url, params={'vvc.configuration':serverconnection.local_config},headers={'Configuration-Context': None}, cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
#        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
        label = rdfxml.xmlrdf_get_resource_uri( content_x,'./dng_types:AttributeType/rdfs:label', exceptionifnotfound=True )
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
        enumvalues = {}
        isenum = False
        if enums_x:
            # load enum values!
            isenum = True
            for enum_x in enums_x:
#                print( f"enum_x={ET.tostring(enum_x)=}" )
                enum_u = rdfxml.xmlrdf_get_resource_uri( enum_x, exceptionifnotfound=True )
#                print( f"{enum_u=}" )
                enumlabel = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
                value = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdf:value', exceptionifnotfound=True )
                # this enum value doesn't have a URI if its rdf:about is a server-local URL
                if serverconnection.app.is_server_uri( enum_u ):
                    # if the enum url is a server URL, then it's not an RDF URI, which means there isn't a uri
                    esameas = None
                else:
                    # else it is an RDF URI, same as the enum url
                    esameas = enum_u
                enumvalues[ enum_u ] = EnumValue( enum_u, enumlabel, value, esameas )

        self.ats[url] = AT( url, sameas, url, label, basetype_u, isenum, enumvalues, modified=modified, modifiedBy=modifiedBy, isused=isused )
#        print( f"{self.ats=}" )

    def load_lt( self, serverconnection, url, iscacheable=True, isused=False ):
#        print( f"load_lt {url=}" )
        if url in self.lts:
#            print( f"LT definition for {url} already present!" )
            return
        content_x = serverconnection.execute_get_xml( url, params={'vvc.configuration':serverconnection.local_config},headers={'Configuration-Context': None}, cacheable=iscacheable )
        if content_x is None:
            burp
        modified = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:modified', exceptionifnotfound=True )
        modifiedBy = rdfxml.xmlrdf_get_resource_uri( content_x,'.//dcterms:contributor', exceptionifnotfound=True )
#        component = rdfxml.xmlrdf_get_resource_uri( content_x,'.//oslc_config:component', exceptionifnotfound=True )
        label = rdfxml.xmlrdf_get_resource_uri( content_x,'.//rdfs:label', exceptionifnotfound=True )
#        print( f"{label=}" )
        sameas = rdfxml.xmlrdf_get_resource_uri( content_x,'.//owl:sameAs' )
#        print( f"{sameas=}" )
#    def __init__( self, url, uri, name, label, modified=None, modifiedBy=None, isused=False ):

        self.lts[url] = LT( url, sameas, url, label, modified=modified, modifiedBy=modifiedBy, isused=isused )
#        print( f"{self.lts=}" )

    def checkinternalconsistency( self ):
        '''
        This checks a typesystem for consistency, e.g. no repeated names, no repeated URIs, ...
        Also builds the lookups to find types by uri or name
        '''
        results = []
        # could check for e.g. presence of URIs, no repeated URIs, no repeated names

        # collect all URIs and names - duplicates will be detected when checking an individual type
        self.uris = collections.Counter()
        self.names = collections.Counter()
        self.otnames = {}
        self.adnames = {}
        self.atnames = {}
        self.ltnames = {}
        for a in self.ots:
            self.names.update(self.ots[a].name)
            if self.ots[a].uri:
                self.uris.update(self.ots[a].uri)
                
        for a in self.ads:
            self.names.update(self.ads[a].name)
            if self.ads[a].uri:
                uself.ris.update(self.ads[a].uri)
                
        for a in self.ats:
            self.names.update(self.ats[a].name)
            if self.ats[a].uri:
                self.uris.update(self.ats[a].uri)
            # collect URIs from enums
            for ae, aev in self.ats[a].enumvalues.items():
                print( f"{ae=} {aev=}" )
                if aev.uri:
                    self.uris.update( aev.uri )
                    
        for a in self.lts:
            self.names.update(self.lts[a].label)
            if self.lts[a].uri:
                self.uris.update(self.lts[a].uri)
                
        # start by checking OTs
        for aurl in self.ots.keys():
            a = self.ots[aurl]
#            print( f"OT {aurl=}" )
            if not a.uri:
                results.append( expand( "OT_URI_MISSING" ) )
            else:
                if self.uris[a.uri]>1:
                    results.append( expand( "OT_DUPLICATE_URI" ) )
            if self.names[a.name]>1:
                results.append( expand( "OT_DUPLICATE_NAME" ) )

        # Attribute Definitions
        for aurl in self.ads.keys():
            a = self.ads[aurl]
            # for all the types in A
#            print( f"AD {aurl=}" )
            if not a.isused:
                results.append( expand( "AD_UNUSED" ) )
            if not a.uri:
                results.append( expand( "AD_URI_MISSING" ) )
            else:
                if self.uris[a.uri]>1:
                    results.append( expand( "AD_DUPLICATE_URI" ) )
            if self.names[a.name]>1:
                results.append( expand( "AD_DUPLICATE_NAME" ) )
                
        # Attribute Types
        for aurl in self.ats.keys():
            a = self.ats[aurl]
            # for all the types in A
#            print( f"AT {a=} {aurl=}" )
            if not a.isused:
                results.append( expand( "AT_UNUSED" ) )
            if not a.uri:
                results.append( expand( "AT_URI_MISSING" ) )
            else:
                if self.uris[a.uri]>1:
                    results.append( expand( "AT_DUPLICATE_URI" ) )
            if self.names[a.name]>1:
                results.append( expand( "AT_DUPLICATE_NAME" ) )

            # collect enum URIs, names, values so we can check for duplicates!
            enumuris = collections.Counter()
            enumnames = collections.Counter()
            enumvalues = collections.Counter()
            for ae, aev in self.ats[aurl].enumvalues.items():
                if aev.uri:
                    enumuris.update( aev.uri )
                enumnames.update( aev.name )
                enumvalues.update( aev.value )

            # check the enums
            for ae, aev in self.ats[aurl].enumvalues.items():
                if not aev.uri:
                    results.append( "AT_ENUMVALUE_NO_URI" )
                else:
                    if enumuris[ aev.uri ]>1:
                        results.append( "AT_ENUMVALUE_DUPLICATE_URI" )
                if enumnames[ aev.name ]>1:
                    results.append( "AT_ENUMVALUE_DUPLICATE_NAME" )
                if enumvalues[ aev.value ]>1:
                    results.append( "AT_ENUMVALUE_DUPLICATE_VALUE" )
            
        # Link Types
        for aurl in self.lts.keys():
            a = self.lts[aurl]
            # for all the types in A
#            print( f"LT {a=} {aurl=}" )
            if not a.uri:
                results.append( expand( "LT_URI_MISSING" ) )
            else:
                if self.uris[a.uri]>1:
                    results.append( expand( "LT_DUPLICATE_URI" ) )
            if self.names[a.name]>1:
                results.append( expand( "LT_DUPLICATE_NAME" ) )
        
#        print( f"{repr(results)=}" )
        for result in results:
            print( f"{result=}" )
        return results

    def checkagainstothertypesystem( self, theothertypesystem, verbose=False, comparewithref=False, allowmoreina=True ):
        '''
        This comparison is based around unique URLs for types, which are/can be common to both typesystems
        i.e. this check is within a component
        '''
#        print( f"CAOTS {self=} {theothertypesystem=}" )
        # compares self (A) with other (B)
        results = []
        # checks e.g. that types with the same UUID have the same URI

        # Artifact Types
        for aurl in self.ots.keys():
            # for all the types in A
#            print( f"{aurl=}" )
            # try to find the a OT in b
            if comparewithref:
                # try to find the b type using a's URI or name
                burl = self.matchtype( self.ots(aurl), theothertypesystem.ots )
            else:
                # simple lookup of aurl in bots
                burl = theothertypesystem.ots.get( aurl )
            if burl:
                # if the type is also in B, we can compare
#                print( f"matched {aurl=}" )
                a = self.ots[aurl]
                b = theothertypesystem.ots[burl]
                # check URI is consistent
#                print( f"{a.uri=} {b.uri=}" )
#                print( f"{a=}\n{b=}" )
                # check for changed name
                if a.name != b.name:
                    results.append( expand( "OT_RENAMED" ) )
                # check for dropped URI
                if a.uri and not b.uri:
                    # b doesn't have a URI
                    results.append( expand( "OT_URI_REMOVED" ) )
                if a.uri and b.uri and a.uri != b.uri:
                    results.append( expand( "OT_URI_CHANGED" ) )
#                if not a.uri and b.uri:
                # check all attribs present in both A and B with no differences
                inanotb = set(a.attriburls) - set(b.attriburls)
                inbnota = set(b.attriburls) - set(a.attriburls)
                inaandb = set(a.attriburls) & set(b.attriburls)
                if inanotb:
                    results.append( expand( "OT_AD_REMOVED" ) )
                if inbnota:
                    results.append( expand( "OT_AD_ADDED" ) )
                # confirm the attribs in both are identical - this will be completed during at checking
#                for at in sorted(inaandb,key=lambda a: a.ats[a].name ):
            else:
                if comparewithref and not allowmoreina:
                    results.append( expand( "OT_NOT_IN_REF" ) )
                    
        # Attribute Definitions
        for aurl in self.ads.keys():
            # for all the types in A
#            print( f"{aurl=}" )
            if comparewithref:
                # try to find the b type using a's URI or name
                burl = self.matchtype( self.ads(aurl), theothertypesystem.ads )
            else:
                # simple lookup of aurl in bots
                burl = theothertypesystem.ads.get( aurl )
            if burl:
                # if the type is also in B, we can compare
#                print( f"matched {aurl=}" )
                a = self.ads[aurl]
                b = theothertypesystem.ads[aurl]
                # check URI is consistent
#                print( f"{a.uri=} {b.uri=}" )
#                print( f"{a=}\n{b=}" )
                # check for changed name
                if a.name != b.name:
                    results.append( expand( "AD_RENAMED" ) )
                # check for dropped URI
                if a.uri and not b.uri:
                    # b doesn't have a URI
                    results.append( expand( "AD_URI_REMOVED" ) )
                if a.uri and b.uri and a.uri != b.uri:
                    results.append( expand( "AD_URI_CHANGED" ) )
                if a.ismultivalued and not b.ismultivalued:
                    results.append( expand( "AD_WAS_MULTIVALUED" ) )
                if not a.ismultivalued and b.ismultivalued:
                    results.append( expand( "AD_BECAME_MULTIVALUED" ) )
                if not comparewithref:
                    if a.basetypeurl != b.basetypeurl:
                        results.append( expand( "AD_BASE_TYPE_URL_CHANGED" ) )
                else:
                    # how to compare the base types?
                    results.append( expand( "AD_BASE_TYPE_CHECK_NEEDED" ) )
            else:
                if comparewithref and not allowmoreina:
                    results.append( expand( "AD_NOT_IN_REF" ) )

        # Attribute Types
        for aurl in self.ats.keys():
            # for all the types in A
#            print( f"{aurl=}" )
            if comparewithref:
                # try to find the b type using a's URI or name
                burl = self.matchtype( self.ats(aurl), theothertypesystem.ats )
            else:
                # simple lookup of aurl in bots
                burl = theothertypesystem.ats.get( aurl )
            if burl:
                # if the type is also in B, we can compare
#                print( f"matched {aurl=}" )
                a = self.ats[aurl]
                b = theothertypesystem.ats[burl]
                # check URI is consistent
#                print( f"{a.uri=} {b.uri=}" )
#                print( f"{a=}\n{b=}" )
                # check for changed name
                if a.name != b.name:
                    results.append( expand( "AT_RENAMED" ) )
                # check for dropped URI
                if a.uri and not b.uri:
                    # b doesn't have a URI
                    results.append( expand( "AT_URI_REMOVED" ) )
                if not a.uri and b.uri:
                    # a doesn't have a URI
                    results.append( expand( "AT_URI_ADDED" ) )
                if a.uri and b.uri and a.uri != b.uri:
                    results.append( expand( "AT_URI_CHANGED" ) )
                if a.isenum and not b.isenum:
                    results.append( expand( "AT_ENUM_ADDED" ) )
                if not a.isenum and b.isenum:
                    results.append( expand( "AT_ENUM_REMOVED" ) )
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
                        results.append( expand( "AT_ENUMVALUE_REMOVED" ) )
                    for e in einbnotas:
                        results.append( expand( "AT_ENUMVALUE_ADDED" ) )
                    for e in einandbs: # these are URLs
#                        print( f"{e=}" )
#                        print( f"{a.enumurls=}" )
                        # compare the nums for same ename/value/uri
                        if a.enumurls[e].name != b.enumurls[e].name:
                            results.append( expand( "AT_ENUMVALUE_RENAMED" ) )
                        if a.enumurls[e].uri != b.enumurls[e].uri:
                            results.append( expand( "AT_ENUMVALUE_URI_CHANGED" ) )
                        if a.enumurls[e].value != b.enumurls[e].value:
                            results.append( expand( "AT_ENUMVALUE_VALUE_CHANGED" ) )
            else:
                if comparewithref and not allowmoreina:
                    results.append( expand( "AT_NOT_IN_REF" ) )

        # Link Types
        for aurl in self.lts.keys():
            # for all the types in A
#            print( f"{aurl=}" )
            if comparewithref:
                # try to find the b type using a's URI or name
                burl = self.matchtype( self.lts(aurl), theothertypesystem.lts )
            else:
                # simple lookup of aurl in b
                burl = theothertypesystem.lts.get( aurl )
            if burl:
                # if the type is also in B, we can compare
#                print( f"matched {aurl=}" )
                a = self.lts[aurl]
                b = theothertypesystem.lts[burl]
                # check URI is consistent
#                print( f"{a.uri=} {b.uri=}" )
#                print( f"{a=}\n{b=}" )
                # check for changed name
                if a.name != b.name:
                    results.append( expand( "LT_RENAMED" ) )
                # check for dropped URI
                if a.uri and not b.uri:
                    # b doesn't have a URI
                    results.append( expand( "LT_URI_REMOVED" ) )
                if not a.uri and b.uri:
                    # a doesn't have a URI
                    results.append( expand( "LT_URI_ADDED" ) )
                if a.uri and b.uri and a.uri != b.uri:
                    results.append( expand( "LT_URI_CHANGED" ) )
            else:
                if comparewithref and not allowmoreina:
                    results.append( expand( "LT_NOT_IN_REF" ) )


#        print( f"{'\n'.join(results)}" )
        for result in results:
            print( f"{result=}" )
        return results

class ComponentTypeSytem( object ):
    # has a local config tree of TypeSystem objects
    localconfigtree = None
    pass

class GCTypeSystem( object ):
    gcconfigtree = None
    # has  gc tree of ComponentTypeSystems
    pass


