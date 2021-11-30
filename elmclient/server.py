##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import collections
import datetime
import logging
import os.path
import pickle
import requests
import socket
import shutil
import time
import urllib
import urllib3

from . import _app
from . import utils
from . import httpops

logger = logging.getLogger(__name__)

CACHE_FOLDER = '.web_cache'
COOKIE_SAVE_FILE = ".cookies"
WEB_SAVE_FOLDER = "cache"

# The number of days to locally cache responses (can be extended by commandline, or disabled completely)
CACHEDAYS = 7

# this port will be checked for a proxy - if it is there, it will be used for all requests
# (The default proxy port for Telerik Fiddler is 8888)
PROXY_PORT = 8888

# this is the default proxy dictionary for Requests - this must be configured
# by the application code
proxydict = None

# Disable the InsecureRequestWarning so we can quietly control SSL certificate validation
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

##############################################################################################
# CacheControl setup

import cachecontrol as CC
import calendar
import cachecontrol.heuristics
import email.utils
import cachecontrol.caches.file_cache

class _AddDaysHeuristic(cachecontrol.heuristics.BaseHeuristic):
    def __init__(self,days):
        super().__init__()
        self.days = days

    def update_headers(self, response):
        date = email.utils.parsedate(response.headers['date'])
        expires = datetime.datetime(*date[:6]) + datetime.timedelta(days=self.days)
        return {
            'expires' : email.utils.formatdate(calendar.timegm(expires.timetuple())),
            'cache-control' : 'public',
        }

    def warning(self, response):
        msg = 'Automatically cached! Response is Stale.'
        return '110 - "%s"' % msg

##############################################################################################

def caching_save_creds(cachingcontrol):
#    return ( cachingcontrol < 2 )
    return False

def caching_save_data(cachingcontrol):
    return ( cachingcontrol < 2 )

def caching_wipe_cache(cachingcontrol):
    return ( cachingcontrol > 0 )


##############################################################################################

def setupproxy(url,proxyport=PROXY_PORT):
    # If a proxy is running on proxyport, setup proxydict so requests uses the proxy
    global proxydict
    if proxydict is None and proxyport!=0:
        # test if proxy is running
        if tcp_can_connect_to_url('127.0.0.1', proxyport, timeout=2.0):
            # Fiddler is running so setup proxy
            urlparts = urllib.parse.urlsplit(url)
            if urlparts.port:
                proxyurl = urlparts.scheme + "://" + urlparts.netloc[:urlparts.netloc.find(':')]
            else:
                proxyurl = urlparts.scheme + "://" + urlparts.netloc
            # insert the proxy dictionary
            proxydict = {
                            'https':'https://127.0.0.1:'+str(proxyport)
                            ,'http':'http://127.0.0.1:'+str(proxyport)
                        }
            logger.info( f'Setting proxy to {proxydict}' )

##############################################################################################

# utility to see if a port is active listening for connections
def tcp_can_connect_to_url(host, port, timeout=5):
    # create an INET, STREAMing socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # now connect to the web server on port
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False


#################################################################################################

# the server has two principle purposes:
# 1) to hold the server client connection, login user and password (and some other server-wide settings)
# 2) to hold some apps - at least a JTS - which share these server-wide settings

# this class is a common interface to provide Jazz server-level operations such as managing connections, provide http REST get/post etc.
# and understands how to transparently login the user to Jazz - the application code just makes the request, this manages the login
#  if it's needed

# caching control =0 for full caching, 1 to wipe the cache then use caching, 2 to wipe cache and disable caching

