# IBM Engineering Lifecycle Management DOORS Next module structure API example using elmclient


 Example of using the DOORS Next Module Structure API


 (c) Copyright 2021- IBM Inc. All rights reserved
 
 SPDX-License-Identifier: MIT



Introduction
============

This code provides a hard-coded example of finding a module and then accessing the module structure.

Being hardcoded means there is no distracting commandline argument parsing :-)
The aim of this code is to provide command-line, automatable, access to the Reportable REST APIs of DOORS Next, EWM and ETM.


Installation
============

The `dn_simple_modulestructure.py` file is in the elmclient/examples folder after installing `elmclient`.


Usage
=====


You probably need to edit the file to setup harcoded parameters on (currently) lines 32-43. Make sure you capitalize and space these names *precisely* as they appear in the browser.

```
jazzhost = 'https://jazz.ibm.com:9443'
    
username = 'ibm'
password = 'ibm'

jtscontext = 'jts'
rmcontext  = 'rm'

proj = "rm_optout_p1"
comp = proj
conf =  f"{comp} Initial Stream"
mod = "AMR Stakeholder Requirements Specification"
```

Then run the file.

NOTE: As you're embedding your password in the file you may want to remove it after using the code. It's easy to make a runtime request for the password, for exmaple by replacing:

```
password = 'ibm'
```

with something like:

```
import getpass
password = getpass.getpass( "ELM password?" )
```

