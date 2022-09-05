##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import logging
import re
import time
import urllib

import colorama
import lark
import lxml.etree as ET
import tqdm

from . import _queryparser
from . import httpops
from . import rdfxml
from . import server
from . import utils

logger = logging.getLogger(__name__)

OSLC_PAGESIZE = 200

# this is used to capture the series of query URLs (likely only the first one will be later used)
# (couldn't find any easy way to return these to the caller for optional display to user)
# (maybe need to return a dictionary or object for results which includes these raw query URL(s))
queryurls = []

##############################################################################################
# used to check for key pressed to abort the query cleanly returning the results retrieved so far
# (rather than ^C which would lose any data retrieved)

try:
    # Win32
    from msvcrt import getch,kbhit
except ImportError:
    # UNIX
    import sys
    import tty
    import termios
    import atexit
    import select

    def getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def kbhit():
        # Save the terminal settings
        fd = sys.stdin.fileno()
        new_term = termios.tcgetattr(fd)
        old_term = termios.tcgetattr(fd)

        # New terminal setting unbuffered
        new_term[3] = (new_term[3] & ~termios.ICANON & ~termios.ECHO)
        termios.tcsetattr(fd, termios.TCSAFLUSH, new_term)
        dr,dw,de = select.select([sys.stdin], [], [], 0)
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
        return dr != []

##############################################################################################

# This class provides OSLC Query capability for use by any app
@utils.mixinomatic
class _OSLCOperations_Mixin:
    def __init__(self,*args,**kwargs):
        super().__init__()

    # Do an OSLC query using basic or enhanced OSLC query syntax with human-friendly references
    #
    # isnull/isnotnull are a list of artifact attributes. These will be applied as an 'AND' on the results: isnull will only allow values
    #   which have null for all the attributes in the list to be kept, isnotnull will keep all entries where the named attribute isn't null
    # The querystring optionally accepts enhanced OSLC syntax which as well as the basic OSLC query, supports:
    #   * combining queries with ( ), and then applying logical and (&&) and logical or (||) between queries
    #   * using the isnull and isnotnull filters afterwards to remove unwanted items (I couldn't work out a neat way to integrate this in the enhanced query syntax
    #
    # NOTE this is not designed for efficiency or in any way optimised - if you put the same query twice and OR/AND them, the OSLC query will be made twice
    # NOTE if efficiency becomes important it might be simpler to retrieve the full set of artifacts with all their relevant attributes from RM and do the query details locally, because then only one query is made
    # OR, set up your OSLC query to do the first biggest query first and refine it entirely locally - but this isn't implemented here
    #
    # sortby is a list of attribute URIs (e.g. dcterms:identifier
    # sortorder default is + for ascending alphabetic sort, use'-' to get descending alphabetic sorting - use '>' to get increasing numeric sorting of the first item in sortby, or < to get decreasing numeric sort (if any value doesn't convert to integer it is assumed to be 0 so will sort first/last)
    def do_complex_query(self,queryresource, *, querystring='', searchterms=None, select='', orderby='', properties=None, isnulls=None
                        ,isnotnulls=None, enhanced=True, show_progress=True
                        ,show_info=False, verbose=False, maxresults=None, delaybetweenpages=0.0
                        , pagesize=200
                        ,resolvenames=True
                        ,totalize=False
                     ):
        if searchterms and querystring:
            logger.info( f"{searchterms=}" )
            logger.info( f"{querystring=}" )
            raise Exception( "Can't use query and search terms together!" )
        if querystring is None:
            querystring=''
        logger.debug( f"{querystring=}" )
        logger.debug( f"{queryresource=}" )
        # find the query capability
        querycapabilityuri = self.get_query_capability_uri(resource_type=queryresource,context=self)
        self.querycapabilityuri = querycapabilityuri
        if querycapabilityuri is None:
            raise Exception( f"No query capability for resource type {queryresource} found!" )
        logger.debug( f"{querycapabilityuri=}" )

        properties = properties or []
        isnulls = isnulls or []
        isnotnulls = isnotnulls or []
        searchterms = searchterms or []

        if show_progress:
            print( "Preparing Query" )

        prefixes = {}
        # process select - this resolves name to URIs and also finds all the prefixes used
        if len(select)>0:
            logger.debug( f"{select=}" )
            parsedselect,selectprefixes = self._parse_select(select)
            prefixes.update(selectprefixes)
            logger.debug( f"{parsedselect=} {selectprefixes=} {prefixes=}" )
        else:
            parsedselect = []

        # process orderby
        if len(orderby)>0:
            parsedorderby,orderprefixes = self._parse_orderby(orderby)
            prefixes.update(orderprefixes)
        else:
            parsedorderby = []

        # check the query - it can validly be empty which means all resources will be returned
        # USE WITH CARE due to server load!
        if len(querystring.strip()) == 0:
            querysteps = []
            uri_to_name_mapping = {}
        else:
            try:
                (querysteps, uri_to_name_mapping) = self._parse_oslc_query(querystring)
