##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import logging
import re

import lark
import lxml.etree as ET

from . import rdfxml

logger = logging.getLogger(__name__)

#
# This enhanced OSLC Query grammar supports "||", "&&" and bracketed evaluation
# This is based on the EBNF in OSLC Query 3.0 standard https://docs.oasis-open-projects.org/oslc-op/query/v3.0/os/oslc-query.html
# Differences/enhancements from the OSLC 3.0 definition:
#  You can combine compound_terms using && and || - note when using these the compound_term MUST be in ( ) (which also makes reading the expression easier)
#  also accepts just a single compound_term with no ( ) needed (i.e. this is basically the vanilla OSLC Query 3.0 syntax)
#  In order to allow the user to use friendly names for attributes and enumeration values, there is a new terminal valueidentifier - these are resolved in the context of the identifier (attribute) in the LHS of the term - a name with a space must be surrounded by ' '
#  You are of course free to use <https://...> URIs for identifiers and value identifiers. Good luck with that!
#  identifiers and valueidentifiers must start with [a-zA-Z0-9_]
#  Identifiers can't use backslash escapes
#  langtag can be used but will be ignored
#  ^^ type-specifiers can be used and will be passed on into the query, but not checked/enforced
#  In order to allow the user to use names with spaces (e.g. an enumeration value 'In Process'), put ' ' around them
#  Won't resolve identifiers or valueidentifiers if they include a : (can't tell the difference between that usage and e.g. dcterms:identifier)
#  DNG 6.0.6.1 doesn't support the Query 3.0 PrefixedName on RHS of a term as a value, so they are all converted to <https://...> references
#  For DNG You can refer to a foldername using e.g. $"folder name" - this gets converted to the URI of the folder in <> NOT EXTENSIVELY TESTED!
#  You can refer to a user name using e.g. @"user name" - this gets converted to the server-specific URI of the user

_core_oslc_grammar = r"""
?compound_term      : simple_term
                    | simple_term boolean_op compound_term                    -> do_oslcand

boolean_op          : "and"

?simple_term        : term
                    | scoped_term

?scoped_term        : identifier_wc "{" compound_term "}"

term                : identifier_wc comparison_op value
                    | identifier_wc inop in_val

inop                : "in"

in_val              : "[" invalue ("," invalue)* "]"

invalue             : value
                    | "*" unsignedinteger -> reqid_to_module_uris

?identifier_wc      : identifier | WILDCARD

identifier          : dottedname
                    | prefixedname
                    | simpleidentifier


dottedname          : ( URI_REF_ESC | NAME | "'" SPACYNAME "'" ) "." ( NAME | "'" SPACYNAME "'" )

prefixedname        : ( URI_REF_ESC | NAME ) ":" NAME

simpleidentifier    : ( NAME  | "'" SPACYNAME "'" )

NAME                : /[a-zA-Z0-9_][a-zA-Z0-9_-]*/

value              : URI_REF_ESC
                    | boolean
                    | decimal
                    | typedliteralstring
                    | literalstring
                    | valueidentifier
                    | urioffoldername
                    | uriofuser
                    | uriofmodule
                    | uriofconfig
                    | dottedname

valueidentifier     : ( ( URI_REF_ESC | NAME | "'" SPACYNAME "'" ) ":" )? NAME
                    | "'" SPACYNAME "'"
                    | "~" unsignedinteger -> reqid_to_core_uri

unsignedinteger     : /[1-9][0-9]*/

URI_REF_ESC         : /<https?:.*?>/

SPACYNAME           : /[ a-zA-Z0-9_][^']*/

urioffoldername     : "$" string_esc

uriofconfig         : "#" string_esc

uriofuser           : "@" string_esc

uriofmodule         : "^" string_esc

typedliteralstring  : string_esc (langtag | ("^^" prefixedname))

literalstring       : string_esc

boolean             : TRUE | FALSE

WILDCARD            : "*"

comparison_op       : EQ
                    | NE
                    | LT
                    | GT
                    | LE
                    | GE



EQ: "="
NE: "!="
LT: "<"
LE: "<="
GE: ">="
GT: ">"

TRUE            : "true"
FALSE           : "false"

decimal         : SIGNED_NUMBER
newstring_esc      : "'" /[^']+/ "'"
string_esc      : ESCAPED_STRING

langtag         : /@[a-z][a-z0-9_]*/

%import common.ESCAPED_STRING
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
"""

