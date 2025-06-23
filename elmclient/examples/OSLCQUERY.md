# IBM Engineering Lifecycle Management OSLC Query commandline example app to export data to CSV


 Commandline OSLC query for IBM Engineering Lifecycle Management (ELM) applications DOORS Next (DN). Engineering Test Management (ETM), Engineering Workflow Manager (EWM) and Global Configuration Management (GCM) for export to CSV


 (c) Copyright 2021- IBM Inc. All rights reserved
 SPDX-License-Identifier: MIT



Introduction
============

The aim of this code is to provide a relatively human-friendly front-end to the OSLC Query capabilities in IBM ELM applications DOORS Next (DN), Engineering Test Manager (ETM), Engineering Workflow Manager (EWM) and Global Configuration Management (GCM), using a commandline application so that OSLC Query can be used to export data from these applications to CSV and XML; running from a commandline means that the export can be automated.

OSLC uses URIs to uniquely identify resources and definitions, to create, retrieve and uppdate, and also for Query to locate resources of interest - that's great for computers but not so friendly to humans because of the complexity of finding these URIs. In addition every URI embeds the server name and project-specific identifiers, so at the detailed level an OSLC query is completely tied to the context it is made in; to perform a similar query on a different server requires (re-)finding completely different URIs on the new server.

This application abstracts OSLC query so the user can specify a query using the friendly names given to resources (as seen in the browser user interface) such as enumeration names and folder names, simplifying life for the user and making queries easier to create, and much more server- and project-independent.

If you're thinking that this sounds like something for nothing, be aware that the cost of abstracting from URIs to human-friendly names is that the `oslcquery` application can only get these human-friendly definitions by querying the server, so there is preparation needed to, for example, parse the high-level query to convert user-friendly names to URIs, and then post-processing to convert URIs in the results back into friendly names. The time this takes can be mitigated to a large extent by the application caching this information, which doesn't change frequently - you can clear or disable this cache if needed.

Of course there are things about a query that can't be elided - you still have to specify URLs for server, context roots, etc., and you have to use the names of things spelled and capitalised correctly. This application allows you to specify the URLs and context roots once.


Overview - OSLC Query
=====================

For full details on the OSLC Query specification see https://docs.oasis-open-projects.org/oslc-op/query/v3.0/os/oslc-query.html

IBM DOORS Next (DN), Engineering Test Manager (ETM), Engineering Workflow Manager (EWM) and Global Configuration Management (GCM) have supported OSLC query for many years now.

OSLC Query is a REST API; a client uses a HTTP GET to place a query to an application, with results returned in the response to the GET.

A query has four main parameters, although all are optional:
* oslc.where - this specifies zero or more conditions, these are tests of property names against values, such as comparisons or equality. Multiple conditions can be specified which are logically anded. So you could specify that the identifier of a resource is equal to 23 AND the Priority property is High - BUT note that the reference to the properties like the identifier or Status MUST be made using the URI of that property, and if comparing with the enumeration name High this must also be made using the URI for that enumeration.
* oslc.select - this specifies properties that the server should return in the results in addition to the URIs of resources that match the oslc.where conditions
* oslc.orderBy - a comma separated list of properties each prefixed by + or - to indicate ascending or descending sort
* oslc.searchTerms - text used to locate resources

An OSLC Query endpoint is found by searching for a Query Capability for a particular type of resource via the ELM application-specific rootservices document. All the applications provide one or more query capabilities on projects. ETM and GCM also provide query capabilities on the application which allows searching for components or configurations. GCM also provides additional application-level OSLC queries. The `oslcquery` application allows you to utilise all these various query capabilities specifying a resource type, on a project by also specifying a project name, or on the application by not specifying a project name. You can see the application- and project-querying capabilities, with the resource types supported, using the type system report option.

The results returned will include at least the URI of each matching resource along with, if present on that resource, the oslc.select properties requested in the query, returned as literal values for strings or numbers, or as a URI for custom properties such as enumerations or references to resources, for example in links.

It is important to note that the OSLC Query specification includes many optional aspects - including details of support for the parameters described above, so you shouldn't expect that DN, ETM and EWM support everything shown in the specification. Behaviour of queries has changed over the evolution of the applications, and is occasionally affected by defects: to ensure the best results you should ensure that your server is updated with the most recent iFix for your version. Also, a particular aspect of the OSLC Query specification not being supported is not a defect, so this isn't a reason to create a support case.

Terminology of OSLC as it relates to ELM:
* Resource - something managed by an application, for example (but not limited to) a work item in EWM or an artifact in DN or a test case in ETM or a configuration in GCM - each resource has a specific type (known as a Shape) and that type defines the properties (aka attributes) of every resource of that type - that type definition is called a Shape
* Shape - the definition of the properties of a specific type of resource such as a Defect in EWM or a Module in DN. Applications support many different types of resource, each has a shape definition. Each shape has a name.
* Property - the definition of a value on a resource - this may be numeric, a date, a string, or be an enumeration of named values. Each property has a name.
* Enumeration - the definition of a specific value for a property - each enumeration has a name.

The OSLC Query specification expects all resources, shapes, properties and enumerations to be referred to using a URI. This is unambiguous and computer-friendly but this makes OSLC Query difficult for humans to use easily; this `oslcquery` application is going to allow users to refer to properties using the human-friendly names seen in the ELM user interfaces, and will automatically translate these to URIs in the OSLC Query made to the ELM application, and in the results which also contain URIs to transform these back to human-friendly names. You can see the shapes, properties and enumerations defined in your project using the typesystem report which is an option on the `oslcquery` commandline.

URIs can be specified using a http: or https:// URL e.g. `http://purl.org/dc/terms/identifier` or in OSLC there is common usage of RDF prefixes to simplify constructing an equivalent to the URI, in this case `dcterms:identifier`. `dcterms` is called a prefix and is defined with the value `http://purl.org/dc/terms/` - all the common prefixes are already defined in this application, you can see these at the end of the typesystem report generated using the `--typesystemreport file.html` option.


Installation
============

Two commands are installed with `elmclient`: `oslcquery` and `batchquery`, put in the Python Scripts folder - if this folder is in the path you can use the command from anywhere.



