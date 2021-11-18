# IBM Engineering Lifecycle Management ReqIF import/export example using elmclient


 Commandline ReqIF import/export eaxample using elmclient


 (c) Copyright 2021- IBM Inc. All rights reserved
 
 SPDX-License-Identifier: MIT



Introduction
============

The aim of this code is to provide command-line, automatable, access to the Reportable REST APIs of DOORS Next, EWM and ETM.

At the moment only DOORS Next Reportable REST has been implemented. The DN Reportable REST API is documented here 

You can:
* Export data to CSV and XML
* Query the resources provided by DOORS Next
* Filter using specific resource IDs, module names, view names, etc.

The Reportable REST API can word with projects but only by providing detailed URL or UUIDs. One of the key objectives in providing this example is to use instead the project name, view names, module names, or artifact IDs.

**IMPORTANT NOTE** Reportable REST API use is an expensive operations on your server - you are responsible to manage the load these place on your server so as not to adversely affect the experience of other users or to jeopardise the server itself due to excessive load.

Installation
============

The `represt` command is installed in your Python scripts folder when installing `elmclient`


Usage
=====


To get all the usage options use `represt -h` or `represt --help`:

```
usage: represt [-h] [-A APPSTRINGS] [-C CSVOUTPUTFILE] [-D DELAYBETWEENPAGES] [-E CACHEEXPIRY] [-G PAGESIZE] [-H FORCEHEADER] [-J JAZZURL] [-K] [-L LOGLEVEL]
               [-M MAXRESULTS] [-P PASSWORD] [-R FORCEPARAMETER] [-S] [-T] [-U USERNAME] [-V] [-W] [-X XMLOUTPUTFILE] [-Z PROXYPORT] [-0 SAVECREDS] [-1 READCREDS]
               [-2 ERASECREDS] [-3 SECRET] [-4]
               {rm} ...

Perform Reportable REST query on an application, with results output to CSV and/or XML - use -h to get some basic help. NOTE only rm queries are allowed at the moment.

positional arguments:
  {rm}                  sub-commands
    rm                  RM Reportable REST actions

optional arguments:
  -h, --help            show this help message and exit
  -A APPSTRINGS, --appstrings APPSTRINGS
                        Must be comma-separated list of used domains or domain:contextroot, the FIRST one is where the reportable rest query goes, default rm If using
                        nonstandard context roots for just rm and gc like /rrc and /thegc then specify "rm:rrc,gc:thegc" NOTE if jts is not on /jts but is on /myjts then
                        add jts: and its context route without leading / e.g. "rm,jts:myjts" to the end of this string. Default can be set using environment variable
                        QUERY_APPSTRINGS
  -C CSVOUTPUTFILE, --csvoutputfile CSVOUTPUTFILE
                        Name of file to save the CSV results to
  -D DELAYBETWEENPAGES, --delaybetweenpages DELAYBETWEENPAGES
                        Delay in seconds between each page of results - use this to reduce overall server load particularly for large result sets or when retrieving many
                        attributes
  -E CACHEEXPIRY, --cacheexpiry CACHEEXPIRY
                        Days to keep cached results from the server (NOTE query results are never cached) - set to 0 to erase current cache and suppress new caching -
                        set to e.g. -7 to erase current cache and then cache for 7 days, set to 7 to maintain the current cache and keep new entries for 7 days
  -G PAGESIZE, --pagesize PAGESIZE
                        Page size for results paging (default is whatever the server does, e.g. 100)
  -H FORCEHEADER, --forceheader FORCEHEADER
                        Force adding header with value to the query - you must provide the header name=value. NOTE these override headers from the application. If you
                        want to force deleting a header give it the value DELETE. There is no way of forcing a header to have the value DELETE
  -J JAZZURL, --jazzurl JAZZURL
                        jazz server url (without the /jts!) default {JAZZURL} Default can be set using environment variable QUERY_JAZZURL
  -K, --collapsetags    In CSV output rather than naming column for the tag hierarchy, just use the leaf tag name
  -L LOGLEVEL, --loglevel LOGLEVEL
                        Set logging on console and (if providing a , and a second level) to file to one of DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF - default is
                        ERROR,DEBUG - can be set by environment variable QUERY_LOGLEVEL
  -M MAXRESULTS, --maxresults MAXRESULTS
                        Limit on number of results - may be exceeded by up to one page of results
  -P PASSWORD, --password PASSWORD
                        User password - can be set using env variable OUERY_PASSWORD - set to PROMPT to be prompted at runtime
  -R FORCEPARAMETER, --forceparameter FORCEPARAMETER
                        Force adding query name and value to the query URL - you must provide the name=value, the value will be correctly encoded for you. NOTE these
                        override parameters from the application. If you want to force deleting a parameter give it the value DELETE. There is no way of forcing a
                        parameter to have the value DELETE
  -S, --sortidentifier  If identifier is in results, sort into ascending numeric order of identifier
  -T, --certs           Verify SSL certificates
  -U USERNAME, --username USERNAME
                        User id - can be set using environment variable QUERY_USER
  -V, --verbose         Show verbose info during query
  -W, --cachecontrol    Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and disables caching. Otherwise caching is continued
                        from previous run(s).
  -X XMLOUTPUTFILE, --xmloutputfile XMLOUTPUTFILE
                        Name of file to save the XML results to
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
  -4, --credspassword   Prompt user for a password to save/read obfuscated credentials (make this longer for greater security)
```

