##
## © Copyright 2022- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

#
# convert elmclient log file into a sequence diagram in a html page
# reuses https://bramp.github.io/js-sequence-diagrams/
#

import argparse
import base64
import glob
import html
import io
import json
import os.path
import re
import urllib.parse
import webbrowser
#import xml.etree.ElementTree as ET
import lxml.etree as ET

import jinja2

#
# Example of syntax (from https://bramp.github.io/js-sequence-diagrams/):
# 
# Title: Here is a title
# A->B: Normal line
# B-->C: Dashed line
# C->>D: Open arrow
# D-->>A: Dashed open arrow
# # Example of a comment.
# Note left of A: Note to the\n left of A
# Note right of A: Note to the\n right of A
# Note over A: Note over A
# Note over A,B: Note over both A and B
#

JINJA_TEMPLATE = """
<!doctype html>
<html>
<head>
    <link rel="stylesheet" type="text/css" href=""https://bramp.github.io/js-sequence-diagrams/css/sequence-diagram-min.css" media="screen" />
<style>
    .signal text {
    fill: #000000;
}
.signal text:hover {
    fill: #aaaaaa
}
.note rect, .note path {
    fill: #ffff80;
}
.title rect, .title path{
    fill: #ff80ff;
}
.actor rect, .actor path {
    fill: #80ffff
}

</style>
</head>
<body onload='showseq();'>
<p>Sequence diagram from emlclient log {{ logfilename }} - wait a few seconds for the diagram to appear...</p>

<div id="diagram"></div>

<script src="https://cdn.jsdelivr.net/npm/underscore@1.13.2/underscore-umd-min.js" ></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/webfont/1.3.0/webfont.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/snap.svg/0.5.1/snap.svg-min.js" ></script>
<script src="https://bramp.github.io/js-sequence-diagrams/js/sequence-diagram-min.js" ></script>

<script type="text/javascript"> 
function showseq(){
//  console.log("Hello2");
  var seqdiv =  document.getElementById("sequence");
  seqtext = seqdiv.textContent
  var d = Diagram.parse(seqtext);
  var options = {theme: 'simple'};
  d.drawSVG('diagram', options);
}
</script>
<p>Created using <a href='https://github.com/bramp/js-sequence-diagrams'>js-sequence-diagrams</a> see examples <a href='https://bramp.github.io/js-sequence-diagrams/'>here</a><p>

<div id="sequence" style="display: none;">{{ seq }}</div>

</body>
</html>
"""

# these are case-sensitive
reqshowheaders=[
    'Accept',
    'Configuration-Context',
    'Content-Type',
    'Cookie',
    'DoorsRP-Request-Type',
    'If-Match',
    'net.jazz.jfs.owning-context',
    'OSLC-Core-Version',
    'Referer',
    'vvc.configuration',
]

# these are case-sensitive
respshowheaders=[
    'ETag',
    'Content-Type',
    'Content-Length',
    'Location',
    'Set-Cookie',
    'WWW-Authenticate',
    'X-jazz-web-oauth-url',
    'X-JSA-AUTHORIZATION-REDIRECT',
    'X-JSA-AUTHORIZATION-URL',
    'X-JSA-LOGIN-REQUIRED',
]

# these are case-sensitive
ignore_mimetypes=[
    "application/javascript",
    "application/octet-stream",
    "application/x-javascript",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/svg+xml",
    "image/x-icon",
    "text/css",
    "text/javascript",
]


def sanitise( s, *, width=60, wrap=True, clip=None, maxlines=0 ):
#    print( f"Sanitising {s=}" )
    results = []
    s0 = s
    s=s.replace('\n',"\\n")
    s=s.replace('\r',"")
    s=s.replace('\\r',"") # to tidy up JSON
    slines = s.split("\\n")
#    print( f"{len(slines)=}" )
    if wrap:
        lines = 0
        while s[:width] and (maxlines==0 or lines<maxlines):
            lines += 1
            results.append( s[:width] )
            s = s[width:]
    elif clip:
        if len(s)>clip:
            results.append( s[:clip]+"..." )
        else:
            results.append( s[:clip] )
    else:
        if maxlines>0:
#            print( f"{maxlines=}" )
#            print( f"{len(slines)=}" )
            if len(slines)>maxlines:
                slines = slines[:maxlines]+['...']
            else:
                slines = slines[:maxlines]
            
        results.extend(slines)
#    return html.escape("\\n".join(results))
    result = "\\n".join(results)
    if result.startswith( "<?xml" ) or result.startswith( "<rdf" ):
        print( f"is xml {result[:4]}" )
        len1 = len( result )
        tree = ET.fromstring( result.encode() )
        len3 = len( ET.tostring( tree ) )
#        ET.indent( tree, space="           " )
        result2 = ET.tostring( tree, pretty_print=True ).decode()
        len2 = len( result2 )
        print( f"{len1=} {len3=} {len2=}" )
        result = "<pre>"+html.escape( ET.tostring( tree, pretty_print=True ).decode() )+"</pre>"
    else:
        print( f"not xml {result[:4]}" )
        result = html.escape( result )
    return result

def addheaders(events,msgheaders,headerstoshow,direction):
    msgs = []
    for header,value in sorted(msgheaders):
        if header in headerstoshow:
            if header == "Cookie":
                cookies = value.split("; ")
                msgs.extend( [f"{sanitise('Cookie: '+c, wrap=False, clip=50)}" for c in cookies] )
            else:
                msgs.append( f"{sanitise(header+': '+value, wrap=False, clip=50)}" )
    if msgs:
        text = '\\n'.join(msgs)
        events.append( f"Note {direction}: {text}" )
    return
    
# parse a message from the logfile into a request/response tuple
def decodemessage(msg):
    request = {'intent':None,'method': None, 'url': None, 'headers':[], 'body':None}
    response = {'status': None,'headers':[], 'body':None, 'action':None }
    parts = re.search( r"\n*(?:INTENT: ([^\n]*?)\n+)?(?:(?:(GET|PUT|POST|HEAD|DELETE|POST) +(\S+)\n((?: +.*?\n)+)\n*)(?::+?=\n(.*?)\n-+?=\n)?.*?\n+Response: (\d+?)\n( .*?)\n\n(?::+?@\n(.*?)\n-+?@\n+)?)?(?:ACTION: (.*?)\n)?",msg, flags=re.DOTALL )
    if parts.group(0) == '':
        raise Exception( "formatting wrong!" )
#    for l,g in enumerate(parts.groups()):
#        print( f"{l=} {g=}" )
    request['intent'] = parts.group(1)
    request['method'] = parts.group(2)
    request['url'] = parts.group(3)
    if parts.group(4) is not None:
        for hdrline in parts.group(4).split( "\n" ):
            hsplit = hdrline.strip().split(": ",1)
            hsplit.append("")
            hdr, value = hsplit[0],hsplit[1]
            request['headers'].append( (hdr,value) )
    request['body'] = parts.group(5).strip() if parts.group(5) else None
    response['status'] = parts.group(6)
    if parts.group(7) is not None:
        for hdrline in parts.group(7).split( "\n" ):
            hsplit = hdrline.strip().split(": ",1)
            hsplit.append("")
            hdr, value = hsplit[0],hsplit[1]
            response['headers'].append( (hdr,value) )
    response['body'] = parts.group(8).strip() if parts.group(8) else None
    response['action'] = parts.group(9)
    return (request,response)
    
def findheader(hdrname,requestorresponse,notfoundreturn=None):
    for h,v in requestorresponse['headers']:
        if hdrname == h:
#            print( f"FOUND {h=} {v=}" )
            return v
    print( f"Not found {hdrname}" )
    return notfoundreturn

def contentshouldbeshown(requestorresponse):
    # find Content-Type header
    contenttype = findheader("Content-Type",requestorresponse)
    # check it
    if contenttype:
        if contenttype.startswith("application"):
            return True
    return False
    
def isinteger(s):
    try:
        return int(s)>=0
    except:
        pass
    return False
    