Usage
=====

NOTE if you can't get a query to work check the 'When things go wrong' section below

To get all the usage options use `-h` or `--help`:

```
usage: oslcquery [-h] [-f SEARCHTERMS] [-n NULL] [-o ORDERBY] [-p PROJECTNAME] [-q QUERY] [-r RESOURCETYPE]
                 [-s SELECT] [-u] [-v VALUE] [-A APPSTRINGS] [-C COMPONENT] [-D DELAYBETWEENPAGES] [-E GLOBALPROJECT]
                 [-F CONFIGURATION] [-G GLOBALCONFIGURATION] [-H SAVECONFIGS] [-I] [-J JAZZURL] [-L LOGLEVEL]
                 [-M MAXRESULTS] [-N] [-O OUTPUTFILE] [-P PASSWORD] [-Q] [-R] [-S] [-T] [-U USERNAME] [-V] [-W]
                 [-X XMLOUTPUTFILE] [-Y] [-Z PROXYPORT] [--nresults NRESULTS] [--compareresults COMPARERESULTS]
                 [--pagesize PAGESIZE] [--typesystemreport TYPESYSTEMREPORT] [--cachedays CACHEDAYS]
                 [--saverawresults SAVERAWRESULTS] [--saveprocessedresults SAVEPROCESSEDRESULTS] [-0 SAVECREDS]
                 [-1 READCREDS] [-2 ERASECREDS] [-3 SECRET] [-4]

Perform OSLC query on a Jazz application, with results output to CSV (and other) formats - use -h to get some basic
help

options:
  -h, --help            show this help message and exit
  -f SEARCHTERMS, --searchterms SEARCHTERMS
                        **APPS MAY NOT FULLY SUPPORT THIS** A word or phrase to search, returning ranked results"
  -n NULL, --null NULL  Post-filter: A property that must be null (empty) for the resource to be included in the
                        results - you can specify this option more than once
  -o ORDERBY, --orderby ORDERBY
                        **APPS MAY NOT FULLY SUPPORT THIS** A comma-separated list of properties to sort by - prefix
                        with "+" for ascending, "-" for descending- if -f/--searchterms is specified this orders items
                        with the same oslc:score - to speciy a leading -, use = e.g. -o=-dcterms:title
  -p PROJECTNAME, --projectname PROJECTNAME
                        Name of the project - omit to run a query on the application
  -q QUERY, --query QUERY
                        Enhanced OSLC query (defaults to empty string which returns all resources)
  -r RESOURCETYPE, --resourcetype RESOURCETYPE
                        The app-specific type being searched, e.g. Requirement for RM, Configuration for GC - this can
                        be the full URI from the query capability resource type,, a prefixed uri, or the unqiue last
                        part of the query URL - also used for resolving ambiguous attribute names in -q/-s/-v/-n
  -s SELECT, --select SELECT
                        A comma-separate list of properties that should be included in the results - NOTE the app may
                        include additional properties, and may not include the requested properties
  -u, --unique          Post-filter: Remove results with an rm_nav:parent value which are not-unique in the results on
                        dcterms:identifier - this keeps module artifacts (which don't have rm_nav:parent) and
                        artifacts for modules (which don't have a module artifact)) - RELEVANT ONLY FOR DOORS Next!
  -v VALUE, --value VALUE
                        Post-filter: A property name that must have a value for the resource to be included in the
                        results - you can specify this option more than once
  -A APPSTRINGS, --appstrings APPSTRINGS
                        A comma-seperated list of apps, the query goes to the first entry, default "rm". Each entry
                        must be a domain or domain:contextroot e.g. rm or rm:rm1 - Default can be set using
                        environemnt variable QUERY_APPSTRINGS
  -C COMPONENT, --component COMPONENT
                        The local component (optional, you *have* to specify the local configuration using -F)
  -D DELAYBETWEENPAGES, --delaybetweenpages DELAYBETWEENPAGES
                        Delay in seconds between each page of results - use this to reduce overall server load
                        particularly for large result sets or when retrieving many properties
  -E GLOBALPROJECT, --globalproject GLOBALPROJECT
                        The global configuration project - needed if the globalconfiguration isn't unique
  -F CONFIGURATION, --configuration CONFIGURATION
                        The local configuration
  -G GLOBALCONFIGURATION, --globalconfiguration GLOBALCONFIGURATION
                        The global configuration (you must not specify local config as well!) - you can specify the
                        id, the full URI, or the config name (not implemented yet)
  -H SAVECONFIGS, --saveconfigs SAVECONFIGS
                        Name of CSV file to save details of the local project components and configurations
  -I, --totalize        For any column with multiple results, put in the total instead of the results
  -J JAZZURL, --jazzurl JAZZURL
                        jazz server url (without the /jts!) default https://jazz.ibm.com:9443 - Default can be set
                        using environemnt variable QUERY_JAZZURL - defaults to https://jazz.ibm.com:9443 which DOESN'T
                        EXIST
  -L LOGLEVEL, --loglevel LOGLEVEL
                        Set logging to file and (by adding a "," and a second level) to console to one of DEBUG,
                        TRACE, INFO, WARNING, ERROR, CRITICAL, OFF - default is None - can be set by environment
                        variable QUERY_LOGLEVEL
  -M MAXRESULTS, --maxresults MAXRESULTS
                        Max number of results to retrieve a pagesize at a time, then the query is terminated. default
                        is no limit
  -N, --noprogressbar   Don't show progress bar during query
  -O OUTPUTFILE, --outputfile OUTPUTFILE
                        Name of file to save the CSV to
  -P PASSWORD, --password PASSWORD
                        user password, default ibm - Default can be set using environment variable QUERY_PASSWORD -
                        set to PROMPT to be asked for password at runtime
  -Q, --resolvenames    toggle name resolving off (default on) - can greatly speed up postprocessing but you'll get
                        URIs rather than names
  -R, --nodefaultselects
                        Suppress adding default select like for rm rm_nav:folder and dcterms:identifier - can speed up
                        postprocessing because e.g. no need to look up folder name
  -S, --sort            Don't sort results by increasing dcterms:identifier, as is done by default - specifying -o
                        (orderby) disables automatic sorting by dcterms:identifier
  -T, --certs           Verify SSL certificates
  -U USERNAME, --username USERNAME
                        user id, default ibm - Default can be set using environment variable QUERY_USER
  -V, --verbose         Show verbose info
  -W, --cachecontrol    Used once -W erases cache then continues with caching enabled. Used twice -WW wipes cache and
                        disables caching. Otherwise caching is continued from previous run(s).
  -X XMLOUTPUTFILE, --xmloutputfile XMLOUTPUTFILE
                        For each query result, GET the artifact and save to file with this base name plus the
                        identifier (if present) - PROBABLY RELEVANT ONLY TO RM!
  -Y, --debugprint      Print the raw results
  -Z PROXYPORT, --proxyport PROXYPORT
                        Port for proxy default is 8888 - used if found to be active - set to 0 to disable
  --nresults NRESULTS   Number of results expected - used for regression testing - use `--nresults -1` to disable
                        checking
  --compareresults COMPARERESULTS
                        TESTING UNFINISHED: saved CSV file to compare results with
  --pagesize PAGESIZE   Page size for OSLC query (default 200)
  --typesystemreport TYPESYSTEMREPORT
                        Load the specified project/configuration and then produce a simple HTML type system report of
                        resource shapes/properties/enumerations to this file
  --cachedays CACHEDAYS
                        The number of days for caching received data, default 7. To disable caching use -WW. To keep
                        using a non-default cache period you must specify this value every time
  --saverawresults SAVERAWRESULTS
                        Save the raw results as XML to this path/file prefix - pages are numbered starting from 0000
  --saveprocessedresults SAVEPROCESSEDRESULTS
                        Save the processed results as JSON to this path/file
  -0 SAVECREDS, --savecreds SAVECREDS
                        Save obfuscated credentials file for use with readcreds, then exit - this stores jazzurl, jts,
                        appstring, username and password
  -1 READCREDS, --readcreds READCREDS
                        Read obfuscated credentials from file - completely overrides commandline/environment values
                        for jazzurl, jts, appstring, username and password
  -2 ERASECREDS, --erasecreds ERASECREDS
                        Wipe and delete obfuscated credentials file
  -3 SECRET, --secret SECRET
                        SECRET used to encrypt and decrypt the obfuscated credentials (make this longer for greater
                        security) - only affects if using -0 or -1
  -4, --credspassword   Prompt user for a password to save/read obfuscated credentials (make this longer for greater
                        security)
```