_enhanced_oslc3_query_grammar = """
where_expression    : compound_term
                    | logicalor_term

?logicalor_term     : logicalcompound_term
                    | logicalcompound_term ( "||" logicalcompound_term )+             -> do_logicalor

?logicalcompound_term    : "(" ( compound_term | logicalor_term ) ")"
                    | "(" ( compound_term | logicalor_term ) ")" ("&&" logicalcompound_term)+                  -> do_logicaland

""" + _core_oslc_grammar

# The basic grammer removes logicalorterm and logicalandterm
_basic_oslc3_query_grammar = """
where_expression    : compound_term

""" + _core_oslc_grammar

# This class will turn a parsed query into a list of steps each (identifier,operation,value) - corresponding to an OSLC query compound_term
# and these lists are combined with the enhanced operations for logicalor and logicaland
# the idea is that results from OSLC query compound_terms are pushed on a stack, and the the logicalor and logicaland take the top
# two entries in the stack and push one result back on the stack.

# The stack will end up with one entry - the results - this is assured by the parsing because it won't generate anything else on a valid enhanced query string

# the transformer does things like turning identifiers (which are human-friendly names) into URIs using nameresolver, and
# turning valueidentifier which are friendly enumeration value names into <URI> (this is done in the term() method)
# while doing this it updates the mapping dictionaries so the results
# can use them to turn result URIs back into friendly names