#            except lark.exceptions.VisitError as e:
            except Exception as e:
                raise Exception( "Error parsing query" )
            logger.info( f"{querysteps=}" )
            logger.info( f"{uri_to_name_mapping=}" )

        if verbose:
            if querysteps:
                for i,querystep in enumerate(querysteps):
                    logger.info( f"Query step {i}: {querystep}" )
            else:
                logger.info( f"No query specified - returns all resources (could affect server behaviour/load significantly, and may fail if the query takes too long!" )

        if verbose:
            print( "Starting query - to terminate with current retrieved results press Esc and wait for the current query page to complete and then for processing to complete" )
        # now evaluate the queries
        resultstack = self._evaluate_steps(querycapabilityuri,querysteps, select=parsedselect, prefixes=prefixes
                                            , orderbys=parsedorderby, searchterms=searchterms, show_progress=show_progress
                                            , verbose=verbose, maxresults=maxresults,delaybetweenpages=delaybetweenpages
                                            , pagesize=pagesize)

        if len(resultstack) != 1:
            raise Exception(f"Something went horribly wrong and there isn't exactly one result left on the query stack! {len(resultstack)} {resultstack}")

        # Now tidy up the results
        # in particular make sure type uris as column headers and values are turned into their more meaningful names
        # go through the results, mapping attribute uris back to names
        mappedresult = {}
        originalresults = resultstack[0]
        remappednames = {}

        if verbose:
            print( f"Original results are {len(originalresults)} resources" )

        if show_progress:
            total = len(originalresults.items())
            pbar = tqdm.tqdm(initial=0, total=total,smoothing=1,unit=" results",desc="Processing       ")

        # convert uris to human-friendly names
        for kuri, v in originalresults.items():
            logger.info( f"post-processing result {kuri} {v}" )
            v1 = {}
            for kattr, vattr in v.items():
                logger.info( f"{kattr=} {vattr=}" )
                # first try to convert the value to a name
                if isinstance(vattr, list):
                    if totalize:
                        remappedvalue = len(vattr)
                    else:
                        remappedvalue = []
                        for lv in vattr:
                            if resolvenames:
                                remappedvalue.append(self.resolve_uri_to_name(lv))
                            else:
                                remappedvalue.append(lv)
                else:
                    remappedvalue = self.resolve_uri_to_name(vattr) if resolvenames else vattr
                # then check the attribute itself for one of the mappings we created while parsing the querystring to turn it into an oslc query
                if kattr in uri_to_name_mapping:
                    # this name was locally mapped
                    v1[uri_to_name_mapping[kattr]] = remappedvalue
                else:
                    # try to map back to a name
                    if kattr not in remappednames:
                        remappedname = self.resolve_uri_to_name(kattr) if resolvenames else kattr
                        remappednames[kattr] = remappedname
                    if remappednames[kattr] is not None:
                        v1[remappednames[kattr]] = remappedvalue
                    else:
                        v1[kattr] = remappedvalue
            logger.info( f"> produced {kuri} {v1}" )
            mappedresult[kuri] = v1

            if show_progress:
                pbar.update(1)

        # if showing progress and pbar has been created (after the first set of results if paged)
        if show_progress and pbar is not None:
            # close off the progress bar
            pbar.close()
            print( "Processing completed" )

        if isnulls or isnotnulls:
            logger.debug( f"{isnulls=} {isnotnulls=}" )
            # now filter for isnulls and isnotnulls
            todeletes = []
            for kuri in list(mappedresult.keys()):
                for isnull in isnulls:
                    # lookup the isnul URI to a name (as used in the results)
                    lookupname = self.resolve_uri_to_name(isnull)
                    if lookupname in mappedresult[kuri].keys():
                        todeletes.append(kuri)
                        kuri = None
                        break
                if kuri is not None:
                    for isnotnull in isnotnulls:
                        # lookup the isnul URI to a name (as used in the results)
                        lookupname = self.resolve_uri_to_name(isnotnull)
                        if lookupname not in mappedresult[kuri].keys():
                            todeletes.append(kuri)
                            break
            for kuri in todeletes:
                if kuri in mappedresult.keys():
                    del mappedresult[kuri]

            if verbose:
                print( f"Without null/notnulls there are {len(mappedresult)} resources" )

        # all done!
        if verbose:
            print( f"Final results contains {len(mappedresult)} resources" )

        return mappedresult

    ########################################################################################
    ########################################################################################
    # Below here is private implementation
    #

    # for a query which has been parsed to steps, execute the steps, recursing if there is more than one compount_term
    # a query with two logicalor terms looks like: [[['dcterms:identifier', 'in', [3949]]], [['dcterms:identifier', 'in', [3950]]], 'logicalor']
    def _evaluate_steps(self, querycapabilityuri,querysteps,*,resultstack=None, select=None, prefixes=None, orderbys=None, searchterms=None, show_progress=False, verbose=False, maxresults=None, delaybetweenpages=0.0, pagesize=200):
        logger.info( f"_evaluate_steps {querysteps}" )
        resultstack = resultstack if resultstack is not None else []
        orderbys = orderbys or []
        select = select or []
        prefixes = prefixes or {}
        searchterms = searchterms or []

        if len(querysteps)==0:
            # ensure a empty oslc.where value is created
            querysteps = [[]]
        for step in querysteps:
            logger.info( f"{step=} {resultstack=}" )

            if isinstance(step, list):
                if len(step)>0 and isinstance(step[0],list):
                    # handle anded terms
                    # iterate, recursing
                    resultstack = self._evaluate_steps( querycapabilityuri,step,resultstack=resultstack, select=select, prefixes=prefixes, orderbys=orderbys, searchterms=searchterms, show_progress=show_progress, verbose=verbose, maxresults=maxresults, delaybetweenpages=delaybetweenpages)
