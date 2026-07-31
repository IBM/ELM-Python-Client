from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict, Tuple
import lxml.etree as ET


# ---------------------------------------------------------------------------
# Shared namespace map — identical to TestCase / TestPlan
# ---------------------------------------------------------------------------

_NAMESPACES: Dict[str, str] = {
    'rdf':          'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'dcterms':      'http://purl.org/dc/terms/',
    'oslc_qm':      'http://open-services.net/ns/qm#',
    'rqm_auto':     'http://jazz.net/ns/auto/rqm#',
    'acp':          'http://jazz.net/ns/acp#',
    'calm':         'http://jazz.net/xmlns/prod/jazz/calm/1.0/',
    'acc':          'http://open-services.net/ns/core/acc#',
    'process':      'http://jazz.net/ns/process#',
    'skos':         'http://www.w3.org/2004/02/skos/core#',
    'jrs':          'http://jazz.net/ns/jrs#',
    'oslc_auto':    'http://open-services.net/ns/auto#',
    'xsd':          'http://www.w3.org/2001/XMLSchema#',
    'bp':           'http://open-services.net/ns/basicProfile#',
    'cmx':          'http://open-services.net/ns/cm-x#',
    'rdfs':         'http://www.w3.org/2000/01/rdf-schema#',
    'rqm_lm':       'http://jazz.net/ns/qm/rqm/labmanagement#',
    'oslc':         'http://open-services.net/ns/core#',
    'owl':          'http://www.w3.org/2002/07/owl#',
    'rqm_process':  'http://jazz.net/xmlns/prod/jazz/rqm/process/1.0/',
    'jazz':         'http://jazz.net/ns/jazz#',
    'oslc_config':  'http://open-services.net/ns/config#',
    'oslc_cm':      'http://open-services.net/ns/cm#',
    'rqm_qm':       'http://jazz.net/ns/qm/rqm#',
    'oslc_rm':      'http://open-services.net/ns/rm#',
    'foaf':         'http://xmlns.com/foaf/0.1/',
}


# ---------------------------------------------------------------------------
# TestScriptStepLink  — reified rdf:Statement for a step-level link
# ---------------------------------------------------------------------------

@dataclass
class TestScriptStepLink:
    """Reified rdf:Statement for a validatesRequirement link on a step."""
    node_id:   Optional[str] = None   # rdf:nodeID (present on GET, omitted for new links)
    subject:   Optional[str] = None   # step URL (filled by TestScriptStep.uri)
    predicate: str = ""
    target:    str = ""
    title:     Optional[str] = None


# ---------------------------------------------------------------------------
# TestScriptStep  — a single script step (separate ETM resource)
# ---------------------------------------------------------------------------