# leafs of the tree are called first, returning results upwards
class _ParseTreeToOSLCQuery(lark.visitors.Transformer):
    def __init__(self,resolverobject):
        super().__init__()
        self.resolverobject = resolverobject
        self.mapping_uri_to_identifer = {}
        self.mapping_identifer_to_uri = {}
        self.mapping_folders = {} # contains both: key name->uri and key uri->name (uris and names never overlap)
        self.mapping_users = {} # contains both: key name->uri and key uri->name (uris and names never overlap)
        self.mapping_modules = {} # contains both: key name->uri and key uri->name (uris and names never overlap)
        self.mapping_projects = {} # contains both: key name->uri and key uri->name (uris and names never overlap)
        self.mapping_configs = {} # contains both: key name->uri and key uri->name (uris and names never overlap)

    def where_expression(self, s):
        logger.debug( f"where_expression {s=}" )
        result = s
        logger.debug( f"where_expression {s=} returning {result=}" )
        return s

    def do_logicalor(self, s):
        if len(s) == 1:
            result = s[0]
        else:
            if isinstance(s[0][0], str):
                res0 = [s[0]]
            else:
                res0 = s[0]

            if isinstance(s[1][0], str):
                res1 = [s[1]]
            else:
                res1 = s[1]
            result = [res0, res1, "logicalor"]
        return result

    def do_logicaland(self, s):
        if len(s) == 1:
            result = s[0]
        else:
            if isinstance(s[0][0], str):
                res0 = [s[0]]
            else:
                res0 = s[0]

            if isinstance(s[1][0], str):
                res1 = [s[1]]
            else:
                res1 = s[1]
            result = [res0, res1, "logicaland"]
        return result

    def compound_term(self,s):
        return s

    def boolean_op(self,s):
        return "and"

    def do_oslcand(self, s):
        if isinstance(s, list):
            if len(s) == 1:
                result = s
            else:
                result = s
        else:
            raise Exception( f"s isn't a list! {s=}" )
        # put the and first, then term1 then term2
        # check if term2 is another and
        if s[2][0]=='and':
            # if the second term of the and is another and, flatten it out
            result = [s[1],s[0],s[2][1], s[2][2]]
        else:
            # otherwise rearrange to be 'and' term1 term2
            result = [s[1],s[0],s[2]]
        return result

    def term(self, s):
        # if RHS (or for in any of the items in RHS list) is a valueidentifier without a prefix, this uses the lhs to resolve the valueidentifier, i.e. as context for attribute value names
        # or if RHS is an untyped literal then LHS is used to apply ^^type:name to it to make it a typedliteral
        # check if first elem is a property identifier, and if so see if value(s) are identifiers if so resolve them in context of the first identifier (e.g. for enum values)
        logger.info( f"Term {type(s)} {s}" )
        identifier, op, value = s
        if s[0] != '*':
            #
            if op == "in":
                # the "value" is actually a list of values, each of which must be resolved if it is an identifier
                logger.info( f"{value=}" )
                if not isinstance(value, list):
                    value = [value]
                resultlist = []
                for val in value:
                    if isinstance(val, str) and not val.startswith('"') and ':' not in val:
                        # this is an valueidentifier - try to resolve it as an enum in the context of identifier
                        if self.resolverobject.resolve_enum_name_to_uri is not None:
                            result = self.resolverobject.resolve_enum_name_to_uri(val,identifier)
                            if result is None:
                                raise Exception(f"List ref '{val}' not resolved in context {identifier}")
                            resultlist.append("<" + result + ">")
                    else:
                        resultlist.append(val)
                    s[2] = resultlist
            else:
                t1 = type(value)
                logger.info( f"t1 {value} {t1=}" )
                if isinstance(value, str) and not value.startswith('"') and not value.startswith("'") and ':' not in value and not re.match(r"\d",value):
                    # this is a valueidentifier - try to resolve it as an enum in the context of identifier
                    if self.resolverobject.resolve_enum_name_to_uri is not None:
                        result = self.resolverobject.resolve_enum_name_to_uri(value, identifier)
                        if result is None:
                            raise Exception(f"Single ref {value} not resolved in context {identifier}")
                        if result.startswith("http:") or result.startswith("https:"):
                            s[2] = "<" + result + ">"
                        else:
                            s[2] = '"'+result+'"'
        logger.info( f"Term returning {s}" )
        return s

    def simpleidentifier(self,s):
        logger.info( f"simpleidentifier {s=}" )
        if len(s) != 1:
            raise Exception( "Bad simpleidentifier" )
        resultname = s[0].value
        # look it up and if necessary store to mapping
        result = self.resolverobject.resolve_property_name_to_uri(resultname)
        if result is None:
            raise Exception("Name resolution for %s failed!" % (resultname))
        else:
            self.mapping_identifer_to_uri[resultname] = result
            self.mapping_uri_to_identifer[result] = resultname
        logger.info( f"simpleidentifier {result=}" )
        return result

    def prefixedname(self,s):
        logger.info( f"prefixedname {s=}" )
        result = s[0]+":"+s[1]
        logger.info( f"prefixedname {result=}" )
        return result

    def dottedname(self,s):
        logger.info( f"dottedname {s=} {s[0]=}" )
        if len(s) != 2:
            raise Exception( "Bad dottedname" )

        # s[0][0] is the shape name
        # s[0][1] is the proprty name
        shapename = s[0].value
        propname = s[1].value
        shapeuri = self.resolverobject.resolve_shape_name_to_uri(shapename)
        result = self.resolverobject.resolve_property_name_to_uri(propname,shapeuri )
        self.mapping_identifer_to_uri[f"{shapename}.{propname}"] = result
        self.mapping_uri_to_identifer[result] = f"{shapename}.{propname}"
        logger.info( f"dottedname {s=} {s[0]=} returns {result}" )
        return result

    def identifier(self, s):
        logger.info( f"Identifier {s=}" )
        if len(s) == 1:
            if type(s[0])==str:
                result = s[0]
            else:
                result = s[0].value
        elif len(s) > 1:
            raise Exception( "Bad identifier" )
        logger.info( f"Identifier returning {result=}" )
        return result

    def urioffoldername(self,s):
        logger.info( f"urioffoldername {s=}" )
        name=s[0].strip('"')
        if self.resolverobject.folder_nametouri_resolver is not None:
            uri = self.resolverobject.folder_nametouri_resolver(name)
            if uri is None:
                raise Exception( "Folder name {name} not found!" )
            self.mapping_folders[name]=uri
            self.mapping_folders[uri]=name
            result = "<"+uri.folderuri+">"
        else:
            raise Exception( "This application doesn't support folder names!" )
        return result

    def uriofuser(self,s):
        logger.info( f"uriofuser {s=}" )
        name=s[0].strip('"')
        if self.resolverobject.user_nametouri_resolver is not None:
            uri = self.resolverobject.user_nametouri_resolver(name)
            if uri is None:
                raise Exception( "User name {name} not found!" )
            self.mapping_users[name]=uri
            self.mapping_users[uri]=name
            result = "<"+uri+">"
        else:
            raise Exception( "This application doesn't support users names!" )
        return result

    def uriofmodule(self,s):
        logger.info( f"uriofmodule {s=}" )
        name=s[0].strip('"')
        if self.resolverobject.resolve_modulename_to_uri is not None:
            uri = self.resolverobject.resolve_modulename_to_uri(name)
            if uri is None:
                raise Exception( f"Module name {name} not found!" )
            logger.info( f"uriofmodule {uri=}" )
            self.mapping_modules[name]=uri
            self.mapping_modules[uri]=name
            result = "<"+uri+">"
        else:
            raise Exception( "This application doesn't support module names!" )
        return result

    def uriofconfig(self,s):
        logger.info( f"uriofconfig {s=}" )
        name=s[0].strip('"')
        if self.resolverobject.resolve_configname_to_uri is not None:
            uri = self.resolverobject.resolve_configname_to_uri(name)
            if uri is None:
                raise Exception( f"Config {name} not found!" )
            logger.info( f"uriofconfig {uri=}" )
            self.mapping_configs[name]=uri
            self.mapping_configs[uri]=name
            result = "<"+uri+">"
        else:
            raise Exception( "This application doesn't support resolving configuration names!" )
        return result