#
# Input options:
# Either params are: an ordinal of the receness of the log (0 is latest, 1 is second, etc.)
# Or a filename
#
# output filename
#
def main():
    parser = argparse.ArgumentParser(description="Convert Log file to html page of sequence diagram using https://github.com/bramp/js-sequence-diagrams")
    
    parser.add_argument( "logfile", nargs='*', default=[], help="The names or ordinals of the log file - use 0 (or nothing) to convert the most recent log, 1 for the second newest, etc. OR specify the explicit filenames" )
    parser.add_argument('-o', '--outputfolder', default=None, help=f'Folder for output files')

    args = parser.parse_args()

    # if no logfile specified, assert at least the most recent logfile
    args.logfile = args.logfile or [0]
    
    for logfile in args.logfile:
        if os.path.isfile(logfile):
            pass
        else:
            # see if it's an integer
            if isinteger(logfile) and int(logfile)>=0:
                logfileno = int(logfile)
                alllogs = sorted(glob.glob("logs/*.log"), key=os.path.getctime,reverse=True)
                if not alllogs:
                    raise Exception( "No logs in logs folder!" )
                if logfileno>len(alllogs):
                    raise Exception( f"You asked for index {logfile} but there are only {len(alllogs)} logs!" )
                logfile = alllogs[logfileno]
                print( f"Selected log {logfileno} file {logfile}" )
            else:
                raise Exception( f"{logfile} is neaither a real file nor an integer >0 to indicate the index from most recent (0) to older" )
                
        outname = os.path.splitext(logfile)[0]+".html"
        
        if args.outputfolder:
            outfile = os.path.join(args.outputfolder, outname )
        else:
            outfile = os.path.abspath(outname)
            
        print( f"Processing {logfile} to {outname}" )
        
        log = open(logfile,'rt').read()
        
        # find all the messages using the markers put in by httpops.py
        msgs = re.findall(r"^>>>>>>>>+!\n(.*?\n)<<<<<<+!",log, flags=re.DOTALL + re.MULTILINE)
        
        if not msgs:
            raise Exception( "No messages in {logfile} - you probably need to add option -L TRACE" )
        
        events = []
        host = "elm"

        # find the commandline to put in the title of the sequence diagram
        if cmdline := re.search( r"COMMANDLINE: (.*)", log ):
            cmd = cmdline.group(1)
            events.append( f"Title: Command: {cmd}" )
            
        events.append( f"participant me" )
        events.append( f"participant {host}" )
        
        for i,msg in enumerate(msgs):
            request,response = decodemessage(msg)
#            print( f"{request=}" )
#            print( f"{response=}" )
            line = i
            
            if request['method']:

                reqparts = urllib.parse.urlparse(request['url'])
                
                path = reqparts.path
                if reqparts.query:
                    path += "?"+reqparts.query

                #  if INTENT: then add a note for it
                if request['intent']:
                    events.append( f"Note left of me: INTENT: {request['intent']}" )
                    
                events.append( f"me->{host}: {request['method']} {sanitise(path,wrap=True)}" )
                
                addheaders(events,request['headers'],reqshowheaders,"left of me" )
                
                if request['body']:
                    if contentshouldbeshown(request):
                        reqbody = sanitise(request['body'], wrap=True)
                    else:
                        reqbody = sanitise(request['body'], wrap=False, maxlines=5)
                        
                    if reqbody:
                        events.append( f"Note left of me: {reqbody}" )
                        
                events.append( f"{host}-->me: {response['status']}" )
                
                addheaders(events,response['headers'],respshowheaders,f"right of {host}" )
                
                if response['body']:
                    if contentshouldbeshown(response):
                        respbody = sanitise(response['body'], wrap=False)
                    else:
                        respbody = sanitise(response['body'], wrap=False, maxlines=5)
    #                    respbody = "Content type not shown..."
                   
                    events.append( f"Note right of {host}: {respbody}" )
                
            #  if ACTION: then add a note for it
            if response['action']:
                events.append( f"Note over me: {response['action']}" )

        j2_template = jinja2.Template(JINJA_TEMPLATE)
        data = {
            'seq': "\n".join(events),
            'logfilename': os.path.basename(logfile),
        }
        
        # save to file
        open(outfile,"wt").write( j2_template.render(data) )
        
        # display the report
        url = f'file://{os.path.abspath(outfile)}'
        webbrowser.open(url, new=2)  # open in new tab

if __name__=="__main__":
    main()
    