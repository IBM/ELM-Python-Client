##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


#################################################################################################

# ENI/RELM application

#
# This is a skeleton implementation for ENI/RELM - just enough to support finding a project
#

#################################################################################################

import logging

import requests
import lxml.etree as ET
import tqdm

from . import _app
from . import _project
from . import _typesystem
from . import oslcqueryapi
from . import rdfxml
from . import server
from . import utils

logger = logging.getLogger(__name__)

#################################################################################################

class _RELMProject(_project._Project):
    def __init__(self, name, project_uri, app, is_optin=False, singlemode=False,defaultinit=False):
        super().__init__(name, project_uri, app, is_optin,singlemode, defaultinit=defaultinit)
        self.hooks = []
        self._components = None  # will become a dict keyed on component uri
        self._configurations = None # keyed on the config name
        self.default_query_resource = 'oslc_config:Configuration'


#################################################################################################

#@utils.mixinomatic
class RELMApp(_app._App):
    domain = 'relm'
    project_class = _RELMProject
    supports_configs = False
    supports_components = False
    supports_reportable_rest = False

    relprefixes = (
        )

#    identifier_name = 'Short ID'
#    identifier_uri = 'Identifier'

    def __init__(self, server, contextroot, jts=None):
        super().__init__(server, contextroot, jts=jts)

        self.rootservices_xml = self.execute_get_xml( self.reluri('rootservices'), intent="Retrieve RELM/ENI toot services" )
#        self.serviceproviders = 'gc:globalConfigServiceProviders'
#        self.default_query_resource = 'oslc_config:Configuration'
        # register some app-specific namespaces
        for prefix,reluri in self.relprefixes:
            rdfxml.addprefix(prefix,self.baseurl+reluri)
        self.hooks = []

    def _get_headers(self, headers=None):
        result = super()._get_headers()
        result['net.jazz.jfs.owning-context'] = self.baseurl
        if headers:
            result.update(headers)
        return result