class JazzTeamServer( httpops.HttpOperations_Mixin ):
    def __init__(self, serverhostport, user, password, jtsappstring='jts', verifysslcerts=True, appstring=None, cachingcontrol=0, cachefolder=CACHE_FOLDER):
        logger.info( f"Creating server {appstring=} {jtsappstring=} {verifysslcerts=} {cachingcontrol=}" )
        self.verifysslcerts = verifysslcerts
        self.username = user
        self.password = password
        self.baseurl = serverhostport
        self.__user = user
        self.__password = password
        self.jts = None
        self.auto_retry = True
        self.cachingcontrol = cachingcontrol # 0=caching, 1=wipe cache then cache, 2= no caching
        self.headers = None
        self.cachefolder = cachefolder
        self.apps = []
        self._session = None

        # setup the session
        self._session = JazzTeamServer.__get_client(user, password,cachingcontrol=cachingcontrol, cachefolder=self.cachefolder)
        self._session.verify = verifysslcerts
        self._session.auto_retry = self.auto_retry
        self._session.cachingcontrol = self.cachingcontrol # 0=caching, 1=wipe cache then cache, 2= no caching

        if not hasattr(self._session,'is_authenticated'):
            self._session.is_authenticated = False

        # create any requested apps
        if jtsappstring:
            self.jts = self.add_app(jtsappstring)
            if appstring is not None:
                if type(appstring)==str:
                    if "," in appstring:
                        appstring = appstring.split(",")
                    else:
                        appstring=[appstring]
                elif type(appstring)!=list:
                    raise Exception( "appstring must be either a string of one or multiple comma-separated appstrings, or a list of single appstrings" )
                for app in appstring:
                    self.add_app(app)
        else:
            if appstring:
                raise Exception( f"You can't add app '{appstring}' because you haven't specified the jts appstring" )


    def get_user_password(self, url=None):
        return (self.__user, self.__password)

    def find_app(self, appstring, ok_to_create=False):
        domain,contextroot = self.get_appstring_details(appstring)
        for app in self.apps:
            if app.domain == domain and app.contextroot==contextroot:
                return app
        if ok_to_create:
            return self.add_app(appstring)
        return None

    # app factory
    def add_app(self, appstring):
        logger.info( f"Adding app {appstring=}" )
        domain,contextroot = self.get_appstring_details(appstring)
        # this is a factory for the different apps
        for app in _app._App.__subclasses__():
            if app.domain == domain:
                thisapp = app(self, contextroot=contextroot, jts=self.jts)
                self.apps.append(thisapp)
                return thisapp
        raise Exception(f"Domain '{domain}' not recognized")