#                    raise Exception( f"Very strange parse result! {step}" )
                else:
                    # do an actual query
                    results = self.execute_oslc_query(querycapabilityuri,whereterms=[step], select=select, prefixes=prefixes, orderbys=orderbys, searchterms=searchterms, show_progress=show_progress, maxresults=maxresults, delaybetweenpages=delaybetweenpages, pagesize=pagesize, verbose=verbose)
                    if isinstance(results, list):
                        resultlist = {}
                        for result in results:
                            resultlist[result] = {}
                        resultstack.append(resultlist)
                    else:
                        # put results onto resultstack
                        resultstack.append(results)
            elif step == "logicalor":
                # pop the top two items off the stack, or them together, push result to stack
                # assumes if a key is in both they both have the same data so it doesn't matter which one we use
                or1 = resultstack.pop()
                or2 = resultstack.pop()
                orresult = {}
                # add the or1 entries to the result
                for k1 in or1.keys():
                    orresult[k1] = or1[k1]
                    # remove this key from or2 if it is there
                    or2.pop(k1, None)
                # add the remaining or2 entries to the result
                for k2 in or2.keys():
                    orresult[k2] = or2[k2]
                del or1
                del or2
                resultstack.append(orresult)

            elif step == "logicaland":
                # pop the top two items off the stack, and them together, push result to stack
                # assumes if a key is in both they both have the same data so it doesn't matter which one we use
                and1 = resultstack.pop()
                and2 = resultstack.pop()
                andresult = {}
                # add entries that are in both and1 and and2 into the result
                for k1 in and1.keys():
                    if k1 in and2:
                        andresult[k1] = and1[k1]
                del and1
                del and2
                resultstack.append(andresult)
            else:
                raise Exception( f"Unknown step type {step}" )
        logger.info( f"{resultstack=}" )
        return resultstack

    # returns the single core artifact from the query results
    # assumes query results include rm_nav:parent
    def find_core_artifact(self,queryresults):
        cas = self.find_core_artifacts(queryresults)
        if len(list(cas.keys()))>1:
            raise Exception( "More than one core artifact found when only one expected!" )
        if len(list(cas.eys()))==0:
            raise Exception( "No core artifact found!" )
        return cas

    # returns just the core artifacts (which have rm_nav:parent) from the query results
    # assumes query results include rm_nav:parent
    def find_core_artifact(self,queryresults):
        results = {}
        for k,v in queryresults.items():
            if 'rm_nav:parent' in v:
                results[k]=v
        return results
        
    # returns just the module artifacts (which don't have rm_nav:parent) from the query results
    # assumes query results would include rm_nav:parent if it had a value
    def find_module_artifacts(self,queryresults):
        results = {}
        for k,v in queryresults.items():
            if 'rm_nav:parent' not in v:
                results[k]=v
        return results
        

    # lower-level OSLC query with prepared arguments
    # by default returns a list of uris as result, but if you provide a select list of attributes, returns a dictionary with as key the artifact uri, each result containing a dictionary with the selected values
    # the whereterms can be created using create_query_operator_string
    # NOTE that prefixes is reversed from what you might expect, i.e. keyed by URL and the value is the prefix!
    # NOTE that whereterms should be a list of lists (the oslc terms) - each of these nested lists is ['attribute',operator',value'] - if more than one and'd term, the first entry must be 'and'!
    def execute_oslc_query(self, querycapabilityuri, *, whereterms=None, select=None, prefixes=None, orderbys=None, searchterms=None, show_progress=False, verbose=False, maxresults=None, delaybetweenpages=0.0, pagesize=200, intent=None):
        if select is None:
            select = []
        prefixes = prefixes or {}
        if orderbys is None:
            orderbys = []
        if searchterms is None:
            searchterms = []
        if whereterms is None:
            whereterms = [[]]

        query_params = self._create_query_params(whereterms, select=select, prefixes=prefixes, orderbys=orderbys, searchterms=searchterms)

        if self.hooks:
            query_params1 = self.hooks[0](query_params)
        else:
             query_params1 = query_params

        results = self._execute_vanilla_oslc_query(querycapabilityuri,query_params1, select=select, prefixes=prefixes, show_progress=show_progress, verbose=verbose, maxresults=maxresults, delaybetweenpages=delaybetweenpages, pagesize=pagesize, intent=intent)
        return results

    # convert whereterms (which is a list of OSLC and terms) into a corresponding oslc.where string
    # replacing property references with prefixed tags
    # updates map with all prefixes used
    def _get_query_clauses(self, whereterms, prefixmap):
        clauses = []
        logger.debug( f"{whereterms=}" )
        if not isinstance(whereterms, list):
            raise Exception( f"Whereterms isn't even a list! {whereterms}")
        if not isinstance(whereterms[0], list):
            if whereterms[0]!='and':
                raise Exception( f"Whereterms isn't a list of lists! {whereterms[0]}")
            else:
                raise Exception( f"Whereterms isn't a list of lists! {whereterms[0]}")
        if len(whereterms[0])>0 and isinstance(whereterms[0][0],list):
            raise Exception( f"Whereterms too deeply nested list! {whereterms[0][0]}")
        if isinstance(whereterms[0], list) and len(whereterms[0])>0 and whereterms[0][0]=='and':
            whereterms = whereterms[0][1:]
        else:
            pass
        for a in whereterms:
            logger.debug( f"{a=}" )
            if len(a)>0:
                (property, operator, value) = a
                if property != "*":
                    tag = rdfxml.uri_to_prefixed_tag(rdfxml.tag_to_uri(property), prefixmap)
                else:
                    tag = "*"
                if operator == "scope":
                    # handle nested series of whereterms recursively
                    scopedterm = self._get_query_clauses(value, prefixmap)
                    clauses.append(f'{tag}{{{scopedterm}}}')    # note there are no space chars allowed by the OSLC Query sytax!
                elif operator == "in":
                    inlist = []
                    for val in value:
                        if isinstance(value, str):
                            inlist.append(val)
                        else:
                            inlist.append(str(val))
                    inliststr = ",".join(inlist)
                    clauses.append(f'{tag} in [{inliststr}]')
                else:
                    clauses.append(f'{tag}{operator}{value}')
        return " and ".join(clauses)

    # NOTE this takes whereterms which is a list of tuples each one (property,operator,value) - operator may be a comparison in which case the comparison is with string/number value, or operator may be scope or in, in which case value is a list of whereterms, or a list of values
    # May support the 'in' operator - not tested yet!
    # May support scoped terms - not tested yet!
    # returns a dictionary suitable for use as params in a request to the server app
    def _create_query_params(self, whereterms, select=None, prefixes=None, orderbys=None, searchterms=None):
        select = select or []
        prefixes = prefixes or {}
        orderbys = orderbys or []
        searchterms = searchterms or []

        uri_to_prefix_map = {}

        if whereterms:
            where_clauses = self._get_query_clauses(whereterms, uri_to_prefix_map)
        else:
            where_clauses = []
