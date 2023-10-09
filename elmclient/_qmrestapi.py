##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

# this is a start of implementing the ETM REST API - it's very incomplete!

import logging

import lxml.etree as ET

from . import rdfxml
from . import utils

logger = logging.getLogger(__name__)

#################################################################################################

class QM_REST_API_Mixin():
    def __init__(self,*args,**kwargs):
        self.typesystem_loaded = False
        self.has_typesystem=True
        self.clear_typesystem()
        self.alias = None
    
    def get_alias( self ):
        if not self.alias:
            # GET the alias
            projects_x = self.execute_get_rdf_xml( f"service/com.ibm.rqm.integration.service.IIntegrationService/projects" )
            self.alias = rdfxml.xmlrdf_get_resource_text( projects_x, f".//atom:entry/atom:title[.='{self.name}']/../atom:content/qm_ns2:project/qm_ns2:alias" )
#            print( f"{self.alias=}" )
        return self.alias
    
    def find_testplan( self, name ):
        pass
        
    def find_testcase( self, name ):
        pass

    def find_testexecturionrecord( self, name ):
        pass

