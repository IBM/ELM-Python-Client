##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import logging

import lxml.etree as ET

logger = logging.getLogger(__name__)

# Some well-known and used RDF/XML prefixes
RDF_DEFAULT_PREFIX = {
    'acc':              'http://open-services.net/ns/core/acc#',  # added for GCM
    'acp':              'http://jazz.net/ns/acp#',
    'atom':             "http://www.w3.org/2005/Atom",
    'config_ext':       'http://jazz.net/ns/config_ext#',
    'dc':               'http://purl.org/dc/elements/1.1/',
    'dcterms':          'http://purl.org/dc/terms/',
    'dng_reqif':        'http://jazz.net/ns/rm/dng/reqif#',
    'dng_task':         'http://jazz.net/ns/rm/dng/task#',      # only for task tracker
    'foaf':             'http://xmlns.com/foaf/0.1/',
    'gc':               'http://jazz.net/ns/globalconfig#',
    'jazz_rm':          'http://jazz.net/ns/rm#',
    'jfs':              'http://jazz.net/xmlns/prod/jazz/jfs/1.0/',
    'jp':               'http://jazz.net/xmlns/prod/jazz/process/1.0/',
    'jp06':             'http://jazz.net/xmlns/prod/jazz/process/0.6/',
    'ldp':              'http://www.w3.org/ns/ldp#',
    'ns':               'http://com.ibm.rdm/navigation#',
    'oslc':             'http://open-services.net/ns/core#',
    'oslc_auto':        'http://open-services.net/ns/auto#',
    'oslc_am':          'http://open-services.net/ns/am#',
    'oslc_cm':          'http://open-services.net/xmlns/cm/1.0/',
    'oslc_cm1':         'http://open-services.net/ns/cm#',
    'oslc_cm_10':       'http://open-services.net/xmlns/cm/1.0/cm#',
    'oslc_config':      'http://open-services.net/ns/config#',
    'oslc_config_ext':  'http://jazz.net/ns/config_ext#',
    'oslc_qm':          'http://open-services.net/ns/qm#',
    'oslc_qm_10':       'http://open-services.net/xmlns/qm/1.0/',
    'oslc_rm':          'http://open-services.net/ns/rm#',
    'oslc_rm_10':       'http://open-services.net/xmlns/rm/1.0/',
    'owl':              'http://www.w3.org/2002/07/owl#',
    'process':          'http://jazz.net/ns/process#',
    'public_rm_10':     'http://www.ibm.com/xmlns/rm/public/1.0/',
    'prov':             'http://www.w3.org/ns/prov#',  # added for GCM
    'qm_rqm':           "http://jazz.net/ns/qm/rqm#",
    'qm_ns2':           "http://jazz.net/xmlns/alm/qm/v0.1/",
    'rdf':              'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs':             'http://www.w3.org/2000/01/rdf-schema#',
    'rdm_types':        'http://www.ibm.com/xmlns/rdm/types/',
    'rm':               'http://www.ibm.com/xmlns/rdm/rdf/',
    'rm_ds':            'http://jazz.net/xmlns/alm/rm/datasource/v0.1', # For RR
    'rm_modules':       'http://jazz.net/ns/rm/dng/module#',
    'rm_config':        'http://jazz.net/ns/rm/dng/config#',
    'rm_nav':           'http://jazz.net/ns/rm/navigation#',
    'rm_text':          'http://jazz.net/xmlns/alm/rm/text/v0.1', # for RR
    'rm_view':          'http://jazz.net/ns/rm/dng/view#',
    'rqm':              'http://jazz.net/xmlns/prod/jazz/rqm/qm/1.0/',
    'rrm':              'http://www.ibm.com/xmlns/rrm/1.0/', # For RR
    'rtc_cm':           "http://jazz.net/xmlns/prod/jazz/rtc/cm/1.0/",
    'xhtml':            'http://www.w3.org/1999/xhtml',
    'xml':              'http://www.w3.org/XML/1998/namespace',
    'xsd':              'http://www.w3.org/2001/XMLSchema#',
    'xs':              'http://www.w3.org/2001/XMLSchema'
}

# Register prefixes to XML system
for prefix,uri in list(RDF_DEFAULT_PREFIX.items()):
    ET.register_namespace(prefix, uri)

def addprefix(prefix,uri,prefix_map=RDF_DEFAULT_PREFIX):
    logger.info( f"Adding prefix {prefix=} {uri=}" )
    if  ( not uri.startswith('http://') and not uri.startswith('https://') ) or (not uri.endswith('#') and not uri.endswith('/')):
        raise Exception( f"BAD URI {prefix=} {uri}" )
    uses = [k for k,v in prefix_map.items() if v==uri]
    if uses:
        logger.info( f"Warning prefix {prefix} uri {uri} is already used for prefex {uses[0]}" )
    prefix_map[prefix]=uri
    ET.register_namespace(prefix, uri)