Once you provide the application `rm` as a parameter, there are rm-specific options - to see these use `represt rm -h`:
'''
usage: represt rm [-h] [-p PROJECT] [-c COMPONENT] [-g GLOBALCONFIGURATION] [-l LOCALCONFIGURATION] [-e TARGETCONFIGURATION] [-n COLLECTION | -m MODULE]
                  [-v VIEW | -q MODULERESOURCEID | -r RESOURCEID | -s CORERESOURCEID | -t TYPENAME] [-a] [-d MODIFIEDSINCE] [-x]
                  [--attributes ATTRIBUTES | --schema | --titles | --linksOnly | --history | --coverPage | --signaturePage]
                  {collections,comments,comparison,linktypes,modules,processes,resources,reviews,revisions,screenflows,storyboards,terms,text,uisketches,usecasediagrams}

positional arguments:
  {collections,comments,comparison,linktypes,modules,processes,resources,reviews,revisions,screenflows,storyboards,terms,text,uisketches,usecasediagrams}
                        RM artifact format - possible values are collections, comments, comparison, linktypes, modules, processes, resources, reviews, revisions,
                        screenflows, storyboards, terms, text, uisketches, usecasediagrams

optional arguments:
  -h, --help            show this help message and exit
  -p PROJECT, --project PROJECT
                        Scope: Name of project - required when using module/collection/view/resource/typename ID/typename as a filter
  -c COMPONENT, --component COMPONENT
                        Scope: Name of component - required when using module/collection/view/resource/typename ID/typename as a filter
  -g GLOBALCONFIGURATION, --globalconfiguration GLOBALCONFIGURATION
                        Scope: Name or ID of global config (make sure you define gc in --appstring!) - to use this you need to provide the project
  -l LOCALCONFIGURATION, --localconfiguration LOCALCONFIGURATION
                        Scope: Name of local config - you need to provide the project - defaults to the "Initial Stream" or "Initial Development" +same name as the
                        project - if name is ambiguous specify a stream using "S:Project Initial Stream", a baseline using "B:my baseline", or changeset using
                        "C:changesetname"
  -e TARGETCONFIGURATION, --targetconfiguration TARGETCONFIGURATION
                        Scope: Name of target configuration when using artifact_format comparison - see description of --localconfiguration for how to disambiguate names
  -n COLLECTION, --collection COLLECTION
                        Sub-scope: RM: Name or ID of collection - you need to provide the project and local/global config
  -m MODULE, --module MODULE
                        Sub-scope: RM: Name or ID of module - you need to provide the project and local/global config
  -v VIEW, --view VIEW  Sub-scope: RM: Name of view - you need to provide the project and local/global config
  -q MODULERESOURCEID, --moduleResourceID MODULERESOURCEID
                        Sub-scope: RM: Comma-separated IDs of module resources - you need to provide the project and local/global config
  -r RESOURCEID, --resourceID RESOURCEID
                        Sub-scope: RM: Comma-separated IDs of core or module resources - you need to provide the project and local/global config
  -s CORERESOURCEID, --coreResourceID CORERESOURCEID
                        Sub-scope: RM: Comma-separated IDs of core resources - you need to provide the project and local/global config
  -t TYPENAME, --typename TYPENAME
                        Sub-scope: RM: Name of type - you need to provide the project and local/global config
  -a, --all             Filter: Report all resources
  -d MODIFIEDSINCE, --modifiedsince MODIFIEDSINCE
                        Filter: only return items modified since this date - NOTE this is only for DCC ETL! Date must be in ISO 8601 format like 2021-01-31T12:34:26Z
  -x, --expandEmbeddedArtifacts
                        Filter: Expand embedded artifacts
  --attributes ATTRIBUTES
                        Output: Comma separated list of attribute names to report (requires specifying project and configuration)
  --schema              Output: Report the schema
  --titles              Output: Report titles
  --linksOnly           Output: Report links only
  --history             Output: Report history
  --coverPage           Output: Report cover page variables
  --signaturePage       Output: Report signature page variables
'''