BEFORE you start:
=================

* Be careful about the load on the server you run this against as it does a lot of http accesses to retrieve the type system, components and configurations, and to query the DNG type system using resource shapes - and the OSLC query itself can be expensive - so try to be as restrictive as possible to return the least number of results, with the least number of proeprties per result. Once querying starts you can press ESC to stop after the next page of results has been retrieved.

* OSLC Query support - you can specify oslc.select, oslc.orderBy and oslc.searchTerms as options on the commandline. These aren't all handled in every possible permutation of what can be specified (with or without an oslc.where query) by all versions of DN, ETM EWM and GCM. This isn't a defect, or a reason to create a support case. Similarly for oslc.score in query results.

* The query is made using paging so there's no built-in limit on results size, but making those paged queries will load up the server. To minimise server impact, use careful query design e.g. restrict to specific IDs or (for DNG) folders. You can specify a pacing time between pages.

* If the query progress is slow, you can press Esc to terminate after the next page of results - the partial results will be processed and written to output file

* To speed up usage, by default the application caches responses for one day (24h), apart from login and the actual OSLC Query, and once login has been successful the cookie is saved to disc and will be tried for the next session so the slight delay of login is avoided if not needed. You can disable caching using the -W option which erases previously saved caches and cookies at the start of a session, or -WW to clear and completely disable caching. You can also set the number of days for caching responses.

* If you don't get the results you expect, __first ensure your server is updated to the latest iFix for the version you're running.__

* If an option includes spaces surround it with " "