#    def uriofproject(self,s):
#        logger.info( f"uriofproject {s=}" )
#        name=s[0].strip('"')
#        if self.resolverobject.resolve_project_nametouri is not None:
#            uri = self.resolverobject.resolve_project_nametouri(name)
#            if uri is None:
#                raise Exception( f"Project name {name} not found!" )
#            logger.info( f"{uri=}" )
#            self.mapping_projects[name]=uri
#            self.mapping_projects[uri]=name
#            result = "<"+uri+">"
#        else:
#            raise Exception( "This application doesn't support project names!" )
#        return result

    def valueidentifier(self, s):
        logger.info( f"valueidentifier {s=}" )
        if len(s)>2:
            raise Exception( f"s should be no more than two items {s=}" )
        elif len(s)==2:
            # this is a prefix:name - check prefix is in the known prefixes and add it to the list of use prefixes
            resultname = s[0].value+":"+s[1].value
            # for DOORS Next always expand the prefixed name to be an actual URI
            result = "<"+rdfxml.tag_to_uri(resultname)+">"
        else:
            result = s[0].value
        logger.info( f"valueidentifier {s=} returning {result}" )
        return result

    def unsignedinteger(self, s):
        logger.info( f"unsignedinteger {s=}" )
        result = s[0]
        logger.info( f"unsignedinteger {s=} returning {result}" )
        return result

    def reqid_to_core_uri(self, s):
        logger.info( f"reqid_to_core_uri {s=}" )
        if len(s)>2:
            raise Exception( f"s should be no more than two items {s=}" )
        elif len(s)==2:
            # this is a prefix:name - check prefix is in the known prefixes and add it to the list of use prefixes
            resultname = s[0].value+":"+s[1].value
            # for DOORS Next always expand the prefixed name to be an actual URI
            result = "<"+rdfxml.tag_to_uri(resultname)+">"
        else:
            result = s[0].value
        # now look it up - using an OSLC query!
        requri = self.resolverobject.resolve_reqid_to_core_uri( result )
        if requri is None:
            raise Exception( f"ID {result} not found!" )
        result = "<"+requri+">"
        logger.info( f"reqid_to_core_uri {s=} returning {result}" )
        return result

    def reqid_to_module_uris(self, s):
        logger.info( f"reqid_to_module_uris {s=}" )
        if len(s)>2:
            raise Exception( f"s should be no more than two items {s=}" )
        elif len(s)==2:
            # this is a prefix:name - check prefix is in the known prefixes and add it to the list of use prefixes
            resultname = s[0].value+":"+s[1].value
            # for DOORS Next always expand the prefixed name to be an actual URI
            result = "<"+rdfxml.tag_to_uri(resultname)+">"
        else:
            result = s[0].value
        # now look it up - using an OSLC query!
        requris = self.resolverobject.resolve_reqid_to_module_uris( result )
        if requris is None:
            raise Exception( f"ID {result} not found!" )
        result = "<"+">,<".join(requris)+">"
        logger.info( f"reqid_to_module_uris {s=} returning {result}" )
        return result

    def comparison_op(self, s):
        logger.info( f"comparison_op {s=}" )
        return s[0].value

    def value(self, s):
        logger.info( f"value {s=}" )
        result = s[0]
        logger.info( f"value {s=} returning {result}" )
        return result

    def invalue(self, s):
        logger.info( f"invalue {s=}" )
        result = s[0]
        logger.info( f"invalue {s=} returning {result}" )
        return result

    def string_esc(self, s):
        logger.info( f"string_esc {s} returning {s[0].value}" )
