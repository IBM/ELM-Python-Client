# IBM Engineering Lifecycle Management ReqIF import/export example using elmclient


 Commandline ReqIF import/export eaxample using elmclient


 (c) Copyright 2021- IBM Inc. All rights reserved
 SPDX-License-Identifier: MIT



Introduction
============

The aim of this code is to provide command-line, automatable, access to the reqif API of DOORS Next,.

This example is reasonably comprehensive. You can:
* Create, Update and Delete reqif definitions stored in a project+config - NOTE not all the possibilities for content of a reqif definition have been implemented, in particular views can't be added
* Import one or more reqif files
* Export one or more reqif files from existing reqif definitions

**IMPORTANT NOTE** ReqIF import and export are expensive operations on your server - you are responsible to manage the load these place on your server so as not to adversely affect the experience of other users or to jeopardise the server itself due to excessive load.

Installation
============

The `reqif_io` command is installed in your Python scripts folder when installing `elmclient`

TLDR;
=====

Here's a sequence which lists ReqIF definitons in a project, creates a new definition for a specific module, exports it to reqifz, reimports the reqifz, and then deletes the definition

NOTE this is so brief because it's using the defaults for server URL and context roots, username and password, because project `rm_optout_p1` doesn't have configuration management enabled - see below these sections for how to set these up for your environment.

NOTE this works when project `rm_optout_p1` was created using the `Systems Requirement Sample`, which has a module `AMR Stakeholder Specification`.


```
reqif_io rm_optout_p1 list
reqif_io rm_optout_p1 create stk -m "AMR Stakeholder Requirements Specification"
reqif_io rm_optout_p1 list
reqif_io rm_optout_p1 export stk
reqif_io rm_optout_p1 import stk.reqifz
reqif_io rm_optout_p1 delete stk
```


Usage
=====


To get all the usage options use `reqif_io -h` or `reqif_io --help`:

```
usage: reqif_io [-h] [-A APPSTRINGS] [-C COMPONENT] [-D DELAYBETWEEN] [-F CONFIGURATION] [-J JAZZURL] [-L LOGLEVEL] [-P PASSWORD] [-T] [-U USERNAME] [-W] [-Z PROXYPORT]
                [-0 SAVECREDS] [-1 READCREDS] [-2 ERASECREDS] [-3 SECRET] [-4]
                projectname {create,delete,export,import,list} ...

Perform Reportable REST query on an application, with results output to CSV and/or XML - use -h to get some basic help

positional arguments:
  projectname           Name of project
  {create,delete,export,import,list}
                        sub-commands
    create              Create a new/update an existing reqif definition in a project/component, adding module(s) or artifact(s)
    delete              Delete an existing reqif definition in a project/component
    export              Export one or more definitions from a project/component and download the reqifz file
    import              Import one or more reqifz files into a project/component
    list                List the definitions in a project/component

optional arguments:
  -h, --help            show this help message and exit
  -A APPSTRINGS, --appstrings APPSTRINGS
                        Defaults to "rm,jts" - Must be comma-separated list of used domains or domain:contextroot, the FIRST one must be rm. If using nonstandard context
                        roots for just rm like /rrc then specify "rm:rrc,jts" NOTE if jts is not on /jts then e.g. for /myjts use e.g. "rm:rn1,jts:myjts". Default can be
                        set using environment variable QUERY_APPSTRINGS
  -C COMPONENT, --component COMPONENT
                        The local component (optional, if used you *have* to specify the local configuration using -F)
  -D DELAYBETWEEN, --delaybetween DELAYBETWEEN
                        Delay in seconds between each import/export - use this to reduce overall server load
  -F CONFIGURATION, --configuration CONFIGURATION
                        Scope: Name of local config - you need to provide the project - defaults to the "Initial Stream" or "Initial Development" +same name as the
                        project
  -J JAZZURL, --jazzurl JAZZURL
                        jazz server url (without the /jts!) default {JAZZURL} Default can be set using environment variable QUERY_JAZZURL - defaults to
                        https://jazz.ibm.com:9443 which DOESN'T EXIST
  -L LOGLEVEL, --loglevel LOGLEVEL
                        Set logging on console and (if providing a , and a second level) to file to one of DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF - default is
                        ERROR,DEBUG - can be set by environment variable QUERY_LOGLEVEL
  -P PASSWORD, --password PASSWORD
                        User password - can be set using env variable OUERY_PASSWORD - set to PROMPT to be prompted at runtime
  -T, --certs           Verify SSL certificates
  -U USERNAME, --username USERNAME
                        User id - can be set using environment variable QUERY_USER
  -W, --cachecontrol    Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and disables caching. Otherwise caching is continued
                        from previous run(s).
  -Z PROXYPORT, --proxyport PROXYPORT
                        Port for proxy default is 8888 - used if found to be active - set to 0 to disable
  -0 SAVECREDS, --savecreds SAVECREDS
                        Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, jts, appstring, username and password
  -1 READCREDS, --readcreds READCREDS
                        Read obfuscated credentials from file - completely overrides commandline/environment values for jazzurl, jts, appstring, username and password
  -2 ERASECREDS, --erasecreds ERASECREDS
                        Wipe and delete obfuscated credentials file
  -3 SECRET, --secret SECRET
                        SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater security)
  -4, --credspassword   Prompt user for a password to save/read obfuscated credentials (make this longer for greater security) - NOTE this is by far the best way to
                        secure saved credentials - they're no longer just obfuscated when you use a runtime password!
```