* On Windows at least, on the command line it is necessary to put " around values that include space, ", < or > and then double any " within a string. So a query like State="New" has to be entered as "State=""New""", or dcterms:identifier<23 has to be entered as "dcterms:identifier<23"

* On Windows at least, if for example a title that you're searching for includes an embedded double-quote " then you have to escape each with a backslash \. Because of the way the Windows commandline works, this means you have to replace each embedded " with \\"". For example to query for a title `A "specification"` you have to put `"dcterms:title=""A \\""specification\\"""""`

* The query specified with the '-q' option supports extended OSLC query syntax, described below - in particular this adds syntactic support for referencing definition names, user names and folder names, and also allows combining results from two or more OSLC queries using set union (denoted by ||) and intersection (denoted by &&).

* As well as the extended query syntax, there are options -n and -v for post-processing the query to eliminate results which have no value for a particular property, or to eliminate results which have a non-empty value for an property. This is of particular use for DN to select only core or only module-based artifacts.

* There is an option -X to retrieve (GET) the RDF XML content for each result URI returned and save to a file.

* Links are only stored at the from or outgoing end, so you can query for resources with a Satisfies link because that is a property stored in a DN artifact which is the source of the link, but you can't query for 'Satisfied By' because that isn't stored anywhere except as an outgoing 'Satisfies' at the other end. There are examples of finding resources with/without links in the DN Advanced Usage section below.

* Saved credentials - there are several ways of providing credentials. You can specify them using environment variables, or on the commandline, or you can save them in an obfuscated file so you only have to specify the credentials file to load. This file can optionally be further secured using a password on the commandline or a password from user input every run.

* By default nothing is logged. use -L and OFF/INFO/DEBUG/ERROR/CRITICAL to do logging - this will create a folder `logs` and put date-time stamped log files in there. NOTE that user login/passwords are redacted in the logs. Nothing else is redacted.

* The application has been used with four different forms of authentication, using ASCII characters only:
** Form with Liberty user registry
** Form with Liberty LDAP (although note this hasn't been tested recently)
** Jazz Authorization Server with local user registry
** JAS-SCIM (LDAP)

* Tested against 6.0.6.1 and 7.0.2 versions of ELM - should work against older/other versions, but there is no intention to test other versions or to guarantee to fix problems if anyone finds it doesn't work.  Occasionally there are defects in the APIs, so if you have problems first ensure you have the latest iFix installed on your server.

* If your jts isn't on /jts, perhaps it's on /jts23, so add jts:jts23 to the end of your -A APPSTRINGS like this: -A rm,gc,jts:jts23 or -A ccm:ccm1,jts:jts23


EWM Basic usage
===============

To get the identifier and title of all work items in a project when your EWM application is on context root /ccm (replace the server:port, APPSTRING and username/password with values for your server):
```
oslcquery -J https://my.server:port -A ccm -U YOURUSERNAME -P YOURPASSWORD -p "My CCM Project" -s dcterms:title -O ccmresults.csv
```

Note the requirement to use the -A option to specify that ccm is the target app for the query, in this case on /ccm1 - if your server has context root /ccm then you can specify just `-A ccm`

Results are written to the file `ccmresults.csv`. For example here are the first four results - the resource URI is in the `$uri` column:

| $uri                                                                              | dcterms:identifier | dcterms:title | type |
|-----------------------------------------------------------------------------------|:--:|--------------------------------------|-------------------------------|
|https://jazz.ibm.com:9443/ccm/resource/itemName/com.ibm.team.workitem.WorkItem/11__|__11|Not possible to change a user password|oslc_cm1:ChangeRequest|
|https://jazz.ibm.com:9443/ccm/resource/itemName/com.ibm.team.workitem.WorkItem/23__|__23|Allow to edit user details|oslc_cm1:ChangeRequest|
|https://jazz.ibm.com:9443/ccm/resource/itemName/com.ibm.team.workitem.WorkItem/30__|__30|Allow a user to create a dashboard of information|oslc_cm1:ChangeRequest|
|https://jazz.ibm.com:9443/ccm/resource/itemName/com.ibm.team.workitem.WorkItem/49__|__49|Provide faceted search capabilities|oslc_cm1:ChangeRequest|

Results always include dcterms:identifier (enforced by this application, not by EWM) and by default are sorted by increasing identifier - to disable sorting use the `-S` option.

In addition to the explicitly selected property dcterms:title, and the dcterms:identifier required by `oslcquery`, EWM has added the `type` property to the results, as it is allowed to do by the OSLC Query specification - this can't be removed.


EWM Advanced usage examples
===========================

EWM can provide a query capability only for `oslc_cm1:ChangeRequest`.

If your EWM application is not on context root /ccm then use the -A option for example for context root /ccm1 add the option `-A ccm:ccm1`

Use the typesystem report to see all the shapes, properties and enumeration names in your project: add `-typesystemreport file.html` to the commandline. Note not all properties are queryable.

To find work items of a specific type: `-q rtc_cm:type=Defect`

To find new Defect work items: `-q Defect.Status=New`

To find high priority new Defects: `-q "Defect.Status=New and Defect.Priority=High"`

Because of EWM's data model you can only query the shape-specific property like Status - so to find new Defects and Tasks use this, which will make two queries to your server: `-q "(Defect.Status=New) || (Task.Status=New)"`

To find new high priority defects with calculation anywhere in the title: `-q "Defect.Status=New and Defect.Priority=High and dcterms:title=""*calculation*"""`

To find new high priority defects and also retrieve their RDF XML to file too, into an existing subdirectory 'defects' with file names starting 'd_': `-q Defect.Priority=High -X defects\d` - NOTE the files are named using the identifier of the work item.

To find Defects modified after a specific date-time: `-q "Defect.'Modified Date'>""2020-08-01T21:51:40.979Z"""` - note that for EWM you must not append `^^xsd:datetime` to the date-time string, unlike DN which requires this.

To find all work items with a word a somewhat like 'donors': `-f Donors`

To find all work items with a "implements Requirement" link, add a postprocessing filter: `-v oslc_cm1:implementsRequirement`

To find all work items without a "implements Requirement" link, add a postprocessing filter: `-n oslc_cm1:implementsRequirement`



ETM Basic usage
===============

Using OSLC Query with ETM is the least mature code - the examples below work but other variations haven't been tested at all.

To get all the test cases in an opt-out project (when your ETM application is on contet root /qm):
```
oslcquery -J https://my.server:port -A qm:qm1 -U YOURUSERNAME -P YOURPASSWORD -p "My QM Project" -s dcterms:title -O qmresults.csv
```

Note the requirement to use the -A option to specify that qm is the target app for the query, in this case on /qm1 - if your server has context root /qm then you can specify just `-A qm`

Results are written to the file `qmresults.csv`. For example here are the first four results - the resource URI is in the `$uri` column:

INSERT TABLE

Results always include $uri and dcterms:identifier (enforced by this application, not by ETM) and by default are sorted by increasing identifier - to disable sorting use the `-S` option.


ETM Advanced usage examples
===========================

ETM projects can provide query capability for a number of different resource types including Component and Configuration. Within a project, ETM provides many query capabilities for different types of resources  - get a typesystem report to see the list. The default resource type is `oslc_qm:TestCaseQuery` - the short way to specify this is `-r TestCaseQuery`.

If your ETM application is not on context root /qm then use the -A option for example for context root /qm1 add the option `-A qm:qm1`

Use the typesystem report to see all the shapes, properties and enumeration names in your project: add `--typesystemreport` to the commandline. Note not all properties are queryable.

*Project queries:*

To find test cases modifed since a specific date (NOTE only UTC times are supported): `-q dcterms:modified>""2020-07-01T21:51:40.979Z""^^xsd:datetime"`

To find test cases created by a specific user: `-q dcterms:creator=@""tanuj"""`

To find all test cases don't specify -q

To find all test cases with a "Validates Requirement" link: `-v oslc_qm:validatesRequirement`

To find all test cases without a "Validates Requirement" link: `-n oslc_qm:validatesRequirement`

*Application queries:*

To find all Configurations (the default for the app) in your ETM server: `oslcquery -A qm -O allqmconfigs.csv`

To find all Configurations which are baselines in your ETM server: `oslcquery -A qm -q "oslc_config:mutable=""false""^^xsd:boolean"`

To find all Components in your ETM server: `oslcquery -A qm -r Component -O allqmcomponents.csv`