#    # used to locate the app for the uri
#    # this is tentative code to allow e.g. links from ccm to rm in query results from ccm to be looked up in rm to get the requirement ID
#    # HOWEVER there's a design problem to solve; how to get the config (maybe require a GC)
#    # AND (much more difficult) how to get a project-like context (when we don't know the project/component) to provide headers
#    def find_app_for_uri( self, uri ):
#        print( f"fafu {uri=}" )
#        if not uri.startswith( self.reluri() ):
#            return None
#        for app in self.apps:
#            print( f"{app.reluri()=}" )
#            if uri.startswith( app.reluri() ):
#                print( f"Found {uri=} {app=}" )
#                return app
#        return None

    # return the absolute URI for a relative URI
    def reluri(self, reluri=''):
        return urllib.parse.urljoin(self.baseurl,reluri)

    # a note about 'appstring':
    #
    # This code is intended to handle general rm/ccm/qm/etc. domains and to be able to handle con-default context roots like /rm23
    # so introduced the idea of an appstring
    #
    # An appstring allows specifying for an app what domain it is (i.e. strictly rm,qm,ccm,gc, etc.), and it's relative uri e.g. /rm1
    # with sensible defaults so it's easy to specify rm on the default /rm by just specifying appstring "rm"
    #
    # appstring is "domain[:(reluri|partialuri)]"
    # so "rm"=>domain rm, context root /rm
    # rm:rm2=>domain rm, context root /rm2
    # ALSO "rm1"=>domain rm, context root /rm1 (domain rm is deduced by taking the first part of the string which is an allowed domain)
    #
    # If you really really wanted to access rm as e.g. /qm1, you'll have to specify rm:qm1
    #
    @staticmethod
    def get_appstring_details(appstring):
        ''' returns (domain,contextroot)'''
        # get the domains of the classes that inherit from _App
        allowed_domains = [a.domain for a in _app._App.__subclasses__()]
        res = appstring.split(":", 1)
        if len(res) < 2:
            if res[0] not in allowed_domains:
                # check for the start of the string being an allowed domain to allow e.g. rm1 is in domain rm
                for dom in allowed_domains:
                    if res[0].startswith(dom):
                        # copy e.g. rm1 as the context root /rm1
                        res.append(res[0])
                        # assert the domain
                        res[0] = dom
            else:
                # the domain is the context root
                res.append(res[0])
        if res[0] not in allowed_domains:
            raise Exception( f"Domain {res[0]} is not in the allowed domains {str(allowed_domains)}" )
        return res

    '''The interface to a Jazz server - handles all HTTP requests'''
    __shared_client_cache = collections.OrderedDict()

    @staticmethod
    def __get_client(username, password, ignorecache=False,cachingcontrol=0, cachefolder=CACHE_FOLDER):
        '''Get shared client session (one using same user/password)'''
        key = (username, password)
        result = JazzTeamServer.__shared_client_cache.get(key)

        if result is not None and ignorecache:
            # force removal of the existing client and starting a new one
            del JazzTeamServer.__shared_client_cache[key]
            result = None

        cacheexpiry = CACHEDAYS

        if result is None:
            # create a new session

            if caching_wipe_cache(cachingcontrol):
                # uncached data
                # if there is an existing data cache remove it
                if os.path.isdir(os.path.join(cachefolder,WEB_SAVE_FOLDER)):
                    logger.info( f"Erasing existing cache" )
                    shutil.rmtree(os.path.join(cachefolder,WEB_SAVE_FOLDER))
                    time.sleep(1.0)

            if caching_save_data(cachingcontrol):
                # cached - create folder for cache
                webcachefolder = os.path.join(cachefolder,WEB_SAVE_FOLDER)
                os.makedirs(webcachefolder,exist_ok=True)
                # cache to file with the CC heuristic to make responses persist for a number of days
                result = CC.CacheControl(requests.Session(), heuristic=_AddDaysHeuristic(cacheexpiry), cache=CC.caches.file_cache.FileCache(webcachefolder))
                # restore cookies saved after previous login, perhaps we'll avoid having to re-login
            else:
                # use an ordinary session
                result = requests.session()

            if caching_save_creds(cachingcontrol):
                # if credentials are being cached, load them from previous session
                # from https://stackoverflow.com/questions/13030095/how-to-save-requests-python-cookies-to-a-file
                os.makedirs(cachefolder,exist_ok=True)
                if os.path.isfile(os.path.join(cachefolder,COOKIE_SAVE_FILE)):
                    with open(os.path.join(cachefolder,COOKIE_SAVE_FILE), 'rb') as f:
                        result.cookies.update(pickle.load(f))
            else:
                # remove any saved cookies from previous login
                if os.path.isfile(os.path.join(cachefolder,COOKIE_SAVE_FILE)):
                    os.remove(os.path.join(cachefolder,COOKIE_SAVE_FILE))

            JazzTeamServer.__shared_client_cache[key] = result

        # ensure proxies are setup
        result.proxies = proxydict
        result.username = username
        result.password = password
        return result

    @staticmethod
    def clear_client_cache():
        JazzTeamServer.__shared_client_cache = collections.OrderedDict()

    # get local headers
    def _get_headers(self, headers=None):
        logger.info( f"server_gh" )
        result = {}
        if self.headers is not None:
            result.update(self.headers)
        if headers is not None:
            result.update(headers)
        logger.info( f"server_gh {result}" )
        return result

#    # get a request with local headers
#    def _get_request(self, verb, reluri='', *, params=None, headers=None, data=None):
#        fullheaders = self._get_headers()
#        if headers is not None:
#            fullheaders.update(headers)
#        sortedparams = None if params is None else {k:params[k] for k in sorted(params.keys())}
#        request = httpops.HttpRequest( self.app.server._session, verb, self.reluri(reluri), params=sortedparams, headers=fullheaders, data=data)
#        return request



