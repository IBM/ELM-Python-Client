from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple, Union
import lxml.etree as ET

if TYPE_CHECKING:
    from elmclient.testexecutionrecord import TestExecutionRecord
    from elmclient.testcase import TestCase
    from elmclient.testplan import TestPlan
    from elmclient.testscript import TestScript


# ---------------------------------------------------------------------------
# Shared namespace map — identical to all other QM resource modules
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
class TestResult:
    """
    Represents an ETM Test Result (``oslc_qm:TestResult``).

    The ETM URL path segment is ``com.ibm.rqm.execution.ExecutionResult``.
    A new Test Result is created for **every execution run** of a Test Case
    Execution Record (TCER).  One TCER accumulates many Test Results over time.

    Typical create workflow
    -----------------------
    1. ``TestResult.create_minimal(tcer_uri, tc_uri, tp_uri, verdict)``
       → POST to ``c.get_factory_uri(resource_type='TestResult', ...)``.
       The ``Location`` header of the 201 response gives the real URL.
    2. GET the URL → ``TestResult.from_etree(xml)`` → live object.

    Properties decoded from a real ETM GET response
    ------------------------------------------------
    * ``produced_by_tcer``     – ``oslc_qm:producedByTestExecutionRecord``
    * ``reports_on_test_case`` – ``oslc_qm:reportsOnTestCase``
    * ``reports_on_test_plan`` – ``oslc_qm:reportsOnTestPlan``
    * ``executes_test_script`` – ``oslc_qm:executesTestScript``
    * ``runs_on_test_environment`` – ``oslc_qm:runsOnTestEnvironment``
    * ``status``               – ``oslc_qm:status`` (plain xsd:string, e.g.
                                   ``"com.ibm.rqm.execution.common.state.passed"``)
    * ``verdict``              – ``rqm_qm:verdict`` (resource URI — the
                                   ``#``-fragment form used by ETM)
    * ``start_time``           – ``rqm_qm:startTime`` (xsd:dateTime)
    * ``end_time``             – ``rqm_qm:endTime``   (xsd:dateTime)
    * ``total_run_time``       – ``rqm_qm:totalRunTime`` (ms, xsd:long)
    * ``tested_by``            – ``rqm_qm:testedBy`` (user resource URI)
    * ``test_schedule``        – ``rqm_qm:testSchedule``
    * ``weight``               – ``rqm_qm:weight`` (xsd:long)
    * ``is_rollup``            – ``rqm_qm:isRollup`` (xsd:boolean string)
    * ``is_current``           – ``rqm_qm:isCurrent`` (xsd:boolean string)
    * ``is_current_for_build`` – ``rqm_qm:isCurrentForBuild`` (xsd:boolean)
    * ``is_locked``            – ``rqm_qm:isLocked`` (xsd:boolean string)
    * ``number_of_iterations`` – ``rqm_qm:numberOfIterations`` (xsd:long)
    * ``step_result_urls``     – ``rqm_qm:containsStepResult`` (multi-valued)
    * Score counters (all xsd:long):
        ``points_attempted``, ``points_passed``, ``points_failed``,
        ``points_blocked``, ``points_skipped``, ``points_deferred``,
        ``points_perm_failed``, ``points_inconclusive``, ``total_points``,
        ``script_step_count``, ``script_step_count_attempted``,
        ``script_step_count_passed``, ``script_step_count_failed``,
        ``script_step_count_blocked``, ``script_step_count_skipped``,
        ``script_step_count_deferred``, ``script_step_count_perm_failed``,
        ``script_step_count_inconclusive``
    * Standard Dublin Core: ``title``, ``description``, ``identifier``,
      ``created``, ``modified``, ``creator``, ``contributor``
    """

    # -------------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------------

    @classmethod
    def create_minimal(
        cls,
        produced_by_tcer: Union[str, 'TestExecutionRecord'],
        reports_on_test_case: Union[str, 'TestCase'],
        reports_on_test_plan: Union[str, 'TestPlan'],
        status: str,
        title: Optional[str] = None,
    ) -> 'TestResult':
        """Build the minimal RDF/XML payload required to POST a new Test Result.

        Parameters
        ----------
        produced_by_tcer      : URI string *or* ``TestExecutionRecord`` — the
                                TCER that produced this result
                                (``oslc_qm:producedByTestExecutionRecord``).
        reports_on_test_case  : URI string *or* ``TestCase``
                                (``oslc_qm:reportsOnTestCase``).
        reports_on_test_plan  : URI string *or* ``TestPlan``
                                (``oslc_qm:reportsOnTestPlan``).
        status                : Verdict string, e.g.
                                ``"com.ibm.rqm.execution.common.state.passed"``
                                or ``"com.ibm.rqm.execution.common.state.failed"``
                                (``oslc_qm:status``).
        title                 : Optional human-readable title (``dcterms:title``).
                                Defaults to the status string if not supplied.
        """
        if not isinstance(produced_by_tcer, str):
            produced_by_tcer = produced_by_tcer.uri
        if not isinstance(reports_on_test_case, str):
            reports_on_test_case = reports_on_test_case.uri
        if not isinstance(reports_on_test_plan, str):
            reports_on_test_plan = reports_on_test_plan.uri

        resolved_title = title if title is not None else status

        tr = cls(
            uri="",
            title=resolved_title,
            type="http://open-services.net/ns/qm#TestResult",
            status=status,
            produced_by_tcer=produced_by_tcer,
            reports_on_test_case=reports_on_test_case,
            reports_on_test_plan=reports_on_test_plan,
            namespaces=dict(_NAMESPACES),
        )

        rdf_ns  = _NAMESPACES['rdf']
        dc_ns   = _NAMESPACES['dcterms']
        qm_ns   = _NAMESPACES['oslc_qm']
        xsd_str = 'http://www.w3.org/2001/XMLSchema#string'

        tr.elements.append((
            f'{{{dc_ns}}}title',
            {f'{{{rdf_ns}}}datatype': xsd_str},
            resolved_title,
        ))
        tr.elements.append((
            f'{{{rdf_ns}}}type',
            {f'{{{rdf_ns}}}resource': 'http://open-services.net/ns/qm#TestResult'},
            None,
        ))
        tr.elements.append((
            f'{{{qm_ns}}}producedByTestExecutionRecord',
            {f'{{{rdf_ns}}}resource': produced_by_tcer},
            None,
        ))
        tr.elements.append((
            f'{{{qm_ns}}}reportsOnTestCase',
            {f'{{{rdf_ns}}}resource': reports_on_test_case},
            None,
        ))
        tr.elements.append((
            f'{{{qm_ns}}}reportsOnTestPlan',
            {f'{{{rdf_ns}}}resource': reports_on_test_plan},
            None,
        ))
        tr.elements.append((
            f'{{{qm_ns}}}status',
            {f'{{{rdf_ns}}}datatype': xsd_str},
            status,
        ))

        return tr

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    uri:               str = ""
    title:             Optional[str] = None
    description:       Optional[str] = None
    identifier:        Optional[str] = None
    created:           Optional[str] = None
    modified:          Optional[str] = None
    creator:           Optional[str] = None
    contributor:       Optional[str] = None
    type:              Optional[str] = None
    relation:          Optional[str] = None
    short_id:          Optional[str] = None
    short_identifier:  Optional[str] = None

    # Execution outcome
    status:            Optional[str] = None   # oslc_qm:status  (xsd:string)
    verdict:           Optional[str] = None   # rqm_qm:verdict  (resource URI)
    start_time:        Optional[str] = None   # rqm_qm:startTime
    end_time:          Optional[str] = None   # rqm_qm:endTime
    total_run_time:    Optional[str] = None   # rqm_qm:totalRunTime (ms, xsd:long)

    # Links to other resources
    produced_by_tcer:         Optional[str] = None  # oslc_qm:producedByTestExecutionRecord
    reports_on_test_case:     Optional[str] = None  # oslc_qm:reportsOnTestCase
    reports_on_test_plan:     Optional[str] = None  # oslc_qm:reportsOnTestPlan
    executes_test_script:     Optional[str] = None  # oslc_qm:executesTestScript
    runs_on_test_environment: Optional[str] = None  # oslc_qm:runsOnTestEnvironment
    tested_by:                Optional[str] = None  # rqm_qm:testedBy
    test_schedule:            Optional[str] = None  # rqm_qm:testSchedule

    # Boolean flags (stored as xsd:boolean strings "true"/"false")
    is_rollup:           Optional[str] = None  # rqm_qm:isRollup
    is_current:          Optional[str] = None  # rqm_qm:isCurrent
    is_current_for_build: Optional[str] = None # rqm_qm:isCurrentForBuild
    is_locked:           Optional[str] = None  # rqm_qm:isLocked

    # Iteration / weight
    number_of_iterations: Optional[str] = None  # rqm_qm:numberOfIterations (xsd:long)
    weight:               Optional[str] = None  # rqm_qm:weight (xsd:long)

    # Point-based score counters (all xsd:long)
    points_attempted:   Optional[str] = None
    points_passed:      Optional[str] = None
    points_failed:      Optional[str] = None
    points_blocked:     Optional[str] = None
    points_skipped:     Optional[str] = None
    points_deferred:    Optional[str] = None
    points_perm_failed: Optional[str] = None
    points_inconclusive: Optional[str] = None
    total_points:       Optional[str] = None

    # Script-step counters (all xsd:long)
    script_step_count:               Optional[str] = None
    script_step_count_attempted:     Optional[str] = None
    script_step_count_passed:        Optional[str] = None
    script_step_count_failed:        Optional[str] = None
    script_step_count_blocked:       Optional[str] = None
    script_step_count_skipped:       Optional[str] = None
    script_step_count_deferred:      Optional[str] = None
    script_step_count_perm_failed:   Optional[str] = None
    script_step_count_inconclusive:  Optional[str] = None

    # Multi-valued: one URL per step result
    step_result_urls: List[str] = field(default_factory=list)

    namespaces:         Dict[str, str] = field(default_factory=dict)
    elements:           List[Tuple[str, Dict[str, str], Optional[str]]] = field(default_factory=list)
    extra_descriptions: Dict[str, List[Tuple[str, Dict[str, str], Optional[str]]]] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # RDF/XML parsing
    # -------------------------------------------------------------------------

    @staticmethod
    def from_etree(etree: ET._ElementTree) -> 'TestResult':
        """Parse a GET response for an ``ExecutionResult`` resource.

        The main ``rdf:Description`` is identified by the substring
        ``'ExecutionResult'`` in its ``rdf:about`` URI where the segment after
        ``ExecutionResult/`` contains no further ``/`` (i.e. the resource itself,
        not its version sub-resource).
        """
        root       = etree.getroot()
        namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        ns         = namespaces.copy()

        rdf_about         = f'{{{ns["rdf"]}}}about'
        rdf_resource_attr = f'{{{ns["rdf"]}}}resource'

        # Main element: 'ExecutionResult' in URI, no '#',
        # and the segment after 'ExecutionResult/' has no further '/'.
        main_elem = None
        for elem in root.findall(".//rdf:Description[@rdf:about]", ns):
            uri = elem.attrib.get(rdf_about, "")
            if 'ExecutionResult' in uri and '#' not in uri:
                after = uri.split('ExecutionResult/')[1]
                if '/' not in after:
                    main_elem = elem
                    break

        if main_elem is None:
            raise ValueError(
                "No main rdf:Description for a TestResult "
                "(ExecutionResult without sub-path) found"
            )

        uri = main_elem.attrib[rdf_about]
        tr  = TestResult(uri=uri, namespaces=namespaces)

        # Mapping of localname → (field_attr, is_resource)
        _LONG_COUNTERS = {
            'pointsAttempted':            'points_attempted',
            'pointsPassed':               'points_passed',
            'pointsFailed':               'points_failed',
            'pointsBlocked':              'points_blocked',
            'pointsSkipped':              'points_skipped',
            'pointsDeferred':             'points_deferred',
            'pointsPermFailed':           'points_perm_failed',
            'pointsInconclusive':         'points_inconclusive',
            'totalPoints':                'total_points',
            'scriptStepCount':            'script_step_count',
            'scriptStepCountAttempted':   'script_step_count_attempted',
            'scriptStepCountPassed':      'script_step_count_passed',
            'scriptStepCountFailed':      'script_step_count_failed',
            'scriptStepCountBlocked':     'script_step_count_blocked',
            'scriptStepCountSkipped':     'script_step_count_skipped',
            'scriptStepCountDeferred':    'script_step_count_deferred',
            'scriptStepCountPermFailed':  'script_step_count_perm_failed',
            'scriptStepCountInconclusive':'script_step_count_inconclusive',
            'totalRunTime':               'total_run_time',
            'weight':                     'weight',
            'numberOfIterations':         'number_of_iterations',
        }

        for elem in main_elem:
            tag       = elem.tag
            text      = elem.text.strip() if elem.text else ""
            attrib    = dict(elem.attrib)
            short_tag = ET.QName(tag).localname
            tr.elements.append((tag, attrib, text))

            if short_tag == 'title' and tag.startswith('{http://purl.org/dc/terms/}'):
                tr.title = text
            elif short_tag == 'description':
                tr.description = text
            elif short_tag == 'identifier':
                tr.identifier = text
            elif short_tag == 'created':
                tr.created = text
            elif short_tag == 'modified':
                tr.modified = text
            elif short_tag == 'creator':
                tr.creator = attrib.get(rdf_resource_attr)
            elif short_tag == 'contributor':
                tr.contributor = attrib.get(rdf_resource_attr)
            elif short_tag == 'type' and rdf_resource_attr in attrib:
                tr.type = attrib[rdf_resource_attr]
            elif short_tag == 'relation':
                tr.relation = attrib.get(rdf_resource_attr)
            elif short_tag == 'shortId':
                tr.short_id = text
            elif short_tag == 'shortIdentifier':
                tr.short_identifier = text
            elif short_tag == 'status':
                tr.status = text
            elif short_tag == 'verdict':
                tr.verdict = attrib.get(rdf_resource_attr)
            elif short_tag == 'startTime':
                tr.start_time = text
            elif short_tag == 'endTime':
                tr.end_time = text
            elif short_tag == 'producedByTestExecutionRecord':
                tr.produced_by_tcer = attrib.get(rdf_resource_attr)
            elif short_tag == 'reportsOnTestCase':
                tr.reports_on_test_case = attrib.get(rdf_resource_attr)
            elif short_tag == 'reportsOnTestPlan':
                tr.reports_on_test_plan = attrib.get(rdf_resource_attr)
            elif short_tag == 'executesTestScript':
                tr.executes_test_script = attrib.get(rdf_resource_attr)
            elif short_tag == 'runsOnTestEnvironment':
                tr.runs_on_test_environment = attrib.get(rdf_resource_attr)
            elif short_tag == 'testedBy':
                tr.tested_by = attrib.get(rdf_resource_attr)
            elif short_tag == 'testSchedule':
                tr.test_schedule = attrib.get(rdf_resource_attr)
            elif short_tag == 'isRollup':
                tr.is_rollup = text
            elif short_tag == 'isCurrent':
                tr.is_current = text
            elif short_tag == 'isCurrentForBuild':
                tr.is_current_for_build = text
            elif short_tag == 'isLocked':
                tr.is_locked = text
            elif short_tag == 'containsStepResult':
                step_url = attrib.get(rdf_resource_attr)
                if step_url and step_url not in tr.step_result_urls:
                    tr.step_result_urls.append(step_url)
            elif short_tag in _LONG_COUNTERS:
                setattr(tr, _LONG_COUNTERS[short_tag], text)

        # Extra rdf:Description blocks with rdf:about (version resource, etc.)
        for desc in root.findall(".//rdf:Description[@rdf:about]", ns):
            about = desc.attrib.get(rdf_about)
            if about == tr.uri:
                continue
            elems = []
            for elem in desc:
                elems.append((elem.tag, dict(elem.attrib), elem.text.strip() if elem.text else ""))
            tr.extra_descriptions[about] = elems

        return tr

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

        def res(ns_key: str, local: str, uri: str):
            """Emit a resource-reference element."""
            add(ns_key, local, None, {f'{{{rdf_ns}}}resource': uri})

        def lit(ns_key: str, local: str, value: str, xsd_type: str):
            """Emit a typed literal element."""
            add(ns_key, local, value,
                {f'{{{rdf_ns}}}datatype': f'http://www.w3.org/2001/XMLSchema#{xsd_type}'})

        # Dublin Core scalars
        if self.title is not None:
            lit('dcterms', 'title', self.title, 'string')
        if self.description is not None:
            lit('dcterms', 'description', self.description, 'string')
        if self.identifier is not None:
            lit('dcterms', 'identifier', self.identifier, 'string')
        if self.created is not None:
            lit('dcterms', 'created', self.created, 'dateTime')
        if self.modified is not None:
            lit('dcterms', 'modified', self.modified, 'dateTime')
        if self.creator is not None:
            res('dcterms', 'creator', self.creator)
        if self.contributor is not None:
            res('dcterms', 'contributor', self.contributor)
        if self.type is not None:
            res('rdf', 'type', self.type)
        if self.relation is not None:
            res('dcterms', 'relation', self.relation)
        if self.short_id is not None:
            lit('oslc', 'shortId', self.short_id, 'int')
        if self.short_identifier is not None:
            lit('rqm_qm', 'shortIdentifier', self.short_identifier, 'string')

        # Execution outcome
        if self.status is not None:
            lit('oslc_qm', 'status', self.status, 'string')
        if self.verdict is not None:
            res('rqm_qm', 'verdict', self.verdict)
        if self.start_time is not None:
            lit('rqm_qm', 'startTime', self.start_time, 'dateTime')
        if self.end_time is not None:
            lit('rqm_qm', 'endTime', self.end_time, 'dateTime')
        if self.total_run_time is not None:
            lit('rqm_qm', 'totalRunTime', self.total_run_time, 'long')

        # Resource references
        if self.produced_by_tcer is not None:
            res('oslc_qm', 'producedByTestExecutionRecord', self.produced_by_tcer)
        if self.reports_on_test_case is not None:
            res('oslc_qm', 'reportsOnTestCase', self.reports_on_test_case)
        if self.reports_on_test_plan is not None:
            res('oslc_qm', 'reportsOnTestPlan', self.reports_on_test_plan)
        if self.executes_test_script is not None:
            res('oslc_qm', 'executesTestScript', self.executes_test_script)
        if self.runs_on_test_environment is not None:
            res('oslc_qm', 'runsOnTestEnvironment', self.runs_on_test_environment)
        if self.tested_by is not None:
            res('rqm_qm', 'testedBy', self.tested_by)
        if self.test_schedule is not None:
            res('rqm_qm', 'testSchedule', self.test_schedule)

        # Boolean flags
        if self.is_rollup is not None:
            lit('rqm_qm', 'isRollup', self.is_rollup, 'boolean')
        if self.is_current is not None:
            lit('rqm_qm', 'isCurrent', self.is_current, 'boolean')
        if self.is_current_for_build is not None:
            lit('rqm_qm', 'isCurrentForBuild', self.is_current_for_build, 'boolean')
        if self.is_locked is not None:
            lit('rqm_qm', 'isLocked', self.is_locked, 'boolean')

        # Numeric literals (xsd:long)
        _long_fields = [
            ('weight',                      'rqm_qm', 'weight'),
            ('number_of_iterations',        'rqm_qm', 'numberOfIterations'),
            ('points_attempted',            'rqm_qm', 'pointsAttempted'),
            ('points_passed',               'rqm_qm', 'pointsPassed'),
            ('points_failed',               'rqm_qm', 'pointsFailed'),
            ('points_blocked',              'rqm_qm', 'pointsBlocked'),
            ('points_skipped',              'rqm_qm', 'pointsSkipped'),
            ('points_deferred',             'rqm_qm', 'pointsDeferred'),
            ('points_perm_failed',          'rqm_qm', 'pointsPermFailed'),
            ('points_inconclusive',         'rqm_qm', 'pointsInconclusive'),
            ('total_points',                'rqm_qm', 'totalPoints'),
            ('script_step_count',           'rqm_qm', 'scriptStepCount'),
            ('script_step_count_attempted', 'rqm_qm', 'scriptStepCountAttempted'),
            ('script_step_count_passed',    'rqm_qm', 'scriptStepCountPassed'),
            ('script_step_count_failed',    'rqm_qm', 'scriptStepCountFailed'),
            ('script_step_count_blocked',   'rqm_qm', 'scriptStepCountBlocked'),
            ('script_step_count_skipped',   'rqm_qm', 'scriptStepCountSkipped'),
            ('script_step_count_deferred',  'rqm_qm', 'scriptStepCountDeferred'),
            ('script_step_count_perm_failed','rqm_qm','scriptStepCountPermFailed'),
            ('script_step_count_inconclusive','rqm_qm','scriptStepCountInconclusive'),
        ]

        for attr, ns_key, local in _long_fields:
            val = getattr(self, attr, None)
            if val is not None:
                lit(ns_key, local, val, 'long')

        # Multi-valued step result references
        rqm_qm_ns = NSMAP.get('rqm_qm', 'http://jazz.net/ns/qm/rqm#')
        for step_url in self.step_result_urls:
            ET.SubElement(desc, ET.QName(rqm_qm_ns, 'containsStepResult'),
                          {ET.QName(rdf_ns, 'resource'): step_url})

        # Known tags — skip during pass-through replay to avoid duplication
        known_tags = {
            'title', 'description', 'identifier', 'created', 'modified',
            'creator', 'contributor', 'type', 'relation', 'shortId',
            'shortIdentifier', 'status', 'verdict', 'startTime', 'endTime',
            'totalRunTime', 'producedByTestExecutionRecord', 'reportsOnTestCase',
            'reportsOnTestPlan', 'executesTestScript', 'runsOnTestEnvironment',
            'testedBy', 'testSchedule', 'isRollup', 'isCurrent',
            'isCurrentForBuild', 'isLocked', 'weight', 'numberOfIterations',
            'pointsAttempted', 'pointsPassed', 'pointsFailed', 'pointsBlocked',
            'pointsSkipped', 'pointsDeferred', 'pointsPermFailed',
            'pointsInconclusive', 'totalPoints',
            'scriptStepCount', 'scriptStepCountAttempted', 'scriptStepCountPassed',
            'scriptStepCountFailed', 'scriptStepCountBlocked', 'scriptStepCountSkipped',
            'scriptStepCountDeferred', 'scriptStepCountPermFailed',
            'scriptStepCountInconclusive',
            'containsStepResult',   # emitted above via step_result_urls
        }

        # Pass-through elements (accessControl, serviceProvider, workflowState, etc.)
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

    def is_xml_equal(self, other: 'TestResult') -> bool:
        def clean(xml: ET._ElementTree) -> bytes:
            return ET.tostring(xml.getroot(), encoding='utf-8', method='c14n')
        return clean(self.to_etree()) == clean(other.to_etree())