@dataclass
class TestScriptStep:
    """
    Represents one ETM Test Script Step (ExecutionElement2).

    Lifecycle — new step
    --------------------
    ETM's services.xml has no ``oslc:creationFactory`` for steps.  However the
    query base URL (``...resources/com.ibm.rqm.planning.ExecutionElement2``) also
    acts as the POST endpoint — this is standard OSLC practice.

    Use ``c.get_query_capability_uri("oslc_qm:TestScriptStepQuery")`` to obtain
    the step endpoint URL, then POST ``TestScriptStep.create_minimal(...).to_etree()``
    to it.  The ``Location`` header of the 201 response gives the real step URL.
    Then call ``script.add_step_url(step_url)`` and PUT the script to register it.

    To add links after creation: GET step → ``add_validatesRequirementLink(...)``
    → PUT step.

    Lifecycle — existing step
    -------------------------
    ``TestScriptStep.from_etree(xml)`` after a GET on the step URL.
    Modify fields / links, then PUT back.

    The ``description`` and ``expected_result`` fields are stored as XHTML
    strings (e.g. ``"<div xmlns=...><p>text</p></div>"``).  Helper
    ``wrap_xhtml()`` converts plain text to that format.
    """

    uri:             str = ""
    title:           Optional[str] = None
    description:     Optional[str] = None   # XHTML string
    expected_result: Optional[str] = None   # XHTML string
    index:           Optional[int] = None   # rqm_qm:index (1-based)
    identifier:      Optional[str] = None
    modified:        Optional[str] = None
    # URL of the parent TestScript
    included_in_test_script: Optional[str] = None
    links:       List[TestScriptStepLink] = field(default_factory=list)
    namespaces:  Dict[str, str]           = field(default_factory=dict)
    elements:    List[Tuple[str, Dict[str, str], Optional[str]]] = field(default_factory=list)
    extra_descriptions: Dict[str, List[Tuple[str, Dict[str, str], Optional[str]]]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create_minimal(
        cls,
        title: str,
        description: str = "",
        expected_result: str = "",
        index: int = 1,
        parent_script_url: Optional[str] = None,
    ) -> 'TestScriptStep':
        """
        Build the minimal RDF/XML payload required to POST a new step.

        Parameters
        ----------
        title            : Step title (``dcterms:title``).
        description      : Step description text.  Plain text is automatically
                           wrapped in an XHTML ``<div><p>…</p></div>`` block.
        expected_result  : Expected result text.  Same XHTML wrapping.
        index            : Step sequence number (1-based, ``rqm_qm:index``).
        parent_script_url: URL of the parent ``VersionedExecutionScript`` resource.
                           Becomes ``rqm_qm:includedInTestScript``.
        """
        step = cls(
            uri="",
            title=title,
            description=wrap_xhtml(description) if description else None,
            expected_result=wrap_xhtml(expected_result) if expected_result else None,
            index=index,
            included_in_test_script=parent_script_url,
            namespaces=dict(_NAMESPACES),
        )
        # Seed the elements list for known scalar tags
        step.elements.append((
            '{http://purl.org/dc/terms/}title',
            {'{http://www.w3.org/2001/XMLSchema#}datatype': 'http://www.w3.org/2001/XMLSchema#string'},
            title
        ))
        step.elements.append((
            '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}type',
            {'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource': 'http://jazz.net/ns/qm/rqm#TestScriptStep'},
            None
        ))
        return step

    # ------------------------------------------------------------------
    # validatesRequirement helpers
    # ------------------------------------------------------------------

    def add_validatesRequirementLink(self, target: str, title: Optional[str] = None) -> None:
        """Add a ``oslc_qm:validatesRequirement`` link to a requirement."""
        self.links.append(TestScriptStepLink(
            subject=self.uri,
            predicate="http://open-services.net/ns/qm#validatesRequirement",
            target=target,
            title=title,
        ))
        rdf_ns    = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm   = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        tag       = '{' + oslc_qm + '}validatesRequirement'
        attrib    = {'{' + rdf_ns + '}resource': target}
        self.elements.append((tag, attrib, None))

    def delete_validatesRequirementLink(self, target: str) -> bool:
        """Remove a ``validatesRequirement`` link by target URI.  Returns True if removed."""
        initial = len(self.links)
        self.links = [
            lnk for lnk in self.links
            if not (lnk.predicate == "http://open-services.net/ns/qm#validatesRequirement"
                    and lnk.target == target)
        ]
        rdf_ns  = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        tag     = '{' + oslc_qm + '}validatesRequirement'
        self.elements = [
            e for e in self.elements
            if not (e[0] == tag and e[1].get('{' + rdf_ns + '}resource') == target)
        ]
        return len(self.links) < initial

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def from_etree(etree: ET._ElementTree) -> 'TestScriptStep':
        """Parse a GET response for a single ExecutionElement2 resource."""
        root       = etree.getroot()
        namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        ns         = namespaces.copy()
        rdf_about  = f'{{{ns["rdf"]}}}about'
        rdf_res    = f'{{{ns["rdf"]}}}resource'

        # The main element is the one whose rdf:about contains 'ExecutionElement2'
        main_elem = None
        for elem in root.findall(".//rdf:Description[@rdf:about]", ns):
            uri = elem.attrib.get(rdf_about, "")
            if 'ExecutionElement2' in uri:
                main_elem = elem
                break

        if main_elem is None:
            raise ValueError("No rdf:Description for a TestScriptStep (ExecutionElement2) found")

        uri  = main_elem.attrib[rdf_about]
        step = TestScriptStep(uri=uri, namespaces=namespaces)

        for elem in main_elem:
            tag       = elem.tag
            text      = elem.text.strip() if elem.text else ""
            attrib    = dict(elem.attrib)
            short_tag = ET.QName(tag).localname
            step.elements.append((tag, attrib, elem.text or ""))

            if short_tag == 'title' and tag.startswith('{http://purl.org/dc/terms/}'):
                step.title = text
            elif short_tag == 'description':
                step.description = elem.text or ""   # keep raw XHTML
            elif short_tag == 'expectedResult':
                step.expected_result = elem.text or ""
            elif short_tag == 'index':
                try:
                    step.index = int(text)
                except (ValueError, TypeError):
                    pass
            elif short_tag == 'identifier':
                step.identifier = text
            elif short_tag == 'modified':
                step.modified = text
            elif short_tag == 'includedInTestScript':
                step.included_in_test_script = attrib.get(rdf_res)

        # Reified rdf:Statement blocks (validatesRequirement links)
        for stmt in root.findall('.//rdf:Description[@rdf:nodeID]', ns):
            node_id       = stmt.attrib.get(f'{{{ns["rdf"]}}}nodeID')
            subject_elem  = stmt.find('rdf:subject',   ns)
            pred_elem     = stmt.find('rdf:predicate', ns)
            object_elem   = stmt.find('rdf:object',    ns)
            title_elem    = stmt.find('dcterms:title', ns)

            if subject_elem is not None and pred_elem is not None and object_elem is not None:
                step.links.append(TestScriptStepLink(
                    node_id   = node_id,
                    subject   = subject_elem.attrib.get(rdf_res),
                    predicate = pred_elem.attrib.get(rdf_res, ""),
                    target    = object_elem.attrib.get(rdf_res, ""),
                    title     = title_elem.text if title_elem is not None else None,
                ))

        # Extra rdf:Description blocks with rdf:about (not the main step)
        for desc in root.findall(".//rdf:Description[@rdf:about]", ns):
            about = desc.attrib.get(rdf_about)
            if about == step.uri:
                continue
            elems = []
            for elem in desc:
                elems.append((elem.tag, dict(elem.attrib), elem.text or ""))
            step.extra_descriptions[about] = elems

        return step

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_etree(self) -> ET._ElementTree:
        NSMAP  = self.namespaces or {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'}
        rdf_ns = NSMAP['rdf']
        rdf    = ET.Element(ET.QName(rdf_ns, 'RDF'), nsmap=NSMAP)

        if self.uri:
            desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                 {ET.QName(rdf_ns, 'about'): self.uri})
        else:
            desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'))

        def add(ns_key: str, local: str, text=None, attrib=None):
            el = ET.SubElement(desc, ET.QName(NSMAP[ns_key], local), attrib or {})
            if text is not None:
                el.text = text

        if self.title is not None:
            add('dcterms', 'title', self.title,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.description is not None:
            add('dcterms', 'description', self.description,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.expected_result is not None:
            add('rqm_qm', 'expectedResult', self.expected_result,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.index is not None:
            add('rqm_qm', 'index', str(self.index),
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.identifier is not None:
            add('dcterms', 'identifier', self.identifier,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.modified is not None:
            add('dcterms', 'modified', self.modified,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.included_in_test_script is not None:
            add('rqm_qm', 'includedInTestScript', None,
                {f'{{{rdf_ns}}}resource': self.included_in_test_script})

        # rdf:type
        add('rdf', 'type', None,
            {f'{{{rdf_ns}}}resource': 'http://jazz.net/ns/qm/rqm#TestScriptStep'})

        # Pass-through elements (scriptStepType, serviceProvider, instanceShape, etc.)
        known_tags = {
            'title', 'description', 'expectedResult', 'index', 'identifier',
            'modified', 'includedInTestScript', 'type',
            'validatesRequirement',   # emitted below via links
        }
        for tag, attrib, text in self.elements:
            short_tag = ET.QName(tag).localname
            if short_tag in known_tags:
                continue
            el = ET.SubElement(desc, ET.QName(tag), {
                ET.QName(k) if isinstance(k, str) and ':' in k else k: v
                for k, v in attrib.items()
            })
            if text:
                el.text = text

        # Direct oslc_qm:validatesRequirement properties
        oslc_qm_ns = NSMAP.get('oslc_qm', 'http://open-services.net/ns/qm#')
        for lnk in self.links:
            if lnk.predicate == "http://open-services.net/ns/qm#validatesRequirement":
                ET.SubElement(desc, ET.QName(oslc_qm_ns, 'validatesRequirement'),
                              {ET.QName(rdf_ns, 'resource'): lnk.target})

        # Reified rdf:Statement blocks
        for lnk in self.links:
            attribs = {}
            if lnk.node_id:
                attribs[ET.QName(rdf_ns, 'nodeID')] = lnk.node_id
            stmt = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'), attribs)
            ET.SubElement(stmt, ET.QName(rdf_ns, 'subject'),
                          {ET.QName(rdf_ns, 'resource'): lnk.subject or self.uri})
            ET.SubElement(stmt, ET.QName(rdf_ns, 'predicate'),
                          {ET.QName(rdf_ns, 'resource'): lnk.predicate})
            ET.SubElement(stmt, ET.QName(rdf_ns, 'object'),
                          {ET.QName(rdf_ns, 'resource'): lnk.target})
            ET.SubElement(stmt, ET.QName(rdf_ns, 'type'),
                          {ET.QName(rdf_ns, 'resource'): rdf_ns + 'Statement'})
            if lnk.title:
                ET.SubElement(stmt, ET.QName(NSMAP['dcterms'], 'title')).text = lnk.title

        # Extra rdf:Description blocks
        for about, elems in self.extra_descriptions.items():
            xdesc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                  {ET.QName(rdf_ns, 'about'): about})
            for tag, attrib, text in elems:
                el = ET.SubElement(xdesc, ET.QName(tag), attrib)
                if text:
                    el.text = text

        return ET.ElementTree(rdf)


# ---------------------------------------------------------------------------
# TestScript  — the parent resource (VersionedExecutionScript)
# ---------------------------------------------------------------------------

@dataclass
class TestScript:
    """
    Represents an ETM Test Script (VersionedExecutionScript).

    ETM has no OSLC creation factory for steps and the query base URL does not
    accept POST.  New steps are created by embedding them as ``rdf:Description``
    blocks with placeholder ``rdf:about`` URLs inside the script's RDF/XML PUT.
    ETM detects URLs containing ``ExecutionElement2/new`` and creates real step
    resources, replacing the placeholders with permanent URIs.

    Typical create workflow
    -----------------------
    1. ``TestScript.create_minimal(title)`` → POST to TestScript factory
       → ``Location`` gives ``script_url``.
    2. GET ``script_url`` → ``TestScript.from_etree(xml)`` → live object + ETag.
    3. For each step: ``TestScriptStep.create_minimal(...)``
       → ``script.add_pending_step(step)``.
    4. PUT ``script.to_etree()`` — steps are embedded with placeholder
       ``rdf:about`` URLs; ETM creates the real ``ExecutionElement2`` resources.
    5. GET ``script_url`` again — ``step_urls`` now contains the real step URLs.
    6. To add links to a step: GET step → ``add_validatesRequirementLink(...)``
       → PUT the step.
    """

    uri:                        str = ""
    title:                      Optional[str] = None
    description:                Optional[str] = None
    identifier:                 Optional[str] = None
    created:                    Optional[str] = None
    modified:                   Optional[str] = None
    creator:                    Optional[str] = None
    contributor:                Optional[str] = None
    type:                       Optional[str] = None
    short_id:                   Optional[str] = None
    short_identifier:           Optional[str] = None
    script_step_count:          Optional[str] = None
    is_locked:                  Optional[str] = None
    # oslc_qm:executionInstructions — IIntegrationService URL for step management
    # This is the URL of the RQM native XML representation of the script,
    # which is the only supported way to create/manage steps in config-managed projects.
    execution_instructions_url: Optional[str] = None
    # rqm_qm:containsTestScriptStep — real step URLs (populated after GET)
    step_urls:                  List[str]           = field(default_factory=list)
    # Steps to be created on the next PUT (cleared once PUT succeeds)
    pending_steps:      List['TestScriptStep'] = field(default_factory=list)
    namespaces:         Dict[str, str] = field(default_factory=dict)
    elements:           List[Tuple[str, Dict[str, str], Optional[str]]] = field(default_factory=list)
    extra_descriptions: Dict[str, List[Tuple[str, Dict[str, str], Optional[str]]]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create_minimal(cls, title: str, description: str = "") -> 'TestScript':
        """Build the minimal RDF/XML payload required to POST a new Test Script."""
        ts = cls(
            uri="",
            title=title,
            description=description if description else None,
            type="http://open-services.net/ns/qm#TestScript",
            namespaces=dict(_NAMESPACES),
        )
        # rqm_qm:scriptType is required by ETM to identify this as a manual script
        ts.elements.append((
            '{http://jazz.net/ns/qm/rqm#}scriptType',
            {'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource':
                 'http://jazz.net/ns/qm/rqm#com.ibm.rqm.planning.common.scripttype.manual'},
            None,
        ))
        return ts

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def add_pending_step(self, step: 'TestScriptStep') -> None:
        """Queue *step* to be embedded inline on the next ``to_etree()`` / PUT.

        Build the step with ``TestScriptStep.create_minimal()``.
        After the PUT, GET the script again — ``step_urls`` will contain the
        real ``ExecutionElement2`` URLs assigned by ETM.
        """
        self.pending_steps.append(step)

    def add_step_url(self, step_url: str) -> None:
        """Append a ``rqm_qm:containsTestScriptStep`` reference (existing step)."""
        if step_url not in self.step_urls:
            self.step_urls.append(step_url)

    def remove_step_url(self, step_url: str) -> bool:
        """Remove a step reference.  Returns True if found and removed."""
        initial = len(self.step_urls)
        self.step_urls = [u for u in self.step_urls if u != step_url]
        return len(self.step_urls) < initial

    @staticmethod
    def sort_steps(steps: List['TestScriptStep']) -> List['TestScriptStep']:
        """Return *steps* sorted by their ``rqm_qm:index`` value (ascending).

        Steps whose index is ``None`` are placed at the end.
        The original list is not modified.
        """
        return sorted(steps, key=lambda s: s.index if s.index is not None else float('inf'))

    def fetch_and_sort_steps(
        self,
        get_rdf_xml: Callable[[str], ET._ElementTree],
    ) -> List['TestScriptStep']:
        """Fetch every step in ``step_urls``, parse it, and return the list
        sorted by ``rqm_qm:index``.

        Parameters
        ----------
        get_rdf_xml:
            A callable that accepts a URL string and returns a parsed
            ``ET._ElementTree``.  Pass ``c.execute_get_rdf_xml`` directly::

                steps = tsObject.fetch_and_sort_steps(
                    lambda url: c.execute_get_rdf_xml(url, cacheable=False)
                )
        """
        steps = [
            TestScriptStep.from_etree(get_rdf_xml(url))
            for url in self.step_urls
        ]
        return self.sort_steps(steps)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def from_etree(etree: ET._ElementTree) -> 'TestScript':
        """Parse a GET response for a VersionedExecutionScript resource."""
        root       = etree.getroot()
        namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        ns         = namespaces.copy()
        rdf_about  = f'{{{ns["rdf"]}}}about'
        rdf_res    = f'{{{ns["rdf"]}}}resource'

        # Main element: 'VersionedExecutionScript' in URI, no '#', no sub-path
        main_elem = None
        for elem in root.findall(".//rdf:Description[@rdf:about]", ns):
            uri = elem.attrib.get(rdf_about, "")
            if 'VersionedExecutionScript' in uri and '#' not in uri:
                after = uri.split('VersionedExecutionScript/')[1]
                if '/' not in after:
                    main_elem = elem
                    break

        if main_elem is None:
            raise ValueError(
                "No main rdf:Description for a TestScript (VersionedExecutionScript) found"
            )

        uri    = main_elem.attrib[rdf_about]
        script = TestScript(uri=uri, namespaces=namespaces)

        for elem in main_elem:
            tag       = elem.tag
            text      = elem.text.strip() if elem.text else ""
            attrib    = dict(elem.attrib)
            short_tag = ET.QName(tag).localname
            script.elements.append((tag, attrib, text))

            if short_tag == 'title' and tag.startswith('{http://purl.org/dc/terms/}'):
                script.title = text
            elif short_tag == 'description':
                script.description = text
            elif short_tag == 'identifier':
                script.identifier = text
            elif short_tag == 'created':
                script.created = text
            elif short_tag == 'modified':
                script.modified = text
            elif short_tag == 'creator':
                script.creator = attrib.get(rdf_res)
            elif short_tag == 'contributor':
                script.contributor = attrib.get(rdf_res)
            elif short_tag == 'type' and rdf_res in attrib:
                script.type = attrib[rdf_res]
            elif short_tag == 'shortId':
                script.short_id = text
            elif short_tag == 'shortIdentifier':
                script.short_identifier = text
            elif short_tag == 'scriptStepCount':
                script.script_step_count = text
            elif short_tag == 'isLocked':
                script.is_locked = text
            elif short_tag == 'executionInstructions':
                script.execution_instructions_url = attrib.get(rdf_res)
            elif short_tag == 'containsTestScriptStep':
                step_url = attrib.get(rdf_res)
                if step_url and step_url not in script.step_urls:
                    script.step_urls.append(step_url)

        # Extra rdf:Description blocks (version resource, etc.)
        for desc in root.findall(".//rdf:Description[@rdf:about]", ns):
            about = desc.attrib.get(rdf_about)
            if about == script.uri:
                continue
            elems = []
            for elem in desc:
                elems.append((elem.tag, dict(elem.attrib), elem.text or ""))
            script.extra_descriptions[about] = elems

        return script

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_etree(self) -> ET._ElementTree:
        NSMAP  = self.namespaces or {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'}
        rdf_ns = NSMAP['rdf']
        rdf    = ET.Element(ET.QName(rdf_ns, 'RDF'), nsmap=NSMAP)

        if self.uri:
            desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                 {ET.QName(rdf_ns, 'about'): self.uri})
        else:
            desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'))

        def add(ns_key: str, local: str, text=None, attrib=None):
            el = ET.SubElement(desc, ET.QName(NSMAP[ns_key], local), attrib or {})
            if text is not None:
                el.text = text

        if self.title is not None:
            add('dcterms', 'title', self.title,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.description is not None:
            add('dcterms', 'description', self.description,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.identifier is not None:
            add('dcterms', 'identifier', self.identifier,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.created is not None:
            add('dcterms', 'created', self.created,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.modified is not None:
            add('dcterms', 'modified', self.modified,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.creator is not None:
            add('dcterms', 'creator', None, {f'{{{rdf_ns}}}resource': self.creator})
        if self.contributor is not None:
            add('dcterms', 'contributor', None, {f'{{{rdf_ns}}}resource': self.contributor})
        if self.short_id is not None:
            add('oslc', 'shortId', self.short_id,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.short_identifier is not None:
            add('rqm_qm', 'shortIdentifier', self.short_identifier,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.script_step_count is not None:
            add('rqm_qm', 'scriptStepCount', self.script_step_count,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#long'})
        if self.is_locked is not None:
            add('rqm_qm', 'isLocked', self.is_locked,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#boolean'})
        if self.type is not None:
            add('rdf', 'type', None, {f'{{{rdf_ns}}}resource': self.type})

        # Pass-through elements (scriptType, template, executionInstructions, etc.)
        known_tags = {
            'title', 'description', 'identifier', 'created', 'modified',
            'creator', 'contributor', 'shortId', 'shortIdentifier',
            'scriptStepCount', 'isLocked',
            'containsTestScriptStep',  # emitted below
            'type',
        }
        for tag, attrib, text in self.elements:
            short_tag = ET.QName(tag).localname
            if short_tag in known_tags:
                continue
            el = ET.SubElement(desc, ET.QName(tag), {
                ET.QName(k) if isinstance(k, str) and ':' in k else k: v
                for k, v in attrib.items()
            })
            if text:
                el.text = text

        rqm_qm_ns = NSMAP.get('rqm_qm', 'http://jazz.net/ns/qm/rqm#')
        oslc_qm_ns = NSMAP.get('oslc_qm', 'http://open-services.net/ns/qm#')
        dcterms_ns = NSMAP.get('dcterms', 'http://purl.org/dc/terms/')

        # rqm_qm:containsTestScriptStep — references to already-existing step URLs
        for step_url in self.step_urls:
            ET.SubElement(desc, ET.QName(rqm_qm_ns, 'containsTestScriptStep'),
                          {ET.QName(rdf_ns, 'resource'): step_url})

        # Pending (new) steps — embedded as rdf:Description blocks with a
        # placeholder rdf:about derived from the script URI context.
        # The placeholder follows the pattern:
        #   <context_base>/resources/com.ibm.rqm.planning.ExecutionElement2/new<i>
        # where <context_base> is extracted from the script URI by stripping
        # everything from 'resources/' onwards.
        # ETM recognises these as new steps to create and assigns permanent URIs.
        if self.pending_steps:
            # Derive the context base from the script URI
            # e.g. https://.../qm/oslc_qm/contexts/<id>/resources/VersionedExecutionScript/<id>
            #   -> https://.../qm/oslc_qm/contexts/<id>/
            if 'resources/' in self.uri:
                context_base = self.uri[:self.uri.index('resources/')]
            else:
                context_base = self.uri.rstrip('/') + '/'

            for i, step in enumerate(self.pending_steps):
                placeholder = f"{context_base}resources/com.ibm.rqm.planning.ExecutionElement2/new{i}"
                # Reference from the script description block
                ET.SubElement(desc, ET.QName(rqm_qm_ns, 'containsTestScriptStep'),
                              {ET.QName(rdf_ns, 'resource'): placeholder})
                # Inline step description block
                step_desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                          {ET.QName(rdf_ns, 'about'): placeholder})
                ET.SubElement(step_desc, ET.QName(rdf_ns, 'type'),
                              {ET.QName(rdf_ns, 'resource'): 'http://jazz.net/ns/qm/rqm#TestScriptStep'})
                if step.title is not None:
                    el = ET.SubElement(step_desc, ET.QName(dcterms_ns, 'title'),
                                       {ET.QName(rdf_ns, 'datatype'): 'http://www.w3.org/2001/XMLSchema#string'})
                    el.text = step.title
                if step.description is not None:
                    el = ET.SubElement(step_desc, ET.QName(dcterms_ns, 'description'),
                                       {ET.QName(rdf_ns, 'datatype'): 'http://www.w3.org/2001/XMLSchema#string'})
                    el.text = step.description
                if step.expected_result is not None:
                    el = ET.SubElement(step_desc, ET.QName(rqm_qm_ns, 'expectedResult'),
                                       {ET.QName(rdf_ns, 'datatype'): 'http://www.w3.org/2001/XMLSchema#string'})
                    el.text = step.expected_result
                if step.index is not None:
                    el = ET.SubElement(step_desc, ET.QName(rqm_qm_ns, 'index'),
                                       {ET.QName(rdf_ns, 'datatype'): 'http://www.w3.org/2001/XMLSchema#int'})
                    el.text = str(step.index)
                # Direct oslc_qm:validatesRequirement properties (no reified statement yet —
                # the step has no real URI until after the PUT)
                for lnk in step.links:
                    if lnk.predicate == "http://open-services.net/ns/qm#validatesRequirement":
                        ET.SubElement(step_desc, ET.QName(oslc_qm_ns, 'validatesRequirement'),
                                      {ET.QName(rdf_ns, 'resource'): lnk.target})

        # Extra rdf:Description blocks (version resource, etc.)
        for about, elems in self.extra_descriptions.items():
            xdesc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                  {ET.QName(rdf_ns, 'about'): about})
            for tag, attrib, text in elems:
                el = ET.SubElement(xdesc, ET.QName(tag), attrib)
                if text:
                    el.text = text

        return ET.ElementTree(rdf)

    def is_xml_equal(self, other: 'TestScript') -> bool:
        def clean(xml: ET._ElementTree) -> bytes:
            return ET.tostring(xml.getroot(), encoding='utf-8', method='c14n')
        return clean(self.to_etree()) == clean(other.to_etree())


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def wrap_xhtml(text: str) -> str:
    """Wrap plain text in the XHTML ``<div><p>…</p></div>`` envelope that
    ETM stores for step descriptions and expected results.

    If the string already starts with ``<``, it is returned unchanged
    (assumed to already be HTML/XHTML).
    """
    if text.lstrip().startswith('<'):
        return text
    return f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{text}</p></div>'
