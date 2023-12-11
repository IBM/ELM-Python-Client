
##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# This mixin implements the validate API (will be used on each app that supports validate)
# ref https://jazz.net/rm/doc/scenarios

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


class Validate_Mixin():
    def listFeeds( self ):
        valuri = self.reluri( 'trs_feed_validation/feeds' )
#        print( f"{valuri=}" )
        results = self.execute_get_json( valuri, headers={'Accept': 'application/json' } )
        # 
#        print( f"{results=}" )
        return results
        
    def validate( self, feedid, *,  repair=False, resetIncrementalData=False, full=False ):
        valuri = self.reluri( 'trs_feed_validation/validate' )
        rep = 'true' if repair else 'false'
        res = 'true' if resetIncrementalData else 'false'
        ful = 'true' if full else 'false'
        response = self.execute_post_content( valuri, params={'id': feedid,'repair': rep,'resetIncrementData': res,'full': ful } )
#        print( f"{response=}" )
        
        # get the location
        location = response.headers.get('Location')
        
        # check for 202 and location
        if response.status_code == 202 and location is not None:
            print( f"Polling tracker at {location}" )
            # wait for the tracker to finished
            result = self.wait_for_tracker( location, interval=1.0, progressbar=True, msg=f"Validating feed {feedid}",useJson=True,returnFinal=True)
            # TODO: success result is now the xml of the verdict       
            # result None is a success!
            logger.info( f"1 {result=}" )
            return result
        else:
            raise Exception( f"Validate data source {id} failed!" )
            
