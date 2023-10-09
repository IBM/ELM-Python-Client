# Python client for IBM Enterprise Lifecycle Management applications


 Python client for IBM Enterprise Lifecycle Management applications


 (c) Copyright 2021- IBM Inc. All rights reserved
 
 SPDX-License-Identifier: MIT

 version="0.23.0"

What's New?
===========

0.23.0 16-Aug-2023
* tested with Python 3.11.4 - worked OOTB. Now developing using 3.11.4 - won't be back-tested with older Pythons but should work back to 3.9 at least.

0.23.0 4-May-2023
* Deprecated RM load_folders() - use find_folder() instead.
* Added RM create_folder() - this doesn't require doing a forced reload of all folders, because it inserts the new folder into the internal info about folders
* Added example dn_simple_createfolderpath.py - allows exercising the create_folders() function
* Added rm-only implementation of create/deliver changeset NOTE these aren't fully finished, specifically hte delivery result may not be obvious(!)
* Added example dn_simple_typesystemimport_cs.py which shows creating/delivering a changeset around typesystem import

Introduction
============

The aim of this code is to provide a Python client for the IBM Enterprise Lifecycle Management (ELM) applications.

IMPORTANT NOTES:
* This code is not developed, delivered or supported in any way as part of the IBM ELM applications
* This code is not supported other than by the efforts of the author and contributors in this github repository
* This code is not intended to be complete/comprehensive - it provides functionality needed by the examples and little else.

Included in this package are a few examples using `elmclient` which are reasonably functional:
* OSLC Query able to work with DOORS Next (DN), Engineering Test Management (ETM), Engineering Workflow Management (EWM) and Global Configuration management (GCM)
* ReqIF import/export for DOORS Next
* Basic Reportable REST for DOORS Next - very basic!
* More general Reportable REST, currently only for DOORS Next but intended to expand to cover EWM and ETM.

There are links to these examples below.

Installation
============

Either method of install described below installs the elmclient package and puts example commands (such as `oslcquery` into your path so a) they can be run simply by typing the command, e.g. `oslcquery` and b) as you edit the source code these commands automatically use the latest code.

Requirements: Python 3.11/3.10/3.9 - NOTE I'm developing using Python 3.11.4 and compatibility with older versions is NOT checked.

Overview
--------

Step 1: Install Python so it can be run from a command prompt
Either Step 2a: Quickest and easiest to get started: install elmclient from pypi
Or Step 2b: If you want to change elmclient code

Step 1
------

Install Python so you can run Python from the commandline - might be python3 if you're on *nix. On Windows the command is `python` - you can find install guides all over the internet.

Step 2a - Quickest and easiest to just use elmclient
----------------------------------------------------

This method is also easiest to update with new versions of elmclient.

at a command prompt:
* for Windows type `pip install elmclient`
* For *nix use `pip3 install elmclient`

To update:
* for Windows type `pip install -U elmclient`
* For *nix use `pip3 install -U elmclient`

Using this method you could copy the examples from where they're lurking in your Python installation's library to a different folder, rename if using one of the commands such as oslcquery to a different name, and edit them in this folder separate from the elmclient install.

Test that all was successful by running `oslcquery -h` you should get a version number then a swathe of text with all the options.


Step 2b - If you want to edit the code in elmclient
---------------------------------------------------

This method assumes you have developer knowledge how to modify and merge code.

By far the preferred method is to first fork the github repository. You'll then get a folder on your PC which has a sub-folder `elmclient'.

Open a command prompt in the folder which has a subfolder `elmclient` and run the command (Windows) `pip install -e .` or (*nix) `pip3 install -e .`

Test that all was successful by running `oslcquery -h` you should get a version number then a swathe of text with all the options.




Coding using the elmclient
==========================

You code will import elmclient, then use it.

The basis of using the elmclient is to first create a "server", then add the needed application(s) to it - typically just one application such as rm, or perhaps more applications such as rm and gc.

Then you can use the API functions to find projects, components, configurations, etc.

The DN reportable REST example provides a simple functional example with hard-coded values for the project, configuration and the artifact ID to be queried. This is the easy way to get into using elmclient - by modifying this example.