#        print( f"{where_clauses=}" )
        # work out the prefixes to be sent in the oslc query
        theprefixes = []
        allprefixes=[]

        # get the select terms
        selecttags = []
        if select:
            for sel in select:
                selecttags.append(sel)

        for uri, prefix in list(uri_to_prefix_map.items()):
            # if the prefix is in the orderbys prefixes, remove it from there
            if prefix not in allprefixes:
                theprefixes.append(f'{prefix}=<{uri}>')
                allprefixes.append(prefix)

        # finally add in any remaining prefixes from orderbys and select
        for uri,op in prefixes.items():
            if op not in allprefixes:
               theprefixes.append(f'{op}=<{uri}>')
               allprefixes.append(op)

        # build the params result
        result = {}
        if len(theprefixes)>0:
            result['oslc.prefix'] = ','.join(theprefixes)
        if where_clauses:
            result['oslc.where'] = where_clauses
        if select:
            result['oslc.select'] = ",".join(select)
        if orderbys:
            result['oslc.orderBy'] = ",".join(orderbys)
        if searchterms:
            result['oslc.searchTerms'] = '"'+'","'.join(searchterms)+'"'
        return result

    #
    # This executes a single vanilla OSLC query (the enhanced stuff is handled by the caller)
    # Returns a dictionary with artifact uri as key containing a (possibly empty) dictionary with the selected values
    # NOTE the select contents must also be already encoded into query_params!
    # select is used to build the returned dictionary containing only the selected values
    #

    def _execute_vanilla_oslc_query(self, querycapabilityuri, query_params, orderby=None, searchterms=None, select=None, prefixes=None, show_progress=False, pagesize=200, verbose=False, maxresults=None, delaybetweenpages=0.0, intent=None):
        select = select or []
        orderby = orderby or []
        searchterms = searchterms or []
        prefixes = prefixes or {}
        logger.debug( f"{prefixes=}" )
        headers = {}

        if pagesize > 0 or maxresults:
            # use paging
            query_params['oslc.paging'] = 'true'
            query_params['oslc.pageSize'] = str(pagesize) if maxresults is None or ( pagesize>0 and pagesize<maxresults ) else str(maxresults)


        logger.debug(f"execute_query {query_params} {select}")
        base_uri = querycapabilityuri
        logger.info( f"The base OSLC Query URL is {base_uri}" )
        logger.debug("base_uri=" + repr(base_uri))

        # unparse the query capability URL to get any existing generic parameters, to which we will add the params for this query
        url_parts = list(urllib.parse.urlparse(base_uri))
        logger.info( f"{url_parts=}" )
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        query.update(dict(((k, httpops.to_binary(v)) for k, v in list(query_params.items()) if v)))
        url_parts[4] = ""
        url_parts[5] = ""
        # reconstruct just the base scheme:hostname
        # inisists on using + instead of %20!
        query_url = urllib.parse.urlunparse(url_parts)
        
        logger.info( f"The full OSLC Query URL is {query_url}" )

        # in case of paged results, always prepare to collect a list of results
        result_xmls = []
        params = {}
        params.update(query)
        logger.info( f"The parameters for this query are {params}" )

        fullurl = f"{query_url}?{urllib.parse.urlencode( params, quote_via=urllib.parse.quote, safe='/')}"
        if verbose:
            print( f"Full query URL is {fullurl}" )