DN Basic usage
==============

To get the identifier and title of all artifacts in a non-configuration managed project (replace the server:port, APPSTRING and username/password with values for your server):
```
oslcquery -J https://my.server:port -U YOURUSERNAME -P YOURPASSWORD -p "My RM Project" -s dcterms:identifier,dcterms:title -O rmresults.csv
```

To get the identifier and title of all artifacts in a component stream:
```
oslcquery -J https://my.server:port -U YOURUSERNAME -P YOURPASSWORD -p "My RM Project" -F "stream name" -s dcterms:title -O rmresults.csv
```

The first four rows of results might look like this, with the first column $uri is the resource URI.

|$uri|dcterms:identifier|dcterms:title|rm_nav:parent|
|----|:----------------:|-------------|-------------|
|https://jazz.ibm.com:9443/rm/materializedviews/VW_CMPEA0B5Eeuh3Iiax2L3Ow||Gold Plating||
|https://jazz.ibm.com:9443/rm/resources/MD_COUvCkB5Eeuh3Iiax2L3Ow|912|AMR System Requirements Specification|/01 Requirements|
|https://jazz.ibm.com:9443/rm/resources/MD_COUvEEB5Eeuh3Iiax2L3Ow|913|Upload Usage Data Locally|/Use Case Content|
|https://jazz.ibm.com:9443/rm/resources/MD_COUvDkB5Eeuh3Iiax2L3Ow|914|Use Case Template|/Module Template|

This `oslcquery` application enforces that results always include dcterms:identifier and rm_nav:parent (which if the artifact is a core artifact shows the folder path) and by default are sorted by increasing identifier - to disable sorting use the `-S` option.

The first row of results doesn't have an identifier, because it's a Collection. If you want to see the format of a result row, add `rdf:type` to the select open -s like this: `-s dcterms:title,rdf:type` and you'll get results like this:

|$uri|dcterms:identifier|dcterms:title|rdf:type|rm_nav:parent|
|----|:----------------:|-------------|------------------------|-------------|
|https://jazz.ibm.com:9443/rm/materializedviews/VW_CMPEA0B5Eeuh3Iiax2L3Ow||Gold Plating|jazz_rm:Collection||
|https://jazz.ibm.com:9443/rm/resources/MD_COUvCkB5Eeuh3Iiax2L3Ow|912|AMR System Requirements Specification|jazz_rm:Module|/01 Requirements|
|https://jazz.ibm.com:9443/rm/resources/MD_COUvEEB5Eeuh3Iiax2L3Ow|913|Upload Usage Data Locally|jazz_rm:Module|/Use Case Content|
|https://jazz.ibm.com:9443/rm/resources/MD_COUvDkB5Eeuh3Iiax2L3Ow|914|Use Case Template|jazz_rm:Module|/Module Template|

Now you can see if the results are collections and modules - further down the results show other values such as Text.


DN Advanced usage examples
==========================

DN can provide query capability for resource types `oslc_rm:Requirement` (which is the default), `rm_nav:folder`, `rm_view:View` and `rm_reqif:ReqIFDefinition` - there are examples of queries on all these these below.. NOTE that different resource types may not provide the same query functionality.

If your DN application is not on context root /rm then use the -A option for example for context root /rm1 and gc on /gc1, then add the option `-A rm:rm1,gc:gc1`

Use the typesystem report to see all the shapes, properties and enumeration names in your project: add `-typesystemreport file.html` to the commandline. Note not all properties are queryable.

If the title of a module (or anything) includes a double-quote " then you have to escape it with \\ and double the quote to "" so it becomes \\"" in the command line. For example to find a module with title `A "specification"` use `-q "dcterms:title=""A \\""specification\"""""`

You can add a filter like `-v rm_nav:parent` to only show results where parent isn't empty - i.e. to get only core artifacts - unfortunately this filters can only be done by postprocessing the query results so it doesn't speed up the query itself.

The converse filter is `-n rm_nav:parent`, which post-filters out results where parent is empty, i.e. only returns module artifacts. You can use -n and -v but that only makes sense (i.e. if you want to possibly get some results) if they reference different attributes.

You can use a global configuration name with a DN query on a project and it will return resources matching the query which are in components which have a configuration contributing to that GC. To use a global configuration you *must* include gc in the --APPSTRING after rm, e.g. -A rm,gc (it is included as /gc by default).

Use the type system report to see all the shapes, properties and enumeration names: add `--typesystemreport file.html` to the commandline - the report will be saved to file.html and the file opened in your default browser.

To find resources of a specific type e.g. Stakeholder Requirement: `-q oslc:instanceShape='Stakeholder Requirement'`

Because of DN's data model (which is different from EWM) all properties can be queried and will return matching results whatever the shape (artifact type). So if in the typesystem report you see Priority below a shape "Stakeholder Requirement" if you use query `-q Priority=High` you will get results from all artifact types where the resource has a Priority property with value High.

To find all artifacts in project, where the project e.g. rm_gc_p1 has one or more components (in this case two components) which contribute to the global configuration 'gccomp Initial Development' in GCM project gcproj: `rm_gc_p1 -E gcproj -G "gccomp Initial Development"` - NOTE this returns all artifacts from all components which have a contribution into the global configuration, using the local configuration which is the contribution from each component.

To find high-priority artifacts (of all artifact types): `-q Priority=High`

To find high-priority Stakeholder Requirements: `-q "oslc:instanceShape='Stakeholder Requirement' and Priority=High"`

To find artifacts in a specific folder: `-q "rm_nav:folder=$""01 Requirements"""`

To find artifacts in a specific folder using path: `-q "rm_nav:folder=$""01 Requirements/Engine"""`

To find artifacts created by a specifc user: `-q "dcterms:creator=@""tanuj"""`

To find artifacts with a specific title: `-q "dcterms:title=""Money that Matters"""`  NOTE DN doesn't appear to support wildcards in string comparisons - you could try using -f/--searchterms for approximate match.

To find artifacts which are collections: `-q rdf:type=jazz_rm:Collection`

To get all artifacts in a project/component: don't specify -q (use with care, can place a large load on your DN server)

To find all modules: `-q rdf:type=jazz_rm:Module`

To find all resources which are modules and also retrieve their RDF XML to file too, into an existing subdirectory 'modules' with file names starting 'mod_': `-q rdf:type=jazz_rm:Module -X modules\mod` - NOTE the files are named for the identifier of the artifact.

All Text format core artifacts: `-q rdf:type=jazz_rm:Text -v rm_nav:parent`

All Text format artifacts (in modules): `-q rdf:type=jazz_rm:Text -n rm_nav:parent`

All wrapped resources: `-q rdf:type=jazz_rm:WrapperResource`

To find artifacts modified after a specific date-time: '-q "'Modified On'>""2020-08-01T21:51:40.979Z""^^xsd:datetime"' - note that DN requires specifying the `^^xsd:datetime`, unlike EWM

To find all artifacts with identifiers (i.e. no Collections in result): `-v dcterms:identifier`

For DN >=7.0 - to find all artifacts with a word somewhat like 'Operational' using OSLC Query searchterms: `-f Operational`

To find all artifacts with outgoing link "Satisfies": `-v Satisfies`

To find all artifacts without outgoing link "Satisfies": `-n Satisfies`

To find all System Requirements with outgoing Satisfies link: `-q "oslc:instanceShape='System Requirement'" -v Satisfies`

To find all System Requirements without outgoing Satisfies link: `-q "oslc:instanceShape='System Requirement'" -n Satisfies`

To include Satisfies link in output file: `-s Satisfies -O artifacts_including_satisfaction.csv`

To find all artifacts in any component in an opt-in DN project which has one or more components contributing to a global configuration called e.g. `gccomp Initial Development' in a GC project called 'gcproj': `-A rm,gc -E gcproj -G "gccomp Initial Development"`