The other examples add fairly complex details around the use of elmclient to provide a commandline interface and should provide again a starting point for further development.


Authentication (in httpops.py)
==============================

The auth code works with:
* form authentication using Liberty in local user registry
* LDAP (using JTS setup for LDAP) and OIDC (Jazz Authorisation Server, which might be configured for LDAP)

Other authentication methods haven't been tested.

You'll have to provide a username and password; that username will determine the permissions to read/write data on your server, just as they would through a browser UI.

The examples `oslcquery` and `reqif_io` layer authentication enhancements on top of this to allow saving obfuscated credentials to a file so you don't have to provide these on the commandline every time. See the code for these examples.


Handling different context roots
================================

It's possible to install the ELM applications to run on non-standard context roots like /rm1 for DOORS Next, or /scm for EWM. This is handled in `elmclient` using APPSTRINGs. These specify the domain of an application using rm, jts, gc, ccm, qm, and the context root as a string without the leading /. So for example /rm1 would be specified as `rm:rm1`, or /scm would be specified as `ccm:scm`.

For example, if your DN is on /rm then just specify `rm`. Or, if it's on /rm23 then specify `rm:rm23`.

If more than one application is needed then use a comma separate list (without spaces). The main application is specified first, but if jts is also on /jts1 then your APPSTRING could be `rm:rm1,jts:jts1`.


Example code provided
=====================

These examples drove the evolution of `elmclient`:

* OSLC Query - read more [here](elmclient/examples/OSLCQUERY.md) - this is the largest example by quite a margin. It enables commandline export to CSV from the supported applications using an abstract syntax for OSLC Query - commandline options
* ReqIF import/export - read more [here](elmclient/examples/REQIF_IO.md) - this allows limited CRUD of reqif definitions in DOORS Next, performing multiple reqif export using a definition, and multiple reqif import - commandline options
* General Reportable REST export to XML/CSV - read more [here](elmclient/examples/REPREST.md) - currently only implemented for DOORS Next but with potential to expand to EWM and ETM - commandline options
* Simple Simple DOORS Next Module Structure API - read more [here](elmclient/examples/DN_SIMPLE_MODULESTRUCTURE.md) - Access a module structure and print out the indentend artifiact titles with section number - hardcoded
* Simple DOORS Next Reportable REST - read more [here](elmclient/examples/DN_REPREST.md) - this is a very simple example of using `elmclient` to access the DOORS Next Reportable REST API - hardcoded
* .. and more, check the examples folder...

ELM APIs
========

This code provides examples of using various ELM APIs:

* DN

** Process - `elmclient`

** OSLC including OSLC Query - `oslcquery.py` for user use, internally `oslcqueryapi.py` implements OSLC Query parsing and querying

** Module Structure - `dn_simple_modulestructure.py` - currently external to `elmclient`

** ReqIF - `reqif_io.py` - currently reqif API is external to `elmclient`

** Reportable REST (incomplete for qm and ccm) - `represt.py` for user use, internally for each application in `_rm.py`, `_ccm.py`, `_qm.py` 


* ETM

** Process - `elmclient`

** OSLC including OSLC Query - `oslcquery.py` for user use, internally `oslcqueryapi.py` implements OSLC Query parsing and querying

** Reportable REST (incomplete for qm and ccm) - `represt.py` for user use, internally for each application in `_rm.py`, `_ccm.py`, `_qm.py` 


* EWM

** Process - `elmclient`

** OSLC including OSLC Query - `oslcquery.py` for user use, internally `oslcqueryapi.py` implements OSLC Query parsing and querying

** Reportable REST (incomplete for qm and ccm) - `represt.py` for user use, internally for each application in `_rm.py`, `_ccm.py`, `_qm.py` 


* GCM

** Process - `elmclient`

** OSLC including OSLC Query - `oslcquery.py` for user use, internally `oslcqueryapi.py` implements OSLC Query parsing and querying


Reporting issues, and contributing
==================================

If you find a problem with elmclient you can report it on the github issues https://github.com/IBM/ELM-Python-Client/issues - note this is just for issues with elmclient code. All other issues will likely be closed immediately.

You can do a pull request to propose updates - there's no guarantee of if/when/how these will be merged but we certainly hope to benefit from contributions!