#        print( f"Full query URL is {fullurl}" )
#        burp
        # retrieve all pages of results - they will be processed later
        total = 1
        page = 0
        if show_progress:
            pbar = None
#            pbar = tqdm.tqdm(initial=0, total=total,smoothing=1,unit=" results",desc="Querying          ")
            donelasttime=0
            # show dummy progress of 0 BECAUSE we don't know the total yet!
            print( "Querying           : 0%|\r",end="" )
        # this loop accumulates the raw results from each page - they'll be combined later
        # there may be one or several pages, indicated by a nextPage tag, which is not present on the last page
        terminate=False
        while True:
            logger.debug('OSLC Query URI: ' + query_url)
            page += 1
            
            # let the intent from entry be used for first page only, after that number the page being retrieved
            if page>1:
                intent = f"Retrieve {utils.nth(page)} page of OSLC query results"

            # request this page
            this_result_xml = self.execute_get_rdf_xml(query_url, params=params, headers=headers, cacheable=False, intent=intent)
            queryurls.append(query_url)
            # accumulate the results
            result_xmls.append(this_result_xml)
            # check for maxresults exceeded - rough calculation!
            if maxresults is not None and len(result_xmls)*pagesize>=maxresults:
                break
            # check for next page link
            if rdfxml.xml_find_element( this_result_xml, ".//oslc:nextPage") is None:
                # no more results to get
                break

            # no parameters should be sent on following pages, they are present in the href link to next page!
            params = None

            # work out the url for the next page
            query_url = rdfxml.xmlrdf_get_resource_uri( this_result_xml, ".//oslc:nextPage")
            # if showing progress, we have to work out how many results there are in total
            # and how many have been retrieved so for, to update the progress bar
            if show_progress:
                # 6.x: <dcterms:title>Query Results: 40220</dcterms:title>
                # <oslc:nextPage rdf:resource="url...&amp;page=3" />

                # work out how many total to retrieve (ccm has many occurrences of totalCount so just choose the first)
                totalel = rdfxml.xml_find_elements(this_result_xml, './rdf:Description/oslc:totalCount')
                totalel = None if not totalel else totalel[0]
                if totalel is not None:
                    total = int(totalel.text)
                else:
                    totaltext = rdfxml.xmlrdf_get_resource_text(this_result_xml, './oslc:ResponseInfo/dcterms:title')
                    if totaltext is not None:
                        ttm = re.search("(\d+)$", totaltext)
                        if ttm is not None:
                            total = int(ttm.group(1))
                        else:
                            raise Exception( "Something very odd happened - total not found" )
                    else:
                        raise Exception( "Something very odd happened - total text not found" )

                # work out how many already retrieved
                rematch = re.search("(page|pageNum)=(\d+)", query_url)
                if rematch is not None:
                    nextpagenumber = int(rematch.group(2))
                    psm = re.search("oslc.pageSize=(\d+)", query_url)
                    if psm is None:
                        raise Exception( "Something very odd happened - oslc.pagesize not found" )
                    ps = int(psm.group(1))
                    donesofar = (nextpagenumber - 1) * ps
                else:
                    # 7.x way
                    rematch1 = re.search("_startIndex=(\d+)", query_url )
                    if rematch1:
                        donesofar=int(rematch1.group(1))
                    else:
                        raise Exception( "Error page number not found in query response!")

                if pbar is None:
                    pbar = tqdm.tqdm(initial=donesofar, total=total,smoothing=1,unit=" results",desc="Querying         ")
                    donelasttime = 0
                else:
                    pbar.update(donesofar-donelasttime)
                donelasttime = donesofar

            while kbhit():
                ch = getch()
                if ch == b'\x1b':
                    print("\nUser pressed escape, terminating query with current results")
                    terminate=True
                else:
                    # only print note about Esc if not already going to terminate
                    if not terminate:
                        print( "\nOnly pressing Esc terminates the query - keypress ignored")
            if terminate:
                break
            if delaybetweenpages>0.0:
                time.sleep(delaybetweenpages)
            
                
        # finished doing the actual query - now process what's been received!

        # if showing progress and pbar has been created (after the first set of results if paged)
        if show_progress and pbar is not None:
            # close off the progress bar
            if not terminate:
                pbar.update(total-donelasttime)
            pbar.close()

        if show_progress:
            print( f"Query completed in {len(result_xmls)} page(s)" )

        # try to find OSLC2 query result resource from the first result (if pages, later results will show this same number)
        total_count_e = result_xmls[0].find('.//{http://open-services.net/ns/core#}totalCount')

        #
        # try to find the list of results - how these are identified is different for each of rm/ccm/gc
        # for RM, the results are each in a <rdfs:member>
        # for ccm the results field has a list of members with no content but rdf:resource identifying the resource, then find the Description item for that resource to get content
        # for GC find   <rdf:Description rdf:about="https://jazz.ibm.com:9443/gc/oslc-query/components/_Xkr1EUP1EemZm4WkswTSBw"> (where rdf:about is the component we searched on)
        #   contains     <j.0:contains rdf:resource="https://jazz.ibm.com:9443/gc/component/1"/>
        #     then look for <rdf:Description rdf:about="https://jazz.ibm.com:9443/gc/component/1">
        #       contains <rdfs:member> results
        rmmode = False
        cmmode = False
        gcmode = False
        qmmode = False

        # check the first set of results to decide what mode we are in
        rdfs_member_es = rdfxml.xml_find_elements( result_xmls[0],'.//rdfs:member/*')
        # only RM returns rdfs:member with sub-tags
        logger.debug(f"rdfs_member_es={rdfs_member_es}")
        if len(rdfs_member_es) == 0:
            # non-RM 
            rdfs_member_es = rdfxml.xml_find_elements( result_xmls[0], './/rdfs:member')
            logger.debug(f"rdfs_member_es1={rdfs_member_es}")
            if len(rdfs_member_es) == 0:
                # QM and GCM don't return rdfs:member like CM
                rdfs_member_es = rdfxml.xml_find_elements( result_xmls[0], './/rdf:Description/ldp:contains')