Listing ReqIF definitions
=========================

usage: `reqif_io "my project" list -h`
```
usage: reqif_io projectname list [-h] [-O OUTPUTDIRECTORY] [definitionnames ...]

positional arguments:
  definitionnames       name of export definition- this can be a regex where . matches any character, etc. If you want the regex to match a complete name put ^ at the
                        start and $ at the end - where multiuple names match, these will be exported in alphabetical order

optional arguments:
  -h, --help            show this help message and exit
  -O OUTPUTDIRECTORY, --outputdirectory OUTPUTDIRECTORY
                        Output directory for all exported files
```

Example:

```
```


Exporting reqif definitions
===========================

usage: `reqif_io "my project" export -h`
```
usage: reqif_io projectname export [-h] [-t] [-O OUTPUTDIRECTORY] [definitionnames ...]

positional arguments:
  definitionnames       name of export definition- this can be a regex where . matches any character, etc. If you want the regex to match a complete name put ^ at the
                        start and $ at the end - where multiuple names match, these will be exported in alphabetical order

optional arguments:
  -h, --help            show this help message and exit
  -t, --timestamp       Add a timestamp to all exported file names (both reqif and html)
  -O OUTPUTDIRECTORY, --outputdirectory OUTPUTDIRECTORY
                        Output directory for all exported files
```

Example:

```
```


Importing reqif files
=====================

usage: `reqif_io "my project" import -h
```
usage: reqif_io projectname import [-h] [-I INPUTDIRECTORY] [-O OUTPUTDIRECTORY] [ifiles ...]

positional arguments:
  ifiles                one or more reqif files or file patterns (e.g. *.reqifz) to import

optional arguments:
  -h, --help            show this help message and exit
  -I INPUTDIRECTORY, --inputdirectory INPUTDIRECTORY
                        Input directory for all imported files
  -O OUTPUTDIRECTORY, --outputdirectory OUTPUTDIRECTORY
                        Output directory for all exported files
```

Example:

```
```


Creating a ReqIF definition
===========================

usage: `reqif_io "my project" create -h`
```
usage: reqif_io projectname create [-h] [-a] [-f] [-i [IDENTIFIERS ...]] [-l] [-m [MODULES ...]] [-r] [-s DESCRIPTION] [-t] [-u] definitionname

positional arguments:
  definitionname        The reqif definition name to create

optional arguments:
  -h, --help            show this help message and exit
  -a, --allcores        Add all core artifacts (not modules/collections) from the project/component
  -f, --folders         Don't include folders in the reqif (defaults to including) - if you need this off, specify it on the last update or on the create
  -i [IDENTIFIERS ...], --identifiers [IDENTIFIERS ...]
                        * for all core artifacts or or comma-separated list of requirement IDs to add - can specify this option more than once
  -l, --links           Don't include links in the reqif (defaults to including) - if you need this off, specify it on the last update or on the create
  -m [MODULES ...], --modules [MODULES ...]
                        * or comma-separated list of module IDs or names of the module to add - for name you can use a regex - can specify this option more than once
  -r, --removeallartifacts
                        When updating, first remove all artifacts/modules/views
  -s DESCRIPTION, --description DESCRIPTION
                        Description for the definition
  -t, --tags            Don't include tags in the reqif (defaults to including) - if you need this off, specify it on the last update or on the create
  -u, --update          Update the named definition by adding things - it must already exist!