#        print( f"{s=}" )
        return s[0].value  # string literals include double quotes in the value

    def typedliteralstring(self, s):
        logger.info( f"typedliteralstring {s}" )
        if s[1]=="xsd:datetime":
            if not re.match(r'"\d\d\d\d-\d\d-\d\d(T\d\d:\d\d:\d\d((\.|,)\d\d\d)?(Z|[+-]\d\d:\d\d)?)?"',s[0]):
                raise Exception( f'Datetime {s[0]} not valid - must be "yyyy-mm-dd[Thh:mm:ss[./,fff]?[Z|+/-hh:mm]]"' )
        result = s[0]+"^^"+s[1]
        logger.info( f"typedliteralstring {s} returning {result}" )
        return result  # string literals include double quotes in the value

    def literalstring(self, s):
        # check for a datetime literal and annotate it with the xsd
        if re.match(r'"\d\d\d\d-\d\d-\d\d(T\d\d:\d\d:\d\d((\.|,)\d\d\d)?(Z|[+-]\d\d:\d\d)?)?"',s[0]):
            result = s[0]
            # this works for DN but not EWM   result = s[0]+"^^xsd:datetime"
        else:
            result = s[0]
        logger.info( f"literalstring {s} {s[0]} returning {result}" )
        return result  # string literals include double quotes in the value

    def boolean(self, s):
        if s[0].value=="true":
            return True
        elif s[0].value=="false":
            return False
        else:
            raise Exception( f"Boolean value must be either true or false - f{s[0].value} isn't allowed" )

    def decimal(self, s):
        logger.info( f"decimal {s=}" )
        # try to convert to int first
        try:
            result = int(s[0].value)
        except ValueError:
            # otherwise try to convert to float
            result = float(s[0].value)
        return result

    def in_val(self, s):
        if len(s) == 1:
            result = s[0]
        else:
            result = s
        return result

    def inop(self, s):
        logger.info( f"inop {s=}" )
        return "in"

    def scoped_term(self, s):
        logger.info( f"scoped_term {s=}" )
        return [s[0], "scope", s[1:]]

# from https://tools.oasis-open.org/version-control/svn/oslc-core/trunk/specs/oslc-core.html#selectiveProperties
# with slight tweaks to implement identifier
# NOTE that for oslc.select NAME can be terminated by { or } to allow for nested properties
_select_grammar  ="""
select_terms    : properties
properties      : property ("," property)*
property        : dottedname | nested_prop | identifier | wildcard 
dottedname      : NAME "." NAME
nested_prop     : (identifier | wildcard) "{" properties "}"
wildcard        : "*"

identifier     : ( ( URI_REF_ESC | NAME | "'" SPACYNAME "'" ) ":" )? NAME
                    | "'" SPACYNAME "'"

URI_REF_ESC     : /<https?:.*>/
NAME            : /[a-zA-Z0-9_][^, {}]*/
SPACYNAME           : /[a-zA-Z0-9_()][^']*/
"""

_orderby_grammar = r"""
sort_terms          : sort_term ("," sort_term)*
sort_term           : scoped_sort_terms | signedterm
signedterm          : SIGN ( dottedname | identifier )
dottedname      : NAME "." NAME
scoped_sort_terms   : identifier "{" sort_terms "}"
identifier          : ( ( URI_REF_ESC | NAME ) ":" )? NAME
URI_REF_ESC         : /<https?:.*>/
NAME                : /[a-zA-Z0-9_]\w*/
SIGN                : ( "+" | "-" | ">" | "<" )
"""

# This class will turn a textual orderby specification into a list of orderby terms

# the transformer does things like turning identifiers (which are human-friendly names) into URIs using nameresolver, and
# turning valueidentifier which are friendly enumeration value names into <URI> (this is done in the term() method)

