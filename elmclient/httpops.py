##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

import codecs
import html.parser
import http
import inspect
import json
import logging
import lxml.etree as ET
import re
import time
import urllib

import requests
import tqdm

from elmclient import rdfxml

logger = logging.getLogger(__name__)


##############################################################################################
# utilities for text<>binary and encoding handling

# find the encoding of a response
def find_encoding(response, encoding):
    if isinstance(encoding, str):
        encoding = encoding
    elif encoding is None and (
        isinstance(response, requests.Response) or isinstance(response, requests.models.Response)):
        encoding = response.encoding
    elif encoding is None:
        pass
    else:
        raise Exception('Unknown encoding type [%s]' % encoding)
    if encoding is None:
        encoding = 'utf-8'  # default
    if "7bit" == encoding:
        encoding = 'us-ascii'
    return encoding

# decode response text
def to_text(response, encoding=None, errors='replace'):
    if response is None or isinstance(response, str):
        return response

    if isinstance(response, requests.models.Response) or isinstance(response, requests.Response):
        return response.text

    encoding = find_encoding(response, encoding)

    if isinstance(response, bytes) or isinstance(response, bytearray):
        content = response
    else:
        raise Exception()

    if "7bit" == encoding:
        encoding = 'us-ascii'

    try:
        if encoding is None:
            result = codecs.decode(content, errors=errors)
        else:
            result = codecs.decode(content, encoding=encoding, errors=errors)
    except:
        raise
    return result

def to_text_strict(response, encoding=None):
    return to_text(response, encoding, 'strict')

# encode to binary for XML
def to_binary_xml(text, encoding=None, errors='xmlcharrefreplace'):
    if isinstance(text, bytes) or isinstance(text, bytearray):
        return text
    encoding = find_encoding(None, encoding)
    result = codecs.encode(text, encoding, errors)
    return result

# encode to binary for non-XML strings
def to_binary(text, encoding=None, errors='strict'):
    if isinstance(text, bytes) or isinstance(text, bytearray):
        return text
    encoding = find_encoding(None, encoding)
    if encoding is None:
        result = codecs.encode(text, errors=errors)
    else:
        result = codecs.encode(text, encoding=encoding, errors=errors)
    return result

#################################################################################################

def getcookievalue( cookies, cookiename, defaultvalue=None):
    print( f"gcv {cookies=} {cookiename=} {defaultvalue=}" )
    for c in cookies:
        if c.name == cookiename:
            print( f"Found {cookiename} {c.value}" )
            return c.value
    print( f"Not found {cookiename}" )
    return defaultvalue

##############################################################################################

class _FormParser(html.parser.HTMLParser):
    '''This is a utility class to parse a login form to identify the login location'''
    def __init__(self):
        super().__init__()
        self.is_in_form = False
        self.method = None
        self.action = None
        self.name = 'j_username'
        self.passwrod = 'j_password'

    def handle_starttag(self, tagname, attrs):
        if tagname.lower() == 'form':
            self.is_in_form = True
            for a in attrs:
                if a[0].lower() == 'action':
                    self.action = a[1]
                elif a[0].lower() == 'method':
                    self.method = a[1]
        elif self.is_in_form:
            pass