```

Example:

```
```


Deleting a reqif definition
===========================

usage: `reqif_io "my project" delete -h`
```
usage: reqif_io projectname delete [-h] [-n] [definitionnames ...]

positional arguments:
  definitionnames  One or more names of export definitions to delete - this can be a regex where . matches any character, etc. If you want the regex to match a complete
                   name put ^ at the start and $ at the end

optional arguments:
  -h, --help       show this help message and exit
  -n, --noconfirm  Don't prompt to confirm each delete (DANGEROUS!)

```

Example:

```
```


Server URLs, user IDs and Passwords, and obfuscated credentials
===============================================================

Obfuscated credentials are based on the same code as for `oslcquery`

Your query has to know what server URL to use, what the context roots for the jts and your target application are, what user id and what password to use for authentication.

To specify these there are a range of methods, from simplest (but needs most typing) to, err, better:

* The simplest way to provide your credentials is to specify them explicitly on the commandline whenever you run `reqif_io`.
```
reqif_io -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 "My Project" export a_reqif_definition
```

* A less intrusive method useful if you're mostly querying one application is to set environment variables - NOTE you can override these on the commandline:
```
set QUERY_JAZZURL=https://myserver:port
set QUERY_USER=measadmin
set QUERY_PASSWORD=secret
set QUERY_APPSTRING=rm:rm1,jts:jts23
reqif_io export a_reqif_definition
```
* Using obfuscated credentials

You can create a file containing obfuscated details which are very convenient particularly if wanting to query against multiple applications, because you just specify the credentials file corresponding to the server you want to use. The file content is encrypted, but as the source code is available it isn't terribly difficult to figure out how this done, which is why the term 'obfuscation' is used here; unless you take the option to provide a runtime password then the obfuscation can with some work be de-obfuscated. There are some basic protections against simply copying the credentials file built into the obfuscation irrespective of using the commandline or runtime password - so if you get an error about not being able to read a saved credentials file you'll have to recreate it.

If you use an obfuscated creds file it will override both the environment variable and commandline options.

**NOTE the credentials file is only obfuscated unless you use the runtime prompt option -4, i.e. it's relatively easy to decode**

To create and then use an obfuscated credentials file specify these details once on the command line with the `-0` option to create a credentials file, then to use these specify the filename after the `-1` option e.g.:
```
reqif_io -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -0 .mycreds

reqif_io -1 .mycreds "My Project" -q dcterms:identifier=23 -O rmresults.csv
```

Optionally add a commandline password (secret) using `-4` when creating and when using the credentials file:
```
reqif_io -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -0 .mycreds -3 commandlinesecret

reqif_io -1 .mycreds -3 commandlinesecret "My Project" -q dcterms:identifier=23 -O rmresults.csv
```

Optionally use a runtime prompt for the credentials file password using `-4` when creating and when using the credentials file - NOTE if you forget what the runtime password is you will have to delete the creds file and recreate it, i.e. there's no password recovery optiopns :-o
```
reqif_io -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -1 .mycreds -4
Password (>0 chars, longer is more secure)?

reqif_io -1 .mycreds -4 "My Project" -q dcterms:identifier=23 -O rmresults.csv
Password (>0 chars, longer is more secure)?
```

To erase obfuscated credentials use option -2 then the credentials filename:
```
reqif_io -2 .mycreds
```

TO BE CLEAR: **NOTE the credentials file is only obfuscated: unless you use the runtime prompt option -4 to encrypt it, it's pretty easy to decode once you have the python source code**


Future work
===========

* Move the reqif API operations within `elmclient` - there should be any direct use of HTTP `execute...` calls
* Increase support for e.g. adding views to a reqif definition