# leafs of the tree are called first, returning results upwards
class _ParseTreeToOSLCOrderBySelect(lark.visitors.Transformer):
#    def __init__(self, shaperesolver=None, nameresolver=None):
    def __init__(self, resolverobject):
        super().__init__()
        self.mapping_uri_to_identifer = {}
        self.mapping_identifer_to_uri = {}
        self.resolverobject = resolverobject
        self.prefixes = {} # prefixes used (will have to be added to oslc.prefix) - NOTE the key is the uri, the value is the prefix!

    def select_terms(self,s):
        logger.info( f"select_terms {s=} {s[0]=}" )
        return s[0]

    def select_term(self,s):
        logger.info( f"select_term {s=} {s[0]=}" )
        return s

    def nested_prop( self,s):
        logger.info( f"nested_prop {s=} {s[0]=}" )
        result = s[0]+"{"+",".join(s[1])+"}"
        logger.info( f"nested_prop {result=}" )
        return result

    def wildcard(self,s):
        return "*"

    def properties(self,s):
        logger.info( f"properties {s=} {s[0]=}" )
        return s

    def property(self,s):
        logger.info( f"property {s=} {s[0]=}" )
        return s[0]

    def sort_terms(self,s):
        return s

    def sort_term(self,s):
        return s[0]

    def signedterm(self,s):
        logger.info( f"signedterm {s=} {s[0]=}" )
        # mapping to always + or -
        signs = { ">": "+", "<": '-', "+": "+", "-": "-"}
        return signs[s[0]]+s[1]

    def scoped_sort_terms(self,s):
        logger.info( f"scoped_sort_terms {s=} {s[0]=}" )
        return s

    def identifier(self, s):
        logger.info( f"identifier {s=} {s[0]=}" )
        if len(s) == 1:
            resultname = s[0].value
            logger.info( f"{resultname=}" )
        elif len(s) > 1:
            # a prefixed name
            resultname = ":".join([s[0].value, s[1].value])
            if s[0].value in rdfxml.RDF_DEFAULT_PREFIX:
                self.prefixes[rdfxml.RDF_DEFAULT_PREFIX[s[0].value]]=s[0].value
                logger.info( f"Added prefix {s[0].value=}" )
            else:
                raise Exception( f"Prefix in orderby '{s[0].value}' not found!" )
        # look it up and if necessary store to mapping
        if ":" not in resultname:
            logger.info( "storing {resultname=}" )
            if self.resolverobject.resolve_property_name_to_uri is not None:
                result1 = self.resolverobject.resolve_property_name_to_uri(resultname)
                if result1 is None:
                    raise Exception("Name resolution for %s failed!" % (resultname))
                else:
                    self.mapping_identifer_to_uri[resultname] = result1
                    self.mapping_uri_to_identifer[result1] = resultname
                result = rdfxml.uri_to_prefixed_tag(result1, uri_to_prefix_map=self.prefixes)

            else:
                raise Exception( f"Cannot resolve {resultname} - no name resolver provided! " )
        else:
            # a prefixed name is assumed to be usable directly (the prefix has been added to prefixes)
            prefix = resultname.split( ":",1 )[0]
            self.prefixes[rdfxml.RDF_DEFAULT_PREFIX[prefix]] = prefix
            logger.info( f"Added prefix {prefix=}" )
            result = resultname
        logger.info( f"identifier1 {result=}" )
        return result

    def dottedname(self,s):
        logger.info( f"dottedname {s=} {s[0]=}" )
        if len(s) != 2:
            raise Exception( "Bad dottedname" )

        # s[0][0] is the shape name
        # s[0][1] is the proprty name
        shapename = s[0].value
        propname = s[1].value
        shapeuri = self.resolverobject.resolve_shape_name_to_uri(shapename)
        result1 = self.resolverobject.resolve_property_name_to_uri(propname,shapeuri )
        result = rdfxml.uri_to_prefixed_tag(result1, uri_to_prefix_map=self.prefixes)
        self.mapping_identifer_to_uri[f"{shapename}.{propname}"] = result
        self.mapping_uri_to_identifer[result] = f"{shapename}.{propname}"
        logger.info( f"dottedname {s=} {s[0]=} returns {result}" )
        return result