class HttpOperations_Mixin():
    ############################################################################
    # methods for HTTP operations
    def __init__(self,*args,**kwargs): # only needed for mixins initialisation because other parent/mixins may have params, this ignores them
        super().__init__()

    def execute_get_xml(self, reluri, *, params=None, headers=None, **kwargs):
        reqheaders = {'Accept': 'application/xml'}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_get_request(reluri=reluri, params=params, headers=reqheaders)
        response = request.execute( **kwargs )
        result = ET.ElementTree(ET.fromstring(response.content))
        return result

    # this can also return a tuple including the etag if you will need it to update the artifact
    def execute_get_rdf_xml(self, reluri, *, params=None, headers=None, return_etag = False, **kwargs):
        if params is None:
            params = {}
        reqheaders = {'Accept': 'application/rdf+xml', 'OSLC-Core-Version': '2.0'}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_get_request(reluri=reluri, params=params, headers=reqheaders)
        response = request.execute( **kwargs )
        result = ET.ElementTree(ET.fromstring(response.content))
        if return_etag:
            return (result,response.headers['ETag'])
        return result

    # assumes you included the If-Match: ETag header!
    def execute_put_rdf_xml(self, reluri, *, data=None, params=None, headers=None, **kwargs):
        reqheaders = {'Accept': 'application/xml', 'Content-Type': 'application/rdf+xml'}
        if headers is not None:
            reqheaders.update(headers)
        if type(data)!=str:
            data = ET.tostring(data)
        request = self._get_post_request(reluri=reluri, data=data, params=params, headers=reqheaders, put=True)
        response = request.execute( **kwargs )
        return response

    def execute_post_rdf_xml(self, reluri, *, data=None, params=None, headers=None, put=False, **kwargs):
        reqheaders = {'Accept': 'application/xml', 'Content-Type': 'application/rdf+xml'}
        if headers is not None:
            reqheaders.update(headers)
        if type(data)!=str:
            data = ET.tostring(data)
        request = self._get_post_request(reluri=reluri, data=data, params=params, headers=reqheaders, put=put)
        response = request.execute( **kwargs )
        return response

    def execute_post_json(self, reluri, *, data=None, params=None, headers=None, put=False, **kwargs):
        reqheaders = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        if headers is not None:
            reqheaders.update(headers)
        if type(data)==dict or type(data)==list:
            data = json.dumps(data)
        elif type(data) != str:
            raise Exception( "Wrong type!" )
        request = self._get_post_request(reluri=reluri, data=data, params=params, headers=reqheaders, put=put)
        response = request.execute( **kwargs )
        return response

    def execute_delete(self, reluri, *, params=None, headers=None, **kwargs):
        reqheaders = {'Accept': 'application/xml', 'Content-Type': 'application/rdf+xml'}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_delete_request(reluri=reluri, params=params, headers=reqheaders)
        response = request.execute( **kwargs )
        return response

    def execute_get_json(self, reluri, *, params=None, headers=None, **kwargs):
        reqheaders = {'Accept': 'application/json'}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_get_request(reluri=reluri, params=params, headers=reqheaders)
        response = request.execute( **kwargs )
        result = json.loads(response.content)
        return result

    def execute_get_binary( self, reluri, *, params=None, headers=None, **kwargs):
        reqheaders = {}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_get_request(reluri=reluri, params=params, headers=reqheaders)
        response = request.execute( **kwargs )
        return response

    def execute_post_content( self, uri, *, params=None, data=None, headers={}, put=False, **kwargs):
        logger.debug("+++++++++++++++++++")
        data = data if data is not None else ""
        reqheaders = {}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_post_request(str(uri), data=data, headers=reqheaders)
        if put:
            request.method = "PUT"
        response = request.execute( **kwargs )
        logger.debug("-----------------")
        return response

    def execute_get(self, reluri, *, params=None, headers=None, **kwargs):
        reqheaders = {}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_get_request(reluri=reluri, params=params, headers=reqheaders)
        response = request.execute( **kwargs )
        result = response.content
        return result

    # return the response (used to get at response headers such as etag)
    def execute_get_raw(self, reluri, *, params=None, headers=None, **kwargs):
        reqheaders = {}
        if headers is not None:
            reqheaders.update(headers)
        request = self._get_get_request(reluri=reluri, params=params, headers=reqheaders)
        response = request.execute( **kwargs )
        return response

    def wait_for_tracker( self, location, *, interval=1.0, progressbar=False, msg='Waiting for tracker' ):
        verdict = None
        if progressbar:
            pbar = tqdm.tqdm(initial=0, total=100,smoothing=1,unit=" results",desc=msg)
            donelasttime=0
        while True:
            response_x = self.execute_get_rdf_xml( location, cacheable=False, intent="Poll tracker until result shows completiom" )
            percent = rdfxml.xmlrdf_get_resource_text( response_x, './/dng_task:percentage' )
            if progressbar:
                if percent is not None:
                    pbar.update(int(percent)-donelasttime)
                    donelasttime = int(percent)
                else:
                    pbar.update(donelasttime)
                
            # check for "complete" status
            if rdfxml.xmlrdf_get_resource_uri( response_x, ".//oslc_auto:state[@rdf:resource='http://open-services.net/ns/auto#complete']" ) is not None:
                if rdfxml.xmlrdf_get_resource_uri( response_x, ".//oslc_auto:verdict[@rdf:resource='http://open-services.net/ns/auto#error']" ) is not None:
                    status = rdfxml.xmlrdf_get_resource_text( response_x, ".//oslc:statusCode" ) or "NO STATUS CODE"
                    message = rdfxml.xmlrdf_get_resource_text( response_x, ".//oslc:message" ) or "NO MESSAGE"
                    verdict = f"{status} {message}"
                else:
                    verdict = response_x
                break
            time.sleep( interval )
        if progressbar:
            pbar.close()
        logger.info( f"Returning task tracker {verdict=}" )
        return verdict

    # record an action in the log
    def record_action( self, action ):
        # this allows splitting out each request+response when parsing the log
        logtext = "\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>!\n"
        logtext += f"\nACTION: {action}\n\n"
        # this allows splitting out each request+response when parsing the log
        logtext += "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<!\n"
        logger.trace(logtext)

    ###########################################################################
    # below here is internal implementation

    def _get_get_request(self, reluri='', *, params=None, headers=None):
        return self._get_request('GET', reluri, params=params, headers=headers)

    def _get_post_request(self, reluri='', *, params=None, headers=None, data=None, put=False ):
        if put:
            return self._get_request('PUT', reluri, params=params, headers=headers, data=data)
        return self._get_request('POST', reluri, params=params, headers=headers, data=data)

    def _get_delete_request(self, reluri='', *, params=None, headers=None ):
        return self._get_request('DELETE', reluri, params=params, headers=headers)