#                print( f"0 {rdfs_member_es=}" )
                if len(rdfs_member_es) != 0:
                    # for GCM, one element holds all the ldp:contains pointing at each result
                    gcmode = True
                    logger.info(f"rdfs_member_es2={rdfs_member_es}")
#                    print(f"rdfs_member_es2={rdfs_member_es}")
                else:
                    # for QM, each result has a Description and there is no overall container like GCM
                    rdfs_member_es = rdfxml.xml_find_elements( result_xmls[0], './/rdf:Description[@rdf:about]')
                    qmmode = True
                    logger.debug(f"rdfs_member_es3={rdfs_member_es}")
            else:
                # only CM has rdfs:member with no sub-tags
                cmmode = True
        else:
            # only RM returns rdfs:member with sub-tags
            rmmode = True
        logger.info(f"cmmode={cmmode} rmmode={rmmode} gcmode={gcmode} {qmmode=}")
#        print(f"cmmode={cmmode} rmmode={rmmode} gcmode={gcmode} {qmmode=}")
        logger.debug( f"{prefixes=}" )
        revprefixes = { v:k for k,v in prefixes.items()}
        # with select - build a dictionary
        allprops = True if "*" in select else False
        # have to convert the select terms to complete URIs to be able to compare with tags  from the results xml also converted to complete URIs.
        # (the other way to do this would perhaps be to convert the selects to tags)
        if not allprops:
            selecturis = {}
            for sel in select:
                selecturis[rdfxml.tag_to_uri(sel,prefix_map=revprefixes)] = sel
        result = {}
        for result_xml in result_xmls:

            # find the elements:
            if rmmode:
                rdfs_member_es = rdfxml.xml_find_elements( result_xml,'.//rdfs:member/*')
            elif cmmode:
                rdfs_member_es = rdfxml.xml_find_elements( result_xml, './/rdfs:member')
            elif gcmode:
                rdfs_member_es = rdfxml.xml_find_elements( result_xml, './/ldp:contains')
            elif qmmode:
                rdfs_member_es = rdfxml.xml_find_elements( result_xml, './/rdf:Description[@rdf:about]/qm_rqm:orderIndex/..')