# find single element matching element_xpath, and checks them for any subelement matching condition_xpath and if condition_value is specified then also matching it
# exception if more than 1 match!
def xml_find_element(xml, element_xpath, condition_xpath=None, condition_value=None, strip=True, prefix_map=RDF_DEFAULT_PREFIX):
    results = xml_find_elements(xml, element_xpath, condition_xpath=condition_xpath, condition_value=condition_value, strip=strip, prefix_map=prefix_map)
    if len(results) > 0:
        if len(results) > 1:
            raise Exception(f"Multiple results when single result expected! {results}")
        return results[0]
    return None

# find all elements matching element_xpath, and checks them for any subelement matching condition_xpath and if condition_value is specified then also matching it

# condition_xpath is xpath with additional features:
# ending in /#text compares the .text with condition_value - selects element if it matches
# ending in /@attrib compares value of attrib with condition_value - selects element if it matches
# default is to match .text with condition_value
# or if no condition_value is specified then the element is added to results

def xml_find_elements(xml, element_xpath, condition_xpath=None, condition_value=None, strip=True,
                      prefix_map=RDF_DEFAULT_PREFIX):
    elements = xml.findall(element_xpath, prefix_map)
    def eq(left, right):
        if strip and left and right:
            return left.strip() == right.strip()
        else:
            return left == right

    results = []
    if condition_xpath:
        # get the last special part of the condition_xpath, if there is one
        last_slash_pos = condition_xpath.rfind('/')
        cond_xp = condition_xpath
        cond_spec = None
        if last_slash_pos >=0:
            last_part = condition_xpath[last_slash_pos + 1:]
            if last_part == '#text' or last_part.startswith('@'):
                # the special last parts shorten the condition_xpath
                cond_xp = condition_xpath[:last_slash_pos]
                cond_spec = last_part

        for e in elements:
            # check ALL matching subelements (used just to use e.find so only tried matching first subelement, which failed e.g. when looking for QueryCapability)
            subels = e.findall(cond_xp, prefix_map)
            for x in subels:
                if cond_spec and condition_value:
                    if cond_spec == '#text':
                        if eq(x.text, condition_value):
                            results.append(e)
                            # no need to check any more subelements
                            break
                    elif cond_spec.startswith('@'):
                        if eq(x.get(uri_to_tag(cond_spec[1:])), condition_value):
                            results.append(e)
                            # no need to check any more subelements
                            break
                    else:
                        raise Exception( f"unexpected special value {cond_spec} in xml_find_elements()" )
                else:
                    if condition_value:
                        if eq(str(x.text), str(condition_value)):
                            results.append(e)
                            # no need to check any more subelements
                            break
                    else:
                        results.append(e)
                        # no need to check any more subelements
                        break
    else:
        results = list(elements)

    return results

# finds first element using xpath and returns (in order of preference) its rdf attrib, rdf:resource, rdf:about, or text
def xmlrdf_get_resource_uri(xml, xpath=None, prefix_map=RDF_DEFAULT_PREFIX,attrib=None):
    if xml is None:
        return None
    r = xml.find(xpath, prefix_map) if xpath else xml
    if r is not None:
        if attrib is not None:
            result = r.get(uri_to_tag(attrib, prefix_map=prefix_map))
            return result
        result = r.get(uri_to_tag('rdf:resource', prefix_map=prefix_map))
        if result:
            return result
        result = r.get(uri_to_tag('rdf:about', prefix_map=prefix_map))
        if result:
            return result
        result = r.text
        if result:
            return result
    return None


# finds first element using xpath and return its text value
def xmlrdf_get_resource_text(xml, xpath, prefix_map=RDF_DEFAULT_PREFIX):
    r = xml.find(xpath, prefix_map)
    if r is not None:
        result = r.text
        return result
    return None


# The term "tag" usually refers to an ElementTree-style tag "{ns}id"
# The term "prefixed tag" refers to an XML namespaced tag like "ns:id"

# return the full uri for a tag like rdf:a or {rdf}a
def tag_to_uri(tag, prefix_map=RDF_DEFAULT_PREFIX,noexception=False):
    if tag is None:
        return None
    pos_colon = tag.find(':')
    if tag.find('/') < 0 and pos_colon >= 0:
        prefix = tag[:pos_colon]
        if prefix not in prefix_map:
            if not noexception:
                raise Exception("Prefix is not resolved: %s" % tag)
            else:
                return tag
        return prefix_map[prefix] + tag[pos_colon + 1:]
    # as the tag contains a / or does not contain :, simply remove the { } and return the resulting URI
    return tag.replace('{', '').replace('}', '')