class HttpRequest():
    def __init__(self, session, verb, uri, *, params=None, headers=None, data=None):
        # Requests encoding of parameters uses + for space - we need it to use %20!
        if params:
            paramstring = f"?{urllib.parse.urlencode( params, quote_via=urllib.parse.quote, safe='/')}"
        else:
            paramstring = ""

#        self._req = requests.Request( verb,uri, params=params, headers=headers, data=data )
        self._req = requests.Request( verb,uri+paramstring, headers=headers, data=data )
        self._session = session

    def get_user_password(self, url=None):
        return ( self._session.username, self._session.password )

    def execute( self, no_error_log=False, close=False, **kwargs ):
        return self._execute_request( no_error_log=no_error_log, close=close, **kwargs )

    # execute the request, retrying with increasing delays (login isn't handled at this level but at lower level)
    def _execute_request( self, *, no_error_log=False, close=False, cacheable=True, **kwargs ):
        for wait_dur in [2, 5, 10, 0]:
            try:
                if not cacheable:
                    # add a header so the response isn't cached
                    self._req.headers['Cache-Control'] = "no-store, max-age=0"
                result = self._execute_one_request_with_login( no_error_log=no_error_log, close=close, **kwargs)
                return result
            except requests.RequestException as e:
                if wait_dur == 0 or not self._is_retryable_error(e):
                    raise
                logger.info( f"Got error on HTTP request. URL: {self._req.url}, {e.response.status_code}, {e.response.text}")
                logger.warning( f'RETRY: Retry after {wait_dur} seconds... URL: {self._req.url}' )
                time.sleep(wait_dur)
        raise Exception('programming error this point should never be reached')
        
    # log a request/response, which may be the result of one or more redirections, so first log each of their request/response
    def log_redirection_history( self, response, intent, action=None, donotlogbody=False ):
        thisintent = intent
        after = ""
        for i,r in enumerate(response.history):
            after= " (after redirects)"
            logger.trace( f"\nWIRE: redir {i} request +++++ {r.request.method} {r.request.url}\n\n{self._log_request(r.request,intent=thisintent,donotlogbody=donotlogbody)}")
            logger.trace(f"\nWIRE: redir response ----- {r.status_code}\n\n{self._log_response(r)}")
            thisintent = 'Redirection of '+intent
        logger.trace( f"\nWIRE: request +++++ {response.request.method} {response.request.url}\n\n{self._log_request(response.request,intent=intent+after,donotlogbody=donotlogbody)}")
        logger.trace(f"\nWIRE: response ----- {response.status_code}\n\n{self._log_response(response, action=action)}")

    # generate a string for logging of a http request with a stacktrace of the collers and showing URL, headers and any data
    def _log_request( self, request, donotlogbody=False, intent=None, action=None ):
        logtext = self._callers()
        # this allows splitting out each request+response when parsing the log
        logtext += "\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>!\n"
        if intent is not None:
            logtext += f"\n\nINTENT: {intent}\n\n"
            
        if donotlogbody:
            # redact username/password parameter values
            # unparse the url
            url_parts = list(urllib.parse.urlparse(request.url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            if 'j_username' in query:
                query['j_username'] = "REDACTED"
            if 'j_password' in query:
                query['j_password'] = "REDACTED"
            url_parts[4] = urllib.parse.urlencode(query)
            # reconstruct the possibly-redacted URL
            query_url = urllib.parse.urlunparse(url_parts)        
            logtext += f"{request.method} {query_url}\n"
        else:
            logtext += f"{request.method} {request.url}\n"
            
        for k in sorted(request.headers.keys()):
            logtext += "  " + k + ": " + to_text(request.headers[k]) + "\n"
        if hasattr(request, 'cookies'):
            cjd = requests.utils.dict_from_cookiejar(request.cookies)
            for k in sorted(cjd.keys()):
                logtext += "  Cookie " + k + ": " + cjd[k] + "\n"
        # add the body
        if request.body is not None:
            if donotlogbody:
                rawtext = "BODY REDACTED"
            elif len(request.body) > 1000000:
                rawtext = "LONG LONG CONTENT NOT SHOWN..."
            else:
                rawtext = repr(request.body)[1:-1]
                if len(rawtext) > 0:
                    if rawtext[0] == '<' or rawtext[0] == '{':
                        rawtext = re.sub(r"\\n", "\n", rawtext)
                        rawtext = re.sub(r"\\t", "    ", rawtext)
            # the surroundings allow splitting out the request body when parsing the log
            logtext += "\n::::::::::=\n"
            logtext += "\n" + rawtext + "\n\n"
            logtext += "\n----------=\n"
            
        # add the subsequent action (e.g. use of the response?)
        if action is not None:
            logtext += f"\n\nACTION: {action}\n\n"

        return logtext

    # generate a compact stacktrace of function-line-file because it's often
    # helpful to know how the HTTP operation was called
    def _callers( self ):
        caller_list = []
        # get the stacktrace and do a couple of f_back-s to remove the call to this function and to the _log_request()/_log_response() function
        frame = inspect.currentframe().f_back.f_back
        while frame.f_back:
            caller_list.append(
                '{2}:{1}:{0}()'.format(frame.f_code.co_name, frame.f_lineno, frame.f_code.co_filename.split("\\")[-1]))
            frame = frame.f_back
        callers = ' <= '.join(caller_list)
        return callers

    # generate a string for logging of a http response showing response code, headers and any data
    def _log_response( self, response, action=None ):
        logtext = f"Response: {response.status_code}\n"
        # use the urllib3 cookiejar so Set-Cookie-s don't get folded into one single unparseable value by Requests
        # see https://github.com/psf/requests/issues/3957
        cs = response.raw.headers.items()
        for c,v in sorted(cs):
            logtext += "  " + c + ": " + v + "\n"
            
        # add the body
        if response.content is not None:
            if len(response.content) > 1000000:
                rawtext = "LONG LONG CONTENT..."
            else:
                rawtext = repr(response.content)[2:-1]
                if len(rawtext) > 0:
                    if rawtext[0] == '<' or rawtext[0] == '{':
                        rawtext = re.sub(r"\\r", "", rawtext)
                        rawtext = re.sub(r"\\n", "\n", rawtext)
                        rawtext = re.sub(r"\\t", "    ", rawtext)
            # the surroundings allow splitting out the response body when parsing the log
            logtext += "\n::::::::::@\n"
            logtext += rawtext 
            logtext += "\n----------@\n\n"

        # record the action  taken by the caller using the response
        if action:
            logtext += f"\n\nACTION: {action}\n\n"
        
        # this allows splitting out each request+response when parsing the log
        logtext += "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<!\n"
        return logtext

    # categorize a Requests .send() exception e as to whether is retriable
    def _is_retryable_error( self, e ):
        if self._session.auto_retry:
            if e.response.status_code in [
                                                http.client.REQUEST_TIMEOUT,
                                                http.client.LOCKED, 
#                                                http.client.INTERNAL_SERVER_ERROR,
                                                http.client.SERVICE_UNAVAILABLE,
 #                                               http.client.BAD_REQUEST
                                        ]:
                return True
        return False
        
    def get_auth_path(self, request_url, response):
        request_url_parsed = urllib.parse.urlparse(request_url)
        form_auth_path = [c.path for c in response.cookies if c.name == 'JazzFormAuth']
        auth_app_context = form_auth_path[0] if len(form_auth_path) == 1 else request_url_parsed.path.split('/')[1]
        return auth_app_context
        
        
    def tidy_cookies(self):
        '''
        LQE 7.0.2SR1 and 7.0.3 has the unpleasant habit of including double-quotes in the auth cookie path so it looks like "/lqe" (which includes the quotation marks in the path) rather than /lqe, and then the path is never matched so authentication is lost
        This code cleans up the path on all cookies on the session4
        # return True if any cookie changed
        '''
        result = False
        for cookie in self._session.cookies:
            if cookie.path.startswith('%22'):
                oldvalue = cookie.path
                cookie.path = cookie.path.replace("%22","")
                logger.debug( f"REVISED cookie {cookie.name} path {oldvalue} to {cookie.path=}" )
                result = True
        return result


    # execute a request once, except:
    #  1. if the response indicates login is required then login and try the request again
    #  2. if request is rejected for various reasons retry with the CSRF header applied
    # supports Jazz Form authorization and Jazz Authorization Server login
    def _execute_one_request_with_login( self, *, no_error_log=False, close=False, donotlogbody=False, retry_get_after_login=True, remove_headers=None, remove_parameters=None, intent=None, action = None ):
#        if intent is None:
#            raise Exception( "No intent provided!" )
        intent = intent or ""
        action = action or ""
        retry_after_login_needed = False
        logger.debug( f"{retry_get_after_login=}" )
        request = self._req
        # copy header Configuration-Context to oslc_config.context parameter so URL when cached is config-specific
        # see https://oslc-op.github.io/oslc-specs/specs/config/config-resources.html#configcontext
        if request.headers.get('Configuration-Context'):
            # if Configuration-Context is not None:
#            print( f"Copied header Configuration-Context to parameter oslc_config.context" )
            request.params['oslc_config.context'] = request.headers['Configuration-Context']
        
        # ensure keep-alive/close
        if close:
            request.headers['Connection'] = 'close'
        else:
            request.headers['Connection'] = 'keep-alive'

        # this is for generic API debugging to be able to remove any parameter before it's actually sent!
        if remove_parameters:
            for p in remove_parameters:
                if p in request.params:
                    del request.params[p]
                    logger.info( f"Removed param {p}" )

        # this is for generic API debugging to be able to remove any header before it's actually sent!
        if remove_headers:
            for h in remove_headers:
#                print( f"{request.headers=}" )
                if h in request.headers:
                    del request.headers[h]
                    logger.info( f"Removing header {h}" )
                    request.headers[h]=None

        # actually (try to) do the request
        try:
            prepped = self._session.prepare_request( request )
            response = self._session.send( prepped )
                                                 
            self.log_redirection_history( response, intent=intent, action=action )

            response.raise_for_status()

            # check for a non-error response which also indicates that authentication is needed using
            # a special header (in which case the response is not the data requested)
            if 'X-com-ibm-team-repository-web-auth-msg' in response.headers:
                if response.headers['X-com-ibm-team-repository-web-auth-msg'] == 'authrequired':
                    logger.trace("WIRE: auth required")
                    self._session.is_authenticated = False
                    response = self._jazz_form_authorize(request.url, request, response)
                    self._session.is_authenticated = True
                    logger.trace("WIRE: auth done - retrying")
                    retry_after_login_needed = True

        except requests.HTTPError as e:
            if not no_error_log:
                logger.trace( f"HTTPError {e}" )
            if e.response.status_code == 401 and 'X-jazz-web-oauth-url' in e.response.headers:
                logger.trace("WIRE: need non-JAS login")
                self._session.is_authenticated = False
                auth_url = e.response.headers['X-jazz-web-oauth-url']
                login_response = self._login(auth_url)
                                   
                if login_response:
                    logger.trace("WIRE: NOT retrying")
                    response = login_response
                else:
                    logger.trace("WIRE: retrying")
                    logger.trace( f"Auth completed (in theory) result - 1" )
                                                                     
                    retry_after_login_needed = True
            elif e.response.status_code == 401 and 'X-JSA-AUTHORIZATION-REDIRECT' in e.response.headers:
                logger.trace("WIRE: JAS Login required!")
                if 'WWW-Authenticate' not in e.response.headers:
                    raise Exception( "Login not possible because response has X-JSA-AUTHORIZATION-REDIRECT but no WWW-Authenticate header")
                else:
                    if e.response.headers['WWW-Authenticate'].find("JSA") < 0:
                        raise Exception( f"Non-JSA authentication not supported - WWW-Authenticate is '{e.response.headers['WWW-Authenticate']}'")

                self._session.is_authenticated = False
                auth_url = e.response.headers['X-JSA-AUTHORIZATION-REDIRECT']
                login_response = self._jsa_login(auth_url)
                self._session.is_authenticated = True
                if login_response:
                    logger.trace("WIRE: Response received after JAS login")
                    response = login_response
                    logger.trace( f"Auth completed (in theory) result - 2" )
                else:
                    logger.trace("WIRE: retrying after JAS login")
                    retry_after_login_needed = True
                    logger.trace( f"Auth completed (in theory) result - 3" )
            elif e.response.status_code in [410,406,404]:
                raise
            else:
                logger.trace( "WIRE: handle content-style auth redirect" )
                # Handle content-style or Javascript-style auth redirect
                body_content = e.response.text
                m = re.search('AuthRedirect\((.*?)\)', body_content)
                json_string = m and m.group(1)
                json_object = json_string and json.loads(json_string)
                auth_url = json_object and json_object.get('redirect')
                if auth_url:
                    self._session.is_authenticated = False
                    self._login(auth_url)
                    self._session.is_authenticated = True
                    retry_after_login_needed = True
                    logger.trace( "Retry needed" )
                    logger.trace( f"Auth completed (in theory) result - 4" )
                else:
                    if e.response.status_code == http.client.NOT_FOUND:
                        raise
                    if no_error_log or (( e.response.status_code == http.client.FORBIDDEN or e.response.status_code == http.client.CONFLICT) and body_content.find('X-Jazz-CSRF-Prevent')):
                        logger.trace( f"Failed to complete request. URL: {request.url}, {e.response.status_code}, {e.response.text}" )
                    else:
                        logger.error( f"Exception on executing request. URL: {request.url}, {e.response.status_code}, {e.response.text}" )
                    raise

        if retry_after_login_needed and ( request.method != "GET" or retry_get_after_login):
#            # completed login - save cookies! When run again, we try picking up these cookies, perhaps we'll avoid having to re-login
#            # from https://stackoverflow.com/questions/13030095/how-to-save-requests-python-cookies-to-a-file
#            if caching_save_creds(self.cachingcontrol):
#                os.makedirs(self.cachefolder, exist_ok=True)
#                with open(os.path.join(self.cachefolder,COOKIE_SAVE_FILE), 'wb') as f:
#                    pickle.dump(self._session.cookies, f)
            # now retry
            try:
                # have to build a new request which will get the (new) auth cookies
                # make sure this request isn't satisfied from cache!
                request.headers.update({'Cache-Control': 'no-cache'})
                prepped = self._session.prepare_request(request)
                response = self._session.send(prepped)
                self.log_redirection_history( response, intent="RETRY AFTER AUTHENTICATION "+intent, action=action )
                response.raise_for_status()
            except requests.HTTPError as e:
                logger.error( f"Exception on retrying request. URL: {request.url}, {e.response.status_code}, {e.response.text}")
                raise
        if 'X-com-ibm-team-repository-web-auth-msg' in response.headers:
            username, password = self.get_user_password(request.url)
            logger.error( f"Authorization Failure. Check user ID {username} and password for URL [{request.url}]" )
            raise Exception(
                'Authorization Failure in JazzClient with credentials [%s/%s].' % (username, '*' * len(password)))
        return response

    def _login(self, auth_url):
        '''Makes an initial get which is assumed to fail and will return
        the proper auth headers. After that, we can POST to the login service.'''
        if auth_url:
            # Access Auth URL
            
            auth_url_response = self._session.get(auth_url)  # Load up them cookies!
            self.log_redirection_history( auth_url_response, intent="Login",donotlogbody=True )

            if auth_url_response.headers.get('X-com-ibm-team-repository-web-auth-msg') != 'authrequired':
                logger.trace("headers show auth not required")
                return None  # no more auth required
            login_url = auth_url_response.url  # Take the redirected URL and login action URL
            self._authorize(login_url)
            
            logger.trace("authorized")
        else:
            logger.error('''Something has changed since this script was written. I can no longer determine where to authorize myself.''')
            raise Exception("Login not possible(1)!")

        try:
                
            # Now we should have the proper oauth cookies, so try again
            response = self._session.get(auth_url)
        except requests.exceptions.RequestException as e:
            logger.info( f"Failed to login to auth URL [{auth_url}] with exception [{e}]" )
            raise Exception("Login not possible(2)!")

    def _jsa_login(self, auth_url):
        # refer to https://jazz.net/wiki/bin/view/Main/NativeClientAuthentication#Open_ID_Connect_and_the_Jazz_Sec
        # (tested against a localUserRegistry JAS and a simple LDAP JAS)
        if auth_url:
            # Access Auth URL
            # step 1 - GET on auth_url with &prompt=none added
            auth_url_response = self._session.get(str(auth_url) + "&prompt=none")  # Load up them cookies!
            self.log_redirection_history( auth_url_response, intent="JAS Authorize step 1",donotlogbody=True )
            # step 2 - check for response indicating
            if auth_url_response.status_code != 200 or 'X-JSA-LOGIN-REQUIRED' not in auth_url_response.headers:
                return auth_url_response  # no more auth required
            if auth_url_response.headers['X-JSA-LOGIN-REQUIRED'] != 'true':
                raise Exception(
                    "login required is not true it is '%s'" % (auth_url_response.headers['X-JSA-LOGIN-REQUIRED']))
            # step 3 GET from auth_url (with nothing added)
            auth_url_response = self._session.get(str(auth_url))  # Load up them cookies!
            self.log_redirection_history( auth_url_response, intent="JAS Authorize step 3",donotlogbody=True )
            if auth_url_response.status_code == 200:
                login_url = auth_url_response.url  # Take the redirected URL and login action URL
                logger.debug( f"1 {login_url=}" )
                if auth_url != login_url:
                    content_text = to_text(auth_url_response)
                    #                 print content
                    auth_form_parser = _FormParser()
                    auth_form_parser.feed(content_text)
                    if auth_form_parser.action:
                        login_url = urllib.parse.urljoin(login_url, auth_form_parser.action)
                        logger.debug( f"2 {login_url=}" )
                self._authorize(login_url)
        else:
            logger.error('''Something about JSA OIDC login has changed since this script was written. I can no longer determine where to authorize myself.''')
            raise Exception("Authorize not possible (1)")

        try:
            # Now we should have the proper oauth cookies, so try again
            response = self._session.get(auth_url)
            response.text
        except requests.exceptions.RequestException as e:
            logger.info( f"Failed to login to OIDC auth URL [{auth_url}] with exception [{e}]" )
            raise Exception("Authorize not possible (2)")

    # general authorize
    def _authorize(self, auth_url):
        username, password = self.get_user_password(auth_url)
        data = {'j_username': username, 'j_password': password}
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Connection': 'keep-alive', 'Referer': auth_url}
        try:
            # JAS authentication uses a post
            request = requests.Request("POST",str(auth_url), headers=headers, data=data)
            prepped = self._session.prepare_request(request)

            response = self._session.send(prepped)
            self.log_redirection_history( response, intent="Authorize",donotlogbody=True )

            response.raise_for_status()
            if 'X-com-ibm-team-repository-web-auth-msg' in response.headers:
                if response.headers['X-com-ibm-team-repository-web-auth-msg'] == 'authrequired':
                    self._jazz_form_authorize(auth_url, request, response)
        except requests.HTTPError:
            # Same issue as in __login()
            pass

    # login using form
    def _jazz_form_authorize(self, request_url, prev_request, prev_response):
        request_url_parsed = urllib.parse.urlparse(request_url)
        form_auth_path = [c.path for c in prev_response.cookies if c.name == 'JazzFormAuth']
        auth_app_context = form_auth_path[0] if len(form_auth_path) == 1 else request_url_parsed.path.split('/')[1]
        username, password = self.get_user_password(request_url)
        auth_url = urllib.parse.urlunparse([request_url_parsed.scheme,
                                            request_url_parsed.netloc,
                                            auth_app_context + '/j_security_check',
                                            "",
                                            urllib.parse.urlencode({'j_username': username, 'j_password': password}),
                                            ""])
        try:

            response = self._session.get(auth_url)
            self.log_redirection_history( response, intent="Authenticate Form",donotlogbody=True )

        except requests.HTTPError as e:
            logger.info( f"Failed to jazz_authorize with auth URL {auth_url} with exception {e}" )  # was logger.error despite subsequent authentication success
            raise Exception("Jazz FORM authorize not possible!")
        return response