To query for folders: there is a pre-defined prefix `rm_nav` defined which allows using the folder query capability like this: `oslcquery myproject -r rm_nav:folder` NOTE DN does not handle any select or where parameters to this query.  NOTE this returns the result of the Folder Query Capability which is just the root folder shown as "/" - an option to retrieve all folders isn't currently provided by oslcquery - this requires a series of queries, the next one being from the root folder.

To query for views: there is a prefix `rm_view` defined which allows using the view query capability like this: `oslcquery myproject -r rm_view:View`

To query for Reqif definitions: there is a prefix `rm_reqif` defined which allows using the Reqif definition query capability like this: `oslcquery myproject -r rm_reqif:ReqIFDefinition`. For information and limitations of Reqifdefinition query, see https://jazz.net/wiki/bin/view/Main/DNGReqIF

To find all artifacts in project/component in a specific module id 3892 `-q rm:module=~3892` - NOTE this is using the enhanced OSLC Query syntax (see below)

To find all artifacts in project/component in a specific module id 3892 modified since a specific date `-q rm:module=~3892 and dcterms:modified>"2020-08-01T21:51:40.979Z"^^xsd:dateTime` - NOTE this is using the enhanced OSLC Query sytnax for finding an artifact by id using ~

To find all artifacts in project/component in a specific module id 3892 modified before a specific date `-q rm:module=~3892 and dcterms:modified<"2020-08-01T21:51:40.979Z"^^xsd:dateTime` - NOTE this is using the enhanced OSLC Query sytnax for finding an artifact by id using ~

To totalize a column which has multiple results replacing them with a count of the number of results, which might be useful for example to get a count of artifacts in each module, use a query for modules `rdm_types:ArtifactFormat=jazz_rm:Module` and select `oslc_rm:uses` then use the -I option. Because this doesn't need name resolution which can slow the query and post-processing down when processing many modules, also use -R and -Q - for results from components across a GC `/gc/configuration/26` in GCM project `gcproj` the query looks like: `-s oslc_rm:uses,dcterms:title -q rdf:type=jazz_rm:Module -G 26 -E gcproj` - the result is a spreadsheet containing the module URI, the module name and identifier and a column with the count of artifacts in the module. You can improve performance (assuming you don't need friendly names, and counting artifacts/module doesn't really need friendly names) by suppressing the reading of the type system using `-Q` and `-R`, and because the results will be large you may consider carefully whether to suppress paging by using `--pagesize 0`.

If you have a project with many components and/or configurations, you may observe that startup is slow - this is because by default if you don't specify a component then oslcquery reads all the components in the project and all the configurations in each component so that it can find the configuration which might be in any component. As of version 0.10.0 you can reduce this cost in a few ways: - most basic is to specify a component using -C, when you do this oslcquery only reads the configurations for that component. The next is to specify a component using `-C` and GC as well - using `-E` and `-G` -and also as a local configuration using `-F` - `oslcquery` will find the contribution to the GC for that component. If you only specify a GC configuration (usinging `-E` and `-G`) then oslcquery won't read RM components or configurations and the query will work on the project returning results from all contributing componenets in the project.

If there are very many results then paging can add significant cost - you may want to suppress paging using `--pagesize 0` but BE CAREFUL not to impact on other users!

GCM basic usage
===============

GCM provides both project and application queries. Wherever possible use the project queries because they require less server projecessing.

To get the details of all gc configurations in a project (replace the server:port, APPSTRING and username/password with values for your server):
```
oslcquery -J https://my.server:port -U YOURUSERNAME -P YOURPASSWORD -A gc -p "My GC Project" -O gcmresults.csv
```

To get the details of all components in a project:
```
oslcquery -J https://my.server:port -U YOURUSERNAME -P YOURPASSWORD "My RM Project" -F "stream name" -s dcterms:title -O rmresults.csv
```

To get all gc configurations in the GCM application, don't specify the `-p projectname`, e.g.:
```
oslcquery -J https://my.server:port -U YOURUSERNAME -P YOURPASSWORD -A gc -O gcmresults.csv
```

To get all gc components in all GCM project, specify the Configuration resource type:
```
oslcquery -J https://my.server:port -U YOURUSERNAME -P YOURPASSWORD -A gc -r Configuration -O gcmresults.csv
```


GCM Advanced usage examples
==========================

GCM projects can provide query capability for a number of different resource types - get a typesystem report to see the list. The default resource type is `oslc_config:Configuration` - the short way to specify this is `-r Configuration`, although this is the default so no need to specify, another commonly used resource type is Component specified using `-r Component`.