# return the tag equivalent of a uri - tag is in form e.g. {rdf}a
def uri_to_tag(uri, prefix_map=RDF_DEFAULT_PREFIX):
    if uri is None:
        return None
    pos_colon = uri.find(':')
    if uri.find('/') < 0 and pos_colon >= 0:
        prefix = uri[:pos_colon]
        if prefix not in prefix_map:
            raise Exception("Prefix is not resolved: %s" % uri)
        return '{' + prefix_map[prefix] + '}' + uri[pos_colon + 1:]
    pos = max(uri.rfind('#'), uri.rfind('/'))
    if pos == -1:
        return uri
    return '{' + uri[:pos + 1] + '}' + uri[pos + 1:]


# convert tag to XML-style prefixed tag
def tag_to_prefix(tag):
    if tag is None:
        return None
    return tag[tag.find('{') + 1: tag.find('}')]

# convert uri to a prefixed tag, creating a new prefix if one doesn't already exist
# of if uri is already a prefixed tag, make sure prefix is put in uri_to_prefix_map
# uri_to_prefix_map is updated with the new prefix (this is the project-specific prefixes)
# default_map is also updated (this is all the application-wide prefixes)
def uri_to_prefixed_tag(uri, uri_to_prefix_map=None, default_map=None,oktocreate=True,noexception=False):
    logger.debug( f"uri_to_prefixed_tag {uri=}" )
    if uri_to_prefix_map is None: # this allows caller to pass an empty dictionary which will be updated (the usual 'or' test doesn't allow returning!)
        uri_to_prefix_map = {}
    if default_map is None:
        default_map = RDF_DEFAULT_PREFIX
    pos = max(uri.rfind('#'), uri.rfind('/'))
    if pos == -1:
        # this could already be prefixed
        if ':' in uri:
            if not uri.startswith('http:') and not uri.startswith('https:'):
                prefix,rest = uri.split(':',1)
                if ' ' in prefix:
                    return uri
                if prefix not in uri_to_prefix_map:
                    if prefix not in default_map:
                        if not noexception:
                            raise Exception( "Unknown prefix {prefix}" )
                        else:
                            return uri
                    # copy from default map
                    logger.debug( "Copying prefix from default {uri} {prefix} {default_map[prefix]}" )
                    uri_to_prefix_map[default_map[prefix]]=prefix
        else:
            if not noexception:
                raise Exception( f"Unknown uri {uri}" )

        return uri
    if not uri.startswith('http:') and not uri.startswith('https:'):
        return uri
    ns_uri = uri[:pos + 1]
    logger.debug( f"{ns_uri=}" )
    if ns_uri in uri_to_prefix_map:
        prefix = uri_to_prefix_map[ns_uri]
        logger.debug( f"found prefix {prefix=} {ns_uri=}" )
    else:
        if ns_uri in list(default_map.values()):
            # use the existing prefix
            prefix = [k for (k, v) in list(default_map.items()) if v == ns_uri][0]
            logger.debug( f"found prefix in default map {prefix=} {ns_uri=}" )
            prefixok = True
        else:
            logger.debug( f"Creating new prefix {ns_uri=}" )
            prefixok=False
            if oktocreate:
                # create a new prefix
                for i in range(1000):
                    prefix = 'rp' + str(i)
                    if prefix not in list(uri_to_prefix_map.values()) and prefix not in default_map.keys():
                        prefixok = True
                        logger.debug( f"New prefix {prefix}" )
                        break

        if prefixok:
            uri_to_prefix_map[ns_uri] = prefix
            default_map[prefix] = ns_uri
            logger.debug( f"Defined new prefix {prefix} {ns_uri}" )
        elif not noexception:
            raise Exception("Not allowed to create a new prefix for URI: %s" % ns_uri)
        else:
            logger.debug( f"FAILED PREFIX CREATION for {uri}" )
            return uri

    return prefix + ':' + uri[pos + 1:]


# if the URI matches an existing prefix mapping (ending with # or /) then apply it and return prefixed tag, otherwise don't - return the value
def uri_to_default_prefixed_tag(uri, default_map=RDF_DEFAULT_PREFIX):
    if not uri.startswith('http:') and not uri.startswith('https:'):
        return uri
    pos = max(uri.rfind('#'), uri.rfind('/'))
    if pos == -1:
        return uri
    ns_uri = uri[:pos + 1]
    if ns_uri in list(RDF_DEFAULT_PREFIX.values()):
        prefix = [k for (k, v) in list(default_map.items()) if v == ns_uri][0]
        return prefix + ':' + uri[pos + 1:]
    return uri


def remove_tag(s):
    if s.startswith('{'):
        s = s[s.find('}') + 1:]
    return s

