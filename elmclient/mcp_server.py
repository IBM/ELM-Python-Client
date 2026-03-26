##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##

"""
MCP (Model Context Protocol) server for elmclient.

Exposes ELM functionality as tools for AI assistants.
See https://modelcontextprotocol.io/ for the MCP specification.

Usage:
    elm-mcp-server                          # stdio transport (default)
    elm-mcp-server --transport sse          # SSE transport

Configuration via environment variables:
    ELM_HOST        - Jazz server URL (required)
    ELM_USER        - Username (required)
    ELM_PASSWORD    - Password (required)
    ELM_JTS_CONTEXT - JTS context path (default: 'jts')
    ELM_VERIFY_SSL  - Verify SSL certificates (default: 'true')

Alternatively, provide a JSON credentials file at ~/.elm_credentials.json:
    {"host": "https://...", "username": "...", "password": "..."}
"""

import json
import logging
import os
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "MCP server requires the 'mcp' package. "
        "Install with: pip install 'elmclient[mcp]'",
        file=sys.stderr,
    )
    sys.exit(1)

import elmclient.server as elmserver
import elmclient.rdfxml as rdfxml

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "elm",
    instructions=(
        "IBM ELM (Engineering Lifecycle Management) server. "
        "Query work items, requirements, and test artifacts."
    ),
)

OSLC_PREFIXES = {
    "http://purl.org/dc/terms/": "dcterms",
    "http://open-services.net/ns/cm#": "oslc_cm",
}

CRED_FILE = os.path.expanduser("~/.elm_credentials.json")

_connections: dict = {}


def _load_config() -> dict:
    """Load connection config from environment or credentials file."""
    host = os.environ.get("ELM_HOST")
    if host:
        return {
            "host": host,
            "username": os.environ["ELM_USER"],
            "password": os.environ["ELM_PASSWORD"],
            "jts_context": os.environ.get("ELM_JTS_CONTEXT", "jts"),
            "verify_ssl": os.environ.get("ELM_VERIFY_SSL", "true").lower() == "true",
        }
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE) as f:
            data = json.load(f)
        return {
            "host": data["host"],
            "username": data["username"],
            "password": data["password"],
            "jts_context": data.get("jts_context", "jts"),
            "verify_ssl": data.get("verify_ssl", True),
        }
    raise RuntimeError(
        f"ELM credentials not found. Set ELM_HOST/ELM_USER/ELM_PASSWORD "
        f"environment variables or create {CRED_FILE}"
    )


def _get_server():
    if "server" not in _connections:
        cfg = _load_config()
        _connections["server"] = elmserver.JazzTeamServer(
            cfg["host"],
            cfg["username"],
            cfg["password"],
            verifysslcerts=cfg["verify_ssl"],
            jtsappstring=cfg["jts_context"],
            appstring="ccm",
            cachingcontrol=0,
        )
        _connections["config"] = cfg
    return _connections["server"]


def _get_app(domain: str = "ccm"):
    key = f"app_{domain}"
    if key not in _connections:
        server = _get_server()
        _connections[key] = server.find_app(domain, ok_to_create=True)
    return _connections[key]


def _find_query_base(project):
    """Find the OSLC query base URI for a project."""
    services_xml = project.get_services_xml()
    qcaps = rdfxml.xml_find_elements(
        services_xml,
        ".//{http://open-services.net/ns/core#}QueryCapability",
    )
    for qc in qcaps:
        qb = rdfxml.xmlrdf_get_resource_uri(qc, "oslc:queryBase")
        if qb:
            return qb
    return None


@mcp.tool()
def list_projects(domain: str = "ccm") -> str:
    """List accessible projects in ELM.

    Args:
        domain: 'ccm' (EWM/work items), 'rm' (DOORS Next/requirements), 'qm' (ETM/tests)
    """
    app = _get_app(domain)
    app._load_projects()
    projects = []
    for uri, info in app._projects.items():
        if isinstance(info, dict):
            projects.append({"name": info.get("name", "?"), "uri": uri})
    return json.dumps(projects, ensure_ascii=False, indent=2)


@mcp.tool()
def list_workitems(
    project_name: str,
    pagesize: int = 30,
    query: str = "",
) -> str:
    """List work items from an EWM project.

    Args:
        project_name: Name of the EWM project
        pagesize: Number of results (default 30)
        query: Optional OSLC query filter
    """
    app = _get_app("ccm")
    project = app.find_project(project_name)
    if not project:
        return json.dumps({"error": f"Project '{project_name}' not found"})

    query_base = _find_query_base(project)
    if not query_base:
        return json.dumps({"error": "Query capability not found"})

    kwargs = dict(
        select=["dcterms:identifier", "dcterms:title"],
        orderbys=["-dcterms:modified"],
        prefixes=OSLC_PREFIXES,
        pagesize=pagesize,
    )
    if query:
        kwargs["whereterms"] = query

    results = project.execute_oslc_query(query_base, **kwargs)

    items = []
    for uri, attrs in results.items():
        items.append({
            "id": attrs.get("dcterms:identifier", "?"),
            "title": attrs.get("dcterms:title", "?"),
            "uri": uri,
        })
    return json.dumps(items, ensure_ascii=False, indent=2)


@mcp.tool()
def get_workitem(
    project_name: str,
    workitem_id: str,
) -> str:
    """Get details of a specific work item by ID.

    Args:
        project_name: Name of the EWM project
        workitem_id: Work item identifier (e.g. '12345')
    """
    app = _get_app("ccm")
    project = app.find_project(project_name)
    if not project:
        return json.dumps({"error": f"Project '{project_name}' not found"})

    query_base = _find_query_base(project)
    if not query_base:
        return json.dumps({"error": "Query capability not found"})

    results = project.execute_oslc_query(
        query_base,
        whereterms=[["dcterms:identifier", "=", f'"{workitem_id}"']],
        select=["*"],
        prefixes=OSLC_PREFIXES,
        pagesize=1,
    )

    if not results:
        return json.dumps({"error": f"Work item {workitem_id} not found"})

    uri, attrs = next(iter(results.items()))
    clean = {"uri": uri}
    for k, v in attrs.items():
        clean[k] = str(v) if not isinstance(v, (str, int, float, bool)) else v
    return json.dumps(clean, ensure_ascii=False, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