The GCM app can provide query capabilities for Component and Configuration, default is Configuration, as well as a number of other resource types - get a typesystem report to see the list.

If your GCM application is not on context root /gc then use the -A option for example for context root /gc1 add the option `-A gc:gc1`


Enhanced OSLC Query syntax
==========================

The basic query syntax is as per https://docs.oasis-open.org/oslc-core/oslc-query/v3.0/csprd01/oslc-query-v3.0-csprd01.html#oslc.where

Enhancements provided within an OSLC Query are:
* You can reference a shape, property and enumeration simply by using its name, e.g. `Priority=High`, or if a name includes a space character then surround it with single quotes ', for example `oslc:instanceShape='Stakeholder Requirement'`
* You can reference the name of a user by prefixing the name with @ e.g. `dcterms:creator=@"tanuj"` - The user name will be checked that it exists on the server (i.e. on the jts)
* For DN you can reference the name of a folder by prefixing the name with $ e.g. `rm_nav:parent=$"00 Requirements"` - NOTE If a folder name is unique you don't have to specify its path. Otherwise start the string with / and specify the full folder path finishing with the desired folder name
* For DN you can reference a single core artifact e.g. id 1234 using syntax ~1234 - you can use this on the rhs of a query like `Satisfies=~1234` os `"Satisfies in [~1234,~7890]"` to match links to the core artifact - there's no way of specifying that the link must be from a core artifact - you can do that by adding e.g. `-v rm_nav:parent` to filter out non-core artifacts.
* For DN you can reference any number of module artifacts for e.g. id 1234 using syntax *1234 - NOTE you can only use this as a query like `"Satisfies in [*1234,*7980]"` to match links to any number of (reused) module artifacts with that ID.
* For DN to reference a module by name use ^"module name" (quotes are required even if module name doesn't have a space)
* For EWM some property names are repeated on different shapes (work item types), and all properties are shape-specific (apart from `rtc_cm:type`). To refer to a shape-specific property use e.g. `Defect.Status` - if a name includes a space then put ' around it e.g. `Defect.'Work Status'` or `'Task Item'.'Work Status'
* For EWM Some property names are repeated within a shape - in this case an alternate name (altname) is displayed in the type system report - use the altname instead of the property name.
* There are built-in RDF prefixes which can be displayed using the type system report.
* This isn't part of the query syntax, but options -n and -v will post filter the query results to keep only artifacts with the named property not present (-n) or present (-v). This is useful to filter query results for example for DN to keep only resources with a Satisfies link by specifing `-v Satisfies`, or without a Satisfies link by specifying `-n Satisfies`.

Combining OSLC queries:
* Apart from the `in` test, OSLC Queries are logical 'and' - no doubt this keeps the implementation simpler, but it can feel limiting, so this application provides syntax to combine multiple queries set-wise by surround each query with brackets ( ) with OR and AND syntax.
* By bracketing each OSLC query, these can be combined with set intersection (&&) and union (||) - NOTE that this is post-processing, i.e. each of the OSLC Queries is made in full and then the results combined based on the resource URI. Each query selects the same properties, and each resource only appears in the overall results once. For example (although not sure this particular example makes much sense):
```
     -q "( Status=Approved ) ||  ( ( Status=Rejected and Priority=Low ) && ( Severity=High) )"
```
NOTE this example will require three queries to be made to your server, one for each bracketed OSLC Query.


Using names for Projects and Configurations
===========================================

You have to specify a project and possibly a local configuration using its name. If that name isn't unique then you're stuck - but having non-unique project/configuration names is a recipe for user confusion, so really that's something you should sort out by making configuration names within a project/component different.

When specifying a global configuration you can use its name or its short id which is an integer. If the name isn't unique you also have to specify the project. If the configuration name still isn't unique then you can use its short ID, but see the previous paragraph observation about non-unique names being a recipe for user confusion.


Server URLs, user IDs and Passwords, and obfuscated credentials
===============================================================

Your query has to know what server URL to use, what the context roots for the jts and your target application are, what user id and what password to use for authentication.

To specify these there are a range of methods, from simplest (but needs most typing) to, err, better:

* The simplest way to provide your credentials is to specify them explicitly on the commandline whenever you run oslcquery.
```
oslcquery -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 "My Project" -q dcterms:identifier=43
```

* A less intrusive method useful if you're mostly querying one application is to set environment variables - NOTE you can override these on the commandline:
```
set QUERY_JAZZURL=https://myserver:port
set QUERY_USER=measadmin
set QUERY_PASSWORD=secret
set QUERY_APPSTRING=rm:rm1,jts:jts23
oslcquery "My Project" -q dcterms:identifier=43
```

* Using obfuscated credentials

You can create a file containing obfuscated details which are very convenient particularly if wanting to query against multiple applications, because you just specify the credentials file corresponding to the server you want to use. The file content is encrypted, but as the source code is available it isn't terribly difficult to figure out how this done, which is why the term 'obfuscation' is used here; unless you take the option to provide a runtime password then the obfuscation can with some work be de-obfuscated. There are some basic protections against simply copying the credentials file built into the obfuscation irrespective of using the commandline or runtime password.

If you use an obfuscated creds file it will override both the environment variable and commandline options.

**NOTE the credentials file is only obfuscated, i.e. it's relatively easy to decode unless you use the runtime pormpt option -4.**

To create and then use an obfuscated credentials file specify these details once on the command line with the `-0` option to create a credentials file, then to use these specify the filename after the `-1` option e.g.:
```
oslcquery -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -0 .mycreds

oslcquery -1 .mycreds "My Project" -q dcterms:identifier=23 -O rmresults.csv
```

Optionally add a commandline password (secret) using `-4` when creating and when using the credentials file:
```
oslcquery -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -0 .mycreds -3 commandlinesecret

oslcquery -1 .mycreds -3 commandlinesecret "My Project" -q dcterms:identifier=23 -O rmresults.csv
```

Optionally use a runtime prompt for the credentials file password using `-4` when creating and when using the credentials file - NOTE if you forget what the runtime password is you will have to delete the creds file and recreate it, i.e. there's no password recovery optiopns :-o
```
oslcquery -J https://myserver:port -U measadmin -P secret -A rm:rm1,jts:jts23 -1 .mycreds -4
Password (>0 chars, longer is more secure)?

oslcquery -1 .mycreds -4 "My Project" -q dcterms:identifier=23 -O rmresults.csv
Password (>0 chars, longer is more secure)?
```

To erase obfuscated credentials use option -2 then the credentials filename:
```
oslcquery -2 .mycreds
```

TO BE CLEAR: **NOTE the credentials file is only obfuscated, i.e. it's pretty easy to decode once you have the python source code unless you use the runtime pormpt option -4.**


Running a batch of queries, for regression testing or to automate data export
=============================================================================

There is an experimental (i.e. unfinished) `batchquery` application which can be used to do a simple regression test or to automate a series of queries. Examples of tests and results are below the tests folder. The example tests are in `test.xlsx` - it currently contains >60 tests across all four ELM applications and also simple tests for the obfuscated credentials options.

At this stage in the development of `batchquery` regression testing is very simply by comparing the number of results retrieved with an expected number. Obviously the tests specified in the spreadsheet relate to the data source tested aginst so you will have to adapt the spreadsheet with the data available to you.

The column headings mostly refer to options of `oslcquery` - if a cell is empty the option isn't provided for that row.

If you want a row to not do a comparison of the number of results, empty the NResults cell on that row.

NOTE that the spreadsheet is case-sensitive! Don't remove columns.

Usage for `batchquery` is:

```
usage: batchquery_app.py [-h] [-d] [-f] [-g GROUP] [-j JUST] [-L LOGLEVEL] [-s] [-t] [-w SHEETNAME] [-W] spreadsheet

Perform OSLC query on a Jazz application, with results output to CSV (and other) formats - use -h to get some basic help

positional arguments:
  spreadsheet           Name of the xlsx spreadsheet with tests

optional arguments:
  -h, --help            show this help message and exit
  -d, --dryrun          Dry run - show commandline but don't run the OSLC Query
  -f, --stoponfail      Stop at first failure
  -g GROUP, --group GROUP
                        Comma-separated list of regex pattern to match groups to be run, in the worksheet Group column
  -j JUST, --just JUST  Comma-separated list of tests to run, matching the TestId column in the worksheet
  -L LOGLEVEL, --loglevel LOGLEVEL
                        Set logging level - default is None - choose from INFO/DEBUG/ERROR
  -s, --save            UNFINISHED Retrieve and save query results forever (used to save reference for -t testing
  -t, --test            UNFINISHED Retrieve data and do comparison to test that results match saved results from -s
  -w SHEETNAME, --sheetname SHEETNAME
                        Name of the worksheet with tests (if not specified the workbook must only have one worksheet, whch is used)
  -W, --cachecontrol    Used once -W erases cache for the first test then continues with caching enabled. Used twice -WW wipes cache and disables caching.
```

To run all tests:

```
batchquery tests\tests.xlsx
```

You can configure for your username, password and ELM jazz url on row 2 in columns V, W and X - these will be copied to all rows below.

You can use option -j with a comma-separated list of test numbers to run just those rows that match in the TestId column - e.g. -j 101,131

You can use -g to specify a comma-separated list of regular expressions to run only a tagged group of tests with all matching tags in the Group column - e.g. -g rm-all,basic, or -g .*-all will run every row with a tag ending in -all. or -g rm-all,7x wil run only tests with both rm-all and 7x in the Group column.


When things go wrong
====================

Error handling isn't very sophisticated in this code - you're likely to get a long unwieldy Python exception message which isn't very helpful if you don't know the source code, but there may be an error message printed at the end which summarises why the exception happened.

If you get the results but not what you expect you should confirm that your server is on the latest iFix, because API defects do happen and get resolved in later iFixes.

The most basic problem is going to be if `oslcquery` can't authenticate you. Testing has been done against servers using form- and JAS-based (OIDC) authentication. SPNEGO and smartcard haven't been tested so those and Other methods of authentication may need some additional code. Test your authentication using the simplest possible command like `oslcquery -p myproject -A username -P userpassword -J https://my.jazz.uri.com:9443`.

Once authenticated the most likely error you'll make in a query is mis-spelling the name of a project, configuration, shape, property, enumeration, etc. - and note that these are all case-sensitive - what you use has to match the definition in the server. Use the typesystem report to find the allowed names for shapes, properties and enumerations.

Another common problem is due to the way than when a CSV file is open in Excel it locks the CSV file and it can't be overwritten, so if while the file is open in Excel you re-run your query to write to the same file, you'll get an error message. You have to close the CSV file to overwrite it.

If the resource you expect isn't visible in the results, check it actually has the properties and values specified in the query. Try simplifying the query until you can see the resource, then build the conditions in the query up one by one until you find out which one is not matching when you were hoping it would.

If the resource is in the results but a property value isn't returned for it, check you spelled it correctly in the select you specified - there are no error messages if these are wrong. It's possible that the property isn't visible through OSLC Query. It's alos possible the applicatin is ignoring your `select` settings - this is allowed by the OSLC Query specification.

It may be helpful to trace the messages to/from the server with a https-capable proxy like Telerik Fiddler Classic. This shows the HTTP GET going to the server, and the response coming back. If you need to see the full detail of the preparation of the query, and of post-processing, then use the -W option on the commandline to clear cached data, because otherwise the data which is already in the cache won't be fetched from your server.

You can increase the logging level to get information about the processing being done. To do this add `-L INFO` for a moderate view of particularly the typesystem, query parsing and processing. Set logging to `-L DEBUG` to get all the gory details including requests/responses to the server. As well as being shown on screen, logging is also written to a timestamped file in the logs folder for each run of `oslcquery`.

Otherwise, well, you have the source code, perhaps you can debug for yourself what's going wrong? If you find a bug or fix a bug please create an issue on github.com



Future work
===========

* Try to make the type system implementation more uniform and complete accross the different ELM applications
* Do more work on EWM and ETM querying, so e.g. link types can be referred to by name
* Tidy up the internal coding of type system
* Bring more of the APIs uinto the elmclient, for example  DN reqif, reportable REST and module APIs.
