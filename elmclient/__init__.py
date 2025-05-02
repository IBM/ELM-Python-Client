##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


from .server import *
from ._app import *
from ._project import *
from ._app import *
from ._project import *
from .oslcqueryapi import *
from ._typesystem import *
from ._ccm import *
from ._rm import *
from ._gcm import *
from ._qm import *
from ._relm import *
from .__meta__ import *
from .httpops import *

__app__ = __meta__.app
__version__ = __meta__.version
__license__ = __meta__.license
__author__ = __meta__.author

import importlib, os, inspect, glob

# scan for extensions to import and extend the specified class
# extensions are .py file with a name like <classname>-something.py e.g RMApp-extension.py
# the classes in the file are added as base classes to the extended class
# so it's dynamic mixins :-) A mixin may override existing methods
def load_extensions( *, path=None, folder=None ):
    path = path or os.getcwd()
    folder = folder or "extensions"
    
    # find public elmclient names+classes - these are extension points
    extendableclasses = {n:c for n,c in inspect.getmembers(importlib.import_module("elmclient"), inspect.isclass) }

    # look for extension files
    searchdir = os.path.join( path, folder )
    if os.access( searchdir, os.F_OK ):
        # folder doesn't exist - nothing to load
        pass
    else:
        files = glob.glob( os.path.join( searchdir, "**/*.py" ), recursive=True )
        for file in files:
            filename = os.path.split( file )[1]
            # get the extended class
            extended = filename.split( "-", 1 )[0]
            if extended not in extendableclasses:
                print( "No matching class to extend for {filename}" )
            else:
                extendedclass=extendableclasses[extended]
                # Import source file - from https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
                loader = importlib.machinery.SourceFileLoader( filename, file )
                spec = importlib.util.spec_from_loader( filename, loader )
                mymodule = importlib.util.module_from_spec( spec )
                loader.exec_module( mymodule )
                # find the classes in the extension
                extenderclasses = { n:c for n,c in inspect.getmembers( mymodule, inspect.isclass ) }
                # add them to the extended class so they precede (i.e. may override) the previous base classes
                for n,c in extenderclasses.items():
                    # add to bases
                    extendedclass.__bases__ = (c,)+extendedclass.__bases__


# load any local extensions
load_extensions( extendableclasses )