#                print( f"1 {rdfs_member_es=}" )
                if len(rdfs_member_es)==0:
                    rdfs_member_es = rdfxml.xml_find_elements( result_xml, './/rdf:Description[@rdf:about]/dcterms:title/..')
#                    print( f"2 {rdfs_member_es=}" )


            # process them
            if len(rdfs_member_es) > 0:
                for rdfs_member in rdfs_member_es:
                    # about is the uri of the resource
                    if cmmode or gcmode:
                        about = rdfs_member.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')
                        # CM-style results
                        desc = result_xml.find(".//rdf:Description[@rdf:about='%s']" % (about), rdfxml.RDF_DEFAULT_PREFIX)
                    elif rmmode or qmmode:
                        # RM/QM-style results
                        about = rdfxml.xmlrdf_get_resource_uri(rdfs_member)
                        desc = rdfs_member
                        # skip entries which have a totalCount - they're not actual results, these are the summary provided by QM
                        if qmmode and len(rdfxml.xml_find_elements( rdfs_member, './/oslc:totalCount'))>0:
                            continue
                    else:
                        raise Exception("Query result extraction mode not set to anything!")
                    # is this a 'duplicate' result? AFAIK only reason this would happen is if oslc.select is e.g. oslc_rm:uses{dcterms:identifier}
                    if about not in result:
                        result[about] = {}
                        dup = False
                    else:
                        dup = True
                    if desc is not None:
                        # for an entry with no children, if dup and value is same then ignore it
                        #   if dup and value is different, exception
                        #
                        # for entry with children
                        #  always: store first value as list or append value to list
                        #

                        themembers = list(desc)
                        # now scan its children - these are the select results
                        for ent in themembers:
                            # place is the column heading
#                            place = None
                            if len(ent)>0 and rdfxml.xmlrdf_get_resource_uri(ent,attrib="rdf:parseType") != "Literal":
                                # this entity has children; it's like using oslc.selct=oslc_rm:uses{dcterms:identifier}
                                # work out a heading for this column by concatenating the ent tag with its child's tags
                                for subent in ent[0]:
                                    # these are the real values - they always result in lists
                                    place = rdfxml.remove_tag(ent.tag)+"/"+rdfxml.remove_tag(subent.tag)
