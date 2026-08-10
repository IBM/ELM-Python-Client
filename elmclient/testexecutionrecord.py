from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple, Union
import lxml.etree as ET

if TYPE_CHECKING:
    from elmclient.testcase import TestCase
    from elmclient.testscript import TestScript


# ---------------------------------------------------------------------------
# Shared namespace map — identical to TestCase / TestPlan / TestScript
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


@dataclass
class TestExecutionRecord:
    """
    Represents an ETM Test Execution Record (``oslc_qm:TestExecutionRecord``).

    The ETM URL path segment is ``com.ibm.rqm.execution.TestcaseExecutionRecord``
    (no "Versioned" prefix — same flat URI scheme as ``TestCase``).

    Typical create workflow
    -----------------------
    1. ``TestExecutionRecord.create_minimal(title, runs_test_case_uri)``
       → POST to ``c.get_factory_uri(resource_type='TestExecutionRecord', ...)``.
       The ``Location`` header of the 201 response gives the real TER URL.
    2. GET TER URL → ``TestExecutionRecord.from_etree(xml)`` → live object + ETag.
    3. Modify fields (``runs_test_script``, ``runs_on_test_environment``, etc.).
    4. PUT ``ter.to_etree()`` with ``If-Match: <etag>``.

    Typical read workflow
    --------------------
    ``c.execute_get_rdf_xml(ter_url)`` → ``TestExecutionRecord.from_etree(xml)``.

    Properties decoded from a real ETM GET response
    ------------------------------------------------
    * ``runs_test_case``            – ``oslc_qm:runsTestCase``
    * ``executes_test_script``      – ``oslc_qm:executesTestScript``
    * ``runs_on_test_environment``  – ``oslc_qm:runsOnTestEnvironment``
    * ``reports_on_test_plan``      – ``oslc_qm:reportsOnTestPlan``
    * ``produces_test_results``     – ``rqm_qm:producesTestResult`` (multi-valued
                                       list — one TCER produces many Test Results)
    * ``current_test_result``       – ``rqm_qm:currentTestResult``
    * ``last_passed_test_result``   – ``rqm_qm:lastPassedTestResult``
    * ``is_suspect_result``         – ``rqm_qm:isSuspectResult``
    * ``estimate``                  – ``rqm_qm:estimate``  (ms, xsd:integer)
    * ``time_spent``                – ``rqm_qm:timeSpent`` (ms, xsd:integer)
    * ``weight``                    – ``rqm_qm:weight``    (xsd:int)
    * ``test_schedule``             – ``rqm_qm:testSchedule``
    * ``short_id``                  – ``oslc:shortId``
    * ``short_identifier``          – ``rqm_qm:shortIdentifier``
    * Standard Dublin Core: ``title``, ``description``, ``identifier``,
      ``created``, ``modified``, ``creator``, ``contributor``
    """

    # -------------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------------

    @classmethod
    def create_minimal(
        cls,
        title: str,
        runs_test_case: Union[str, 'TestCase'],
        executes_test_script: Optional[Union[str, 'TestScript']] = None,
        reports_on_test_plan: Optional[Union[str, 'TestPlan']] = None,
    ) -> 'TestExecutionRecord':
        """Build the minimal RDF/XML payload required to POST a new TER.

        Parameters
        ----------
        title                : Human-readable title (``dcterms:title``).
        runs_test_case       : URI string *or* ``TestCase`` object — the test
                               case this TER will execute
                               (``oslc_qm:runsTestCase``).
        executes_test_script : Optional URI string *or* ``TestScript`` object.
                               When supplied, sets ``oslc_qm:executesTestScript``
                               on the new TCER so ETM assigns the default test
                               script immediately on creation.
        reports_on_test_plan : Optional URI string *or* ``TestPlan`` object.
                               When supplied, sets ``oslc_qm:reportsOnTestPlan``
                               on the new TCER so ETM links it to the correct
                               test plan on creation.
        """
        if not isinstance(runs_test_case, str):
            runs_test_case = runs_test_case.uri

        if executes_test_script is not None and not isinstance(executes_test_script, str):
            executes_test_script = executes_test_script.uri

        if reports_on_test_plan is not None and not isinstance(reports_on_test_plan, str):
            reports_on_test_plan = reports_on_test_plan.uri

        rdf_ns = _NAMESPACES['rdf']
        qm_ns  = _NAMESPACES['oslc_qm']

        ter = cls(
            uri="",
            title=title,
            type="http://open-services.net/ns/qm#TestExecutionRecord",
            runs_test_case=runs_test_case,
            executes_test_script=executes_test_script,
            reports_on_test_plan=reports_on_test_plan,
            namespaces=dict(_NAMESPACES),
        )

        ter.elements.append((
            '{http://purl.org/dc/terms/}title',
            {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'},
            title,
        ))
        ter.elements.append((
            f'{{{rdf_ns}}}type',
            {f'{{{rdf_ns}}}resource': 'http://open-services.net/ns/qm#TestExecutionRecord'},
            None,
        ))
        ter.elements.append((
            f'{{{qm_ns}}}runsTestCase',
            {f'{{{rdf_ns}}}resource': runs_test_case},
            None,
        ))
        if executes_test_script is not None:
            ter.elements.append((
                f'{{{qm_ns}}}executesTestScript',
                {f'{{{rdf_ns}}}resource': executes_test_script},
                None,
            ))
        if reports_on_test_plan is not None:
            ter.elements.append((
                f'{{{qm_ns}}}reportsOnTestPlan',
                {f'{{{rdf_ns}}}resource': reports_on_test_plan},
                None,
            ))

        return ter

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    uri:                      str = ""
    title:                    Optional[str] = None
    description:              Optional[str] = None
    identifier:               Optional[str] = None
    created:                  Optional[str] = None
    modified:                 Optional[str] = None
    creator:                  Optional[str] = None
    contributor:              Optional[str] = None
    type:                     Optional[str] = None
    relation:                 Optional[str] = None
    short_id:                 Optional[str] = None
    short_identifier:         Optional[str] = None
    weight:                   Optional[str] = None
    estimate:                 Optional[str] = None   # milliseconds, xsd:integer
    time_spent:               Optional[str] = None   # milliseconds, xsd:integer
    is_suspect_result:        Optional[str] = None   # xsd:boolean string

    # Resource-reference properties
    runs_test_case:           Optional[str] = None   # oslc_qm:runsTestCase
    executes_test_script:     Optional[str] = None   # oslc_qm:executesTestScript
    runs_on_test_environment: Optional[str] = None   # oslc_qm:runsOnTestEnvironment
    reports_on_test_plan:     Optional[str] = None   # oslc_qm:reportsOnTestPlan
    # rqm_qm:producesTestResult — multi-valued: one TCER produces many Test Results
    produces_test_results:    List[str]     = field(default_factory=list)
    current_test_result:      Optional[str] = None   # rqm_qm:currentTestResult
    last_passed_test_result:  Optional[str] = None   # rqm_qm:lastPassedTestResult
    test_schedule:            Optional[str] = None   # rqm_qm:testSchedule

    namespaces:         Dict[str, str] = field(default_factory=dict)
    elements:           List[Tuple[str, Dict[str, str], Optional[str]]] = field(default_factory=list)
    extra_descriptions: Dict[str, List[Tuple[str, Dict[str, str], Optional[str]]]] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # Convenience setters for mutable reference properties
    # -------------------------------------------------------------------------

    def set_runs_test_case(self, target: Union[str, 'TestCase']) -> None:
        """Set ``oslc_qm:runsTestCase``, replacing any previously stored value."""
        if not isinstance(target, str):
            target = target.uri
        self.runs_test_case = target
        rdf_ns    = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm   = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        tag       = '{' + oslc_qm + '}runsTestCase'
        self.elements = [e for e in self.elements if ET.QName(e[0]).localname != 'runsTestCase']
        self.elements.append((tag, {'{' + rdf_ns + '}resource': target}, None))

    def set_executes_test_script(self, target: Union[str, 'TestScript']) -> None:
        """Set ``oslc_qm:executesTestScript``, replacing any previously stored value."""
        if not isinstance(target, str):
            target = target.uri
        self.executes_test_script = target
        rdf_ns    = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm   = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        tag       = '{' + oslc_qm + '}executesTestScript'
        self.elements = [e for e in self.elements if ET.QName(e[0]).localname != 'executesTestScript']
        self.elements.append((tag, {'{' + rdf_ns + '}resource': target}, None))

    def set_runs_on_test_environment(self, target: str) -> None:
        """Set ``oslc_qm:runsOnTestEnvironment``, replacing any previously stored value."""
        self.runs_on_test_environment = target
        rdf_ns    = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm   = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        tag       = '{' + oslc_qm + '}runsOnTestEnvironment'
        self.elements = [e for e in self.elements if ET.QName(e[0]).localname != 'runsOnTestEnvironment']
        self.elements.append((tag, {'{' + rdf_ns + '}resource': target}, None))

    def set_reports_on_test_plan(self, target: str) -> None:
        """Set ``oslc_qm:reportsOnTestPlan``, replacing any previously stored value."""
        self.reports_on_test_plan = target
        rdf_ns    = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm   = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        tag       = '{' + oslc_qm + '}reportsOnTestPlan'
        self.elements = [e for e in self.elements if ET.QName(e[0]).localname != 'reportsOnTestPlan']
        self.elements.append((tag, {'{' + rdf_ns + '}resource': target}, None))

    # -------------------------------------------------------------------------
    # RDF/XML parsing
    # -------------------------------------------------------------------------

    @staticmethod
    def from_etree(etree: ET._ElementTree) -> 'TestExecutionRecord':
        """Parse a GET response for a ``TestcaseExecutionRecord`` resource.

        The main ``rdf:Description`` is identified by the substring
        ``'TestcaseExecutionRecord'`` in its ``rdf:about`` URI **without** a
        further sub-path (i.e. the part after ``TestcaseExecutionRecord/`` must
        contain exactly one segment with no trailing ``/``).
        """
        root       = etree.getroot()
        namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        ns         = namespaces.copy()

        rdf_about        = f'{{{ns["rdf"]}}}about'
        rdf_resource_attr = f'{{{ns["rdf"]}}}resource'

        # Main element: 'TestcaseExecutionRecord' in URI, no '#',
        # and the segment after 'TestcaseExecutionRecord/' has no further '/'.
        main_elem = None
        for elem in root.findall(".//rdf:Description[@rdf:about]", ns):
            uri = elem.attrib.get(rdf_about, "")
            if 'TestcaseExecutionRecord' in uri and '#' not in uri:
                after = uri.split('TestcaseExecutionRecord/')[1]
                if '/' not in after:
                    main_elem = elem
                    break

        if main_elem is None:
            raise ValueError(
                "No main rdf:Description for a TestExecutionRecord "
                "(TestcaseExecutionRecord without sub-path) found"
            )

        uri = main_elem.attrib[rdf_about]
        ter = TestExecutionRecord(uri=uri, namespaces=namespaces)

        for elem in main_elem:
            tag       = elem.tag
            text      = elem.text.strip() if elem.text else ""
            attrib    = dict(elem.attrib)
            short_tag = ET.QName(tag).localname
            ter.elements.append((tag, attrib, text))

            if short_tag == 'title' and tag.startswith('{http://purl.org/dc/terms/}'):
                ter.title = text
            elif short_tag == 'description':
                ter.description = text
            elif short_tag == 'identifier':
                ter.identifier = text
            elif short_tag == 'created':
                ter.created = text
            elif short_tag == 'modified':
                ter.modified = text
            elif short_tag == 'creator':
                ter.creator = attrib.get(rdf_resource_attr)
            elif short_tag == 'contributor':
                ter.contributor = attrib.get(rdf_resource_attr)
            elif short_tag == 'type' and rdf_resource_attr in attrib:
                ter.type = attrib[rdf_resource_attr]
            elif short_tag == 'relation':
                ter.relation = attrib.get(rdf_resource_attr)
            elif short_tag == 'shortId':
                ter.short_id = text
            elif short_tag == 'shortIdentifier':
                ter.short_identifier = text
            elif short_tag == 'weight':
                ter.weight = text
            elif short_tag == 'estimate':
                ter.estimate = text
            elif short_tag == 'timeSpent':
                ter.time_spent = text
            elif short_tag == 'isSuspectResult':
                ter.is_suspect_result = text
            elif short_tag == 'runsTestCase':
                ter.runs_test_case = attrib.get(rdf_resource_attr)
            elif short_tag == 'executesTestScript':
                ter.executes_test_script = attrib.get(rdf_resource_attr)
            elif short_tag == 'runsOnTestEnvironment':
                ter.runs_on_test_environment = attrib.get(rdf_resource_attr)
            elif short_tag == 'reportsOnTestPlan':
                ter.reports_on_test_plan = attrib.get(rdf_resource_attr)
            elif short_tag == 'producesTestResult':
                tr_url = attrib.get(rdf_resource_attr)
                if tr_url and tr_url not in ter.produces_test_results:
                    ter.produces_test_results.append(tr_url)
            elif short_tag == 'currentTestResult':
                ter.current_test_result = attrib.get(rdf_resource_attr)
            elif short_tag == 'lastPassedTestResult':
                ter.last_passed_test_result = attrib.get(rdf_resource_attr)
            elif short_tag == 'testSchedule':
                ter.test_schedule = attrib.get(rdf_resource_attr)

        # Extra rdf:Description blocks with rdf:about (version resource, etc.)
        for desc in root.findall(".//rdf:Description[@rdf:about]", ns):
            about = desc.attrib.get(rdf_about)
            if about == ter.uri:
                continue
            elems = []
            for elem in desc:
                elems.append((elem.tag, dict(elem.attrib), elem.text.strip() if elem.text else ""))
            ter.extra_descriptions[about] = elems

        return ter

    # -------------------------------------------------------------------------
    # RDF/XML serialisation
    # -------------------------------------------------------------------------

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
            add('dcterms', 'creator',     None, {f'{{{rdf_ns}}}resource': self.creator})
        if self.contributor is not None:
            add('dcterms', 'contributor', None, {f'{{{rdf_ns}}}resource': self.contributor})
        if self.type is not None:
            add('rdf', 'type', None, {f'{{{rdf_ns}}}resource': self.type})
        if self.relation is not None:
            add('dcterms', 'relation', None, {f'{{{rdf_ns}}}resource': self.relation})
        if self.short_id is not None:
            add('oslc', 'shortId', self.short_id,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.short_identifier is not None:
            add('rqm_qm', 'shortIdentifier', self.short_identifier,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.weight is not None:
            add('rqm_qm', 'weight', self.weight,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.estimate is not None:
            add('rqm_qm', 'estimate', self.estimate,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#integer'})
        if self.time_spent is not None:
            add('rqm_qm', 'timeSpent', self.time_spent,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#integer'})
        if self.is_suspect_result is not None:
            add('rqm_qm', 'isSuspectResult', self.is_suspect_result,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#boolean'})

        # Resource-reference properties
        if self.runs_test_case is not None:
            add('oslc_qm', 'runsTestCase',           None, {f'{{{rdf_ns}}}resource': self.runs_test_case})
        if self.executes_test_script is not None:
            add('oslc_qm', 'executesTestScript',     None, {f'{{{rdf_ns}}}resource': self.executes_test_script})
        if self.runs_on_test_environment is not None:
            add('oslc_qm', 'runsOnTestEnvironment',  None, {f'{{{rdf_ns}}}resource': self.runs_on_test_environment})
        if self.reports_on_test_plan is not None:
            add('oslc_qm', 'reportsOnTestPlan',      None, {f'{{{rdf_ns}}}resource': self.reports_on_test_plan})
        for tr_url in self.produces_test_results:
            add('rqm_qm', 'producesTestResult', None, {f'{{{rdf_ns}}}resource': tr_url})
        if self.current_test_result is not None:
            add('rqm_qm', 'currentTestResult',       None, {f'{{{rdf_ns}}}resource': self.current_test_result})
        if self.last_passed_test_result is not None:
            add('rqm_qm', 'lastPassedTestResult',    None, {f'{{{rdf_ns}}}resource': self.last_passed_test_result})
        if self.test_schedule is not None:
            add('rqm_qm', 'testSchedule',            None, {f'{{{rdf_ns}}}resource': self.test_schedule})

        # Known tags — skip during pass-through replay to avoid duplication
        known_tags = {
            'title', 'description', 'identifier', 'created', 'modified',
            'creator', 'contributor', 'type', 'relation', 'shortId',
            'shortIdentifier', 'weight', 'estimate', 'timeSpent',
            'isSuspectResult',
            'runsTestCase', 'executesTestScript', 'runsOnTestEnvironment',
            'reportsOnTestPlan', 'producesTestResult', 'currentTestResult',
            'lastPassedTestResult', 'testSchedule',
        }

        # Pass-through elements (accessControl, serviceProvider, hasPriority, etc.)
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

        # Extra rdf:Description blocks (version resource, etc.)
        for about, elems in self.extra_descriptions.items():
            xdesc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                  {ET.QName(rdf_ns, 'about'): about})
            for tag, attrib, text in elems:
                el = ET.SubElement(xdesc, ET.QName(tag), attrib)
                if text:
                    el.text = text

        return ET.ElementTree(rdf)

    def is_xml_equal(self, other: 'TestExecutionRecord') -> bool:
        def clean(xml: ET._ElementTree) -> bytes:
            return ET.tostring(xml.getroot(), encoding='utf-8', method='c14n')
        return clean(self.to_etree()) == clean(other.to_etree())
