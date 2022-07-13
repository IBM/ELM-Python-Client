##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

import datetime
import logging
import re
import sys

import anytree
import dateutil.parser
import dateutil.tz
import lxml.etree as ET
import requests
import tqdm
import pytz

from . import _app
from . import _project
from . import _typesystem
from . import oslcqueryapi
from . import rdfxml
from . import server
from . import utils

#################################################################################################

logger = logging.getLogger(__name__)

#################################################################################################

BASELINE  = 1
STREAM    = 2
CHANGESET = 3

class _Config():
    configtype = None
    def __init__(self, *ags, **kwargs ):
        logger.info( f"Config init {self=}" )
        pass
    def is_stream(self):
        return self.configtype == STREAM
    def is_baseline(self):
        return self.configtype == BASELINE
    def is_changeset(self):
        return self.configtype == CHANGESET

class _Stream(_Config):
    configtype = STREAM
    from_baseline = None
    baselines = []
    changesets = []
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        
    def create_baseline(self):
        pass
    def create_changeset(self):
        pass
    pass

class _Baseline(_Config):
    configtype = BASELINE
    instream = None
    streams = []
    
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
    def create_stream(self):
        pass

class _Changeset(_Config):
    configtype = CHANGESET
    instream=None
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        
    def deliver(self):
        pass
    def discard(self):
        pass
        