Getting started
===============

To get any data you'll have to specify your ELM server URL, login and password - unless your server happens to be on the default https://jazz.ibm.com:9443 with login ibm and password ibm :-)

The simple way to set these is on the commandline, for example:

`represt -J https://myserver.com -U myuser -P mypassword <...other options... >`

Find an opt-out project `aproject` and you can get data from it like:

`represt -J https://myserver.com -U myuser -P mypassword rm resources aproject`

If your projet name has a space, surround it with " ", like this:

`represt -J https://myserver.com -U myuser -P mypassword rm resources "a project"`

A more sophisticated way of keeping obfuscated credentials in a file is shown below.


Examples of usage
=================

Module resources:
`represt -J https://myserver.com -U myuser -P mypassword rm modules "a project" -l "The Development Stream" --all`


Module resources in a view:
`represt -J https://myserver.com -U myuser -P mypassword rm modules "a project" -l "The Development Stream" -m "The Module"`


Details of al (core and module) artifact 123:
`represt -J https://myserver.com -U myuser -P mypassword rm resources -p "a project" -l "The Development Stream" -r 123`


Details of a core artifact 123:
`represt -J https://myserver.com -U myuser -P mypassword rm resources -p "a project" -l "The Development Stream" -s 123`


Details of a reused artifact 123 in a module:
`represt -J https://myserver.com -U myuser -P mypassword rm resources -p "a project" -l "The Development Stream" -q 123`


Server URLs, user IDs and Passwords, and obfuscated credentials
===============================================================

Obfuscated credentials are based on the same code as for `oslcquery`

Your query has to know what server URL to use, what the context roots for the jts and your target application are, what user id and what password to use for authentication.

To specify these there are a range of methods, from simplest (but needs most typing) to, err, better:

* The simplest way to provide your credentials is to specify them explicitly on the commandline whenever you run `reqif_io`.
```
represt -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 rm resources "My Opt-Out Project" --all
```

* A less intrusive method useful if you're mostly querying one application is to set environment variables - NOTE you can override these on the commandline:
```
set QUERY_JAZZURL=https://myserver:port
set QUERY_USER=measadmin
set QUERY_PASSWORD=secret
set QUERY_APPSTRING=rm:rm1,jts:jts23
represt rm resources "My Opt-Out Project" --all
```
* Using obfuscated credentials

You can create a file containing obfuscated details which are very convenient particularly if wanting to query against multiple applications, because you just specify the credentials file corresponding to the server you want to use. The file content is encrypted, but as the source code is available it isn't terribly difficult to figure out how this done, which is why the term 'obfuscation' is used here; unless you take the option to provide a runtime password then the obfuscation can with some work be de-obfuscated. There are some basic protections against simply copying the credentials file built into the obfuscation irrespective of using the commandline or runtime password - so if you get an error about not being able to read a saved credentials file you'll have to recreate it.

If you use an obfuscated creds file it will override both the environment variable and commandline options.

**NOTE the credentials file is only obfuscated unless you use the runtime prompt option -4, i.e. it's relatively easy to decode**

To create and then use an obfuscated credentials file specify these details once on the command line with the `-0` option to create a credentials file, then to use these specify the filename after the `-1` option e.g.:
```
represt -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -0 .mycreds

represt -1 .mycreds rm resources "My Opt-Out Project" --all -m "AMR Stakeholder Requirements Specification"
```

Optionally add a commandline password (secret) using `-4` when creating and when using the credentials file:
```
represt -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -0 .mycreds -3 commandlinesecret

represt -1 .mycreds -3 commandlinesecret rm resources "My Opt-Out Project" --all -m "AMR Stakeholder Requirements Specification"
```

Best way to secure the creds is to use a runtime prompt for the credentials file password using `-4` when creating and when using the credentials file - NOTE if you forget what the runtime password is you will have to delete the creds file and recreate it, i.e. there's no password recovery optiopns :-o
```
represt -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -0 .mycreds -4
Password (>0 chars, longer is more secure)? (password is not echoed)

represt -1 .mycreds -4 commandlinesecret rm resources "My Opt-Out Project" --all -m "AMR Stakeholder Requirements Specification"
Password (>0 chars, longer is more secure)?
```

To erase obfuscated credentials use option -2 then the credentials filename:
```
represt -2 .mycreds rm
```

TO BE CLEAR: **NOTE the credentials file is only obfuscated unless you use the runtime prompt option -4, i.e. it's pretty easy to decode once you have the python source code**


Future work
===========

* Extend to the EWM and EtM Reportable REST API