#                                    place = f"{rdfxml.tag_to_prefix(ent.tag)}/{rdfxml.tag_to_prefix(subent.tag)}"
                                    value = subent.text
                                    if value is None:
                                        value = rdfxml.xmlrdf_get_resource_uri(subent)
                                    if place in result[about]:
                                        result[about][place].append(value)
                                        logger.debug( f"Saving{about} {place} {value}" )
                                    else:
                                        result[about][place] = [value]
                                        logger.debug( f"Saving1 {about} {place} {value}" )
                            else:
                                # no children, just use the text if not empty or the resource URL
                                if len(ent)>0 and rdfxml.xmlrdf_get_resource_uri(ent,attrib="rdf:parseType") == "Literal":
                                    # get the XML literal value by converting the whole ent to a string and then strip off the start/end tags!
                                    # (shouldn't there be a less hacky way of doing this?)
                                    literal = ET.tostring(ent).decode()
                                    value = literal[literal.index('>')+1:literal.rindex('<')]
                                    logger.info( f"0 {value=}" )
                                elif ent.text is None or not ent.text.strip():
                                    # no text, try the resource URI
                                    value = ent.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
                                    if value is None:
                                        # no resource URI, use an empty string
                                        value = ""
                                    logger.info( f"1 {value=}" )
                                else:
                                    value = ent.text
                                    logger.info( f"2 {value=}" )
                                place = rdfxml.uri_to_default_prefixed_tag(rdfxml.tag_to_uri(ent.tag))
                                if dup and place in result[about]:
                                    # possibly extend as a list
                                    if result[about][place] is None or type(result[about][place])!=list:
                                        # only extend the list if this value is different
                                        if result[about][place] is not None and result[about][place] != value:
                                            # make it a list
                                            result[about][place] = [result[about][place]]
                                            result[about][place].append(value)
                                            logger.debug( f"Saving4 {about} {place} {value}" )
                                            logger.debug( f"{result[about][place]=}" )
                                        else:
                                            logger.debug( f"Saving5 {about} {place} {value}" )
                                    else:
                                        result[about][place].append(value)
                                        logger.debug( f"Saving3 {about} {place} {value}" )
                                        logger.debug( f"{result[about][place]=}" )

                                else:
                                    result[about][place] = value
                                    logger.debug( f"Saving2 {about} {place} {value}" )

        return result

    #
    # refer to OSLC Query 3.0 https://tools.oasis-open.org/version-control/svn/oslc-core/trunk/specs/oslc-query.html
    #
    # parse the query and return list of steps - each step is a single vanilla OSLC query, and for enhanced query syntax there will be a step per real OSLC query
    #
    # each step is either an OSLC query - a list of [attribute comparison value] - these are used to actually perform a query (as a series of AND operations),
    #   and the results will be pushed the stack
    # or an entry on the list can be a string like logicalor/logicaland (which will take two values from the stack and return a combined result onto the stack)
    # the combination is by matching keys in the returned/stacked query results
    #
    def _parse_oslc_query(self, querystring, enhanced=True, verbose=False):
        if enhanced:
            parser = lark.Lark(_queryparser._enhanced_oslc3_query_grammar, start='where_expression', debug=False)
        else:
            parser = lark.Lark(_basic_oslc3_query_grammar, start='where_expression', debug=False)
        tree = parser.parse(querystring)
        xformer = _queryparser._ParseTreeToOSLCQuery( resolverobject=self )
        querysteps = xformer.transform(tree)
        return querysteps, xformer.mapping_uri_to_identifer

    #
    # parse an oslc.orderby statement, substituting URIs for human-friendly names
    # refer to OSLC Query 3.0 section 7.4 https://tools.oasis-open.org/version-control/svn/oslc-core/trunk/specs/oslc-query.html
    #
    def _parse_orderby(self, orderbystring, verbose=False):
        logger.debug( f"{orderbystring=}" )
        parser = lark.Lark(_queryparser._orderby_grammar, start='sort_terms', debug=False)
        tree = parser.parse(orderbystring)
        xformer = _queryparser._ParseTreeToOSLCOrderBySelect( resolverobject=self)
        orderbys = xformer.transform(tree)
        return orderbys, xformer.prefixes

    #
    # parse an oslc.select statement, substituting URIs for human-friendly names
    # refer to OSLC Query 3.0 section 7.4 https://tools.oasis-open.org/version-control/svn/oslc-core/trunk/specs/oslc-query.html
    #
    def _parse_select(self, selectstring, verbose=False):
        logger.info( f"{selectstring=}" )
        parser = lark.Lark(_queryparser._select_grammar, start='select_terms', debug=False)
        tree = parser.parse(selectstring)
        xformer = _queryparser._ParseTreeToOSLCOrderBySelect( resolverobject=self )
        selects = xformer.transform(tree)
        return selects, xformer.prefixes

