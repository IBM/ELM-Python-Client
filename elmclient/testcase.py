from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple, Union
import lxml.etree as ET

if TYPE_CHECKING:
    from elmclient.testscript import TestScript
    from elmclient.testexecutionrecord import TestExecutionRecord
    from elmclient.testplan import TestPlan


@dataclass
class TestCaseLink:
    """Represents a reified rdf:Statement for a validatesRequirement link."""
    node_id:   Optional[str] = None
    subject:   Optional[str] = None
    predicate: str = ""
    target:    str = ""
    title:     Optional[str] = None


@dataclass
class TestCase:
    @classmethod
    def create_minimal(cls, title: str) -> 'TestCase':
        namespaces = {
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

        tc = cls(
            uri="",
            title=title,
            type="http://open-services.net/ns/qm#TestCase",
            namespaces=namespaces,
        )

        tc.elements.append((
            '{http://purl.org/dc/terms/}title',
            {'{http://www.w3.org/2001/XMLSchema#}datatype': 'http://www.w3.org/2001/XMLSchema#string'},
            title,
        ))
        tc.elements.append((
            '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}type',
            {'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource': 'http://open-services.net/ns/qm#TestCase'},
            None,
        ))

        return tc

    uri:              str = ""
    title:            Optional[str] = None
    description:      Optional[str] = None
    identifier:       Optional[str] = None
    created:          Optional[str] = None
    modified:         Optional[str] = None
    creator:          Optional[str] = None
    contributor:      Optional[str] = None
    type:             Optional[str] = None
    relation:         Optional[str] = None
    short_id:         Optional[str] = None
    short_identifier: Optional[str] = None
    script_step_count: Optional[str] = None
    weight:           Optional[str] = None
    is_locked:        Optional[str] = None
    # oslc_qm:usesTestScript — multi-valued direct properties, no reified statement
    test_scripts:     List[str]     = field(default_factory=list)
    # reified rdf:Statements — used for validatesRequirement links
    links:            List[TestCaseLink] = field(default_factory=list)
    namespaces:       Dict[str, str] = field(default_factory=dict)
    elements:         List[Tuple[str, Dict[str, str], Optional[str]]] = field(default_factory=list)
    extra_descriptions: Dict[str, List[Tuple[str, Dict[str, str], Optional[str]]]] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # TestExecutionRecord helpers
    #
    # NOTE: ETM does NOT embed TCER back-references in the TestCase RDF/XML.
    # The link is stored on the TCER (oslc_qm:runsTestCase → TestCase URI).
    # TCERs are discovered through an OSLC query, not by parsing the TestCase.
    #
    # These helpers provide convenience entry points for that workflow without
    # storing network-derived state on the TestCase object itself.
    # -------------------------------------------------------------------------

    def create_tcer(
        self,
        title: str,
        test_plan: Optional[Union[str, 'TestPlan']] = None,
    ) -> 'TestExecutionRecord':
        """Return a new :class:`~elmclient.testexecutionrecord.TestExecutionRecord`
        pre-wired to this test case, ready to POST.

        When the test case references exactly one test script
        (``oslc_qm:usesTestScript``), that script is automatically set as
        ``oslc_qm:executesTestScript`` on the new TCER so ETM assigns the
        default test script on creation.  If the test case has zero or more
        than one test script, ``executesTestScript`` is left unset.

        The ``test_plan`` argument must be supplied explicitly because the
        Test Plan → Test Case link lives on the ``TestPlan`` side and is not
        visible in the ``TestCase`` XML.

        Parameters
        ----------
        title     : Human-readable title for the new TCER.
        test_plan : Optional URI string *or* ``TestPlan`` object.  When
                    supplied, sets ``oslc_qm:reportsOnTestPlan`` on the new
                    TCER so ETM links it to the correct test plan on creation.

        Usage::

            tcer = tc.create_tcer("Login on Chrome", test_plan=tp_url)
            response = c.execute_post_rdf_xml(
                tcer_factory_u, data=tcer.to_etree(),
                intent="Create TCER", headers=post_headers,
                remove_parameters=['oslc_config.context'],
            )
            tcer_url = response.headers['Location']

        Raises ``ValueError`` if ``self.uri`` is empty (the test case has not
        yet been saved to ETM).
        """
        if not self.uri:
            raise ValueError(
                "TestCase.uri is empty — save the test case to ETM first "
                "before creating a TCER from it."
            )
        from elmclient.testexecutionrecord import TestExecutionRecord
        # Auto-wire the single test script when there is exactly one
        script_uri = self.test_scripts[0] if len(self.test_scripts) == 1 else None
        return TestExecutionRecord.create_minimal(
            title,
            runs_test_case=self.uri,
            executes_test_script=script_uri,
            reports_on_test_plan=test_plan,
        )

    def tcer_query_terms(self) -> List[List[str]]:
        """Return OSLC ``whereterms`` that find all TCERs for this test case.

        Pass the result directly to ``c.execute_oslc_query``::

            tcers = c.execute_oslc_query(
                c.get_query_capability_uri("oslc_qm:TestExecutionRecordQuery"),
                whereterms=tc.tcer_query_terms(),
                select=['*'],
            )

        Raises ``ValueError`` if ``self.uri`` is empty.
        """
        if not self.uri:
            raise ValueError(
                "TestCase.uri is empty — the test case must have a URI "
                "to query its TCERs."
            )
        return [['oslc_qm:runsTestCase', '=', f'<{self.uri}>']]

    # -------------------------------------------------------------------------
    # usesTestScript helpers
    # Stored as plain direct properties only (no reified statement),
    # identical to how TestPlan handles usesTestCase.
    # -------------------------------------------------------------------------

    def add_usesTestScript(self, target: Union[str, 'TestScript']) -> None:
        """Add an ``oslc_qm:usesTestScript`` reference.

        *target* can be either a plain URI string or a ``TestScript`` object,
        in which case ``testscript.uri`` is used.
        """
        if not isinstance(target, str):
            target = target.uri
        if target not in self.test_scripts:
            self.test_scripts.append(target)
        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns     = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        tag        = '{' + oslc_qm_ns + '}usesTestScript'
        attrib     = {'{' + rdf_ns + '}resource': target}
        already    = any(
            e[0] == tag and e[1].get('{' + rdf_ns + '}resource') == target
            for e in self.elements
        )
        if not already:
            self.elements.append((tag, attrib, None))

    def remove_usesTestScript(self, target: Union[str, 'TestScript']) -> bool:
        """Remove an ``oslc_qm:usesTestScript`` reference.

        *target* can be either a plain URI string or a ``TestScript`` object.
        Returns True if found and removed, False otherwise.
        """
        if not isinstance(target, str):
            target = target.uri
        initial_len = len(self.test_scripts)
        self.test_scripts = [ts for ts in self.test_scripts if ts != target]

        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns     = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        ts_tag     = '{' + oslc_qm_ns + '}usesTestScript'
        self.elements = [
            e for e in self.elements
            if not (e[0] == ts_tag and e[1].get('{' + rdf_ns + '}resource') == target)
        ]

        return len(self.test_scripts) < initial_len

    # -------------------------------------------------------------------------
    # validatesRequirement helpers
    # Stored as BOTH a reified rdf:Statement (-> links) AND a direct property
    # element on the main description (-> elements).
    # -------------------------------------------------------------------------

    def add_validatesRequirementLink(self, target: str, title: Optional[str] = None) -> None:
        """Add a ``oslc_qm:validatesRequirement`` link to a requirement."""
        self.links.append(TestCaseLink(
            subject=self.uri,
            predicate="http://open-services.net/ns/qm#validatesRequirement",
            target=target,
            title=title,
        ))
        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns     = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        tag        = '{' + oslc_qm_ns + '}validatesRequirement'
        attrib     = {'{' + rdf_ns + '}resource': target}
        self.elements.append((tag, attrib, None))

    def delete_validatesRequirementLink(self, target: str) -> bool:
        """Remove a ``validatesRequirement`` link by target URI.

        Returns True if at least one link was removed.
        """
        initial_links = len(self.links)
        self.links = [
            link for link in self.links
            if not (
                link.predicate == "http://open-services.net/ns/qm#validatesRequirement"
                and link.target == target
            )
        ]
        oslc_qm_ns   = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns       = self.namespaces.get('rdf',     'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        validate_tag = '{' + oslc_qm_ns + '}validatesRequirement'
        self.elements = [
            e for e in self.elements
            if not (e[0] == validate_tag and e[1].get('{' + rdf_ns + '}resource') == target)
        ]
        return len(self.links) < initial_links

    # -------------------------------------------------------------------------
    # RDF/XML parsing
    # -------------------------------------------------------------------------

    @staticmethod
    def from_etree(etree: ET._ElementTree) -> 'TestCase':
        root       = etree.getroot()
        namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        ns         = namespaces.copy()

        rdf_about        = f'{{{ns["rdf"]}}}about'
        rdf_resource_attr = f'{{{ns["rdf"]}}}resource'

        # Main element: 'TestCase' in URI, no '#'
        main_elem = None
        for elem in root.findall(".//rdf:Description[@rdf:about]", ns):
            uri = elem.attrib.get(rdf_about, "")
            if 'TestCase' in uri and '#' not in uri:
                main_elem = elem
                break

        if main_elem is None:
            raise ValueError("No main rdf:Description for a TestCase found")

        uri      = main_elem.attrib[rdf_about]
        testcase = TestCase(uri=uri, namespaces=namespaces)

        for elem in main_elem:
            tag       = elem.tag
            text      = elem.text.strip() if elem.text else ""
            attrib    = dict(elem.attrib)
            short_tag = ET.QName(tag).localname
            testcase.elements.append((tag, attrib, text))

            if short_tag == 'title' and tag.startswith('{http://purl.org/dc/terms/}'):
                testcase.title = text
            elif short_tag == 'identifier':
                testcase.identifier = text
            elif short_tag == 'description':
                testcase.description = text
            elif short_tag == 'created':
                testcase.created = text
            elif short_tag == 'modified':
                testcase.modified = text
            elif short_tag == 'creator':
                testcase.creator = attrib.get(rdf_resource_attr)
            elif short_tag == 'contributor':
                testcase.contributor = attrib.get(rdf_resource_attr)
            elif short_tag == 'type' and rdf_resource_attr in attrib:
                testcase.type = attrib[rdf_resource_attr]
            elif short_tag == 'relation':
                testcase.relation = attrib.get(rdf_resource_attr)
            elif short_tag == 'shortId':
                testcase.short_id = text
            elif short_tag == 'shortIdentifier':
                testcase.short_identifier = text
            elif short_tag == 'scriptStepCount':
                testcase.script_step_count = text
            elif short_tag == 'weight':
                testcase.weight = text
            elif short_tag == 'isLocked':
                testcase.is_locked = text
            elif short_tag == 'usesTestScript':
                ts_uri = attrib.get(rdf_resource_attr)
                if ts_uri and ts_uri not in testcase.test_scripts:
                    testcase.test_scripts.append(ts_uri)

        # Reified rdf:Statements (validatesRequirement links)
        for stmt in root.findall('.//rdf:Description[@rdf:nodeID]', ns):
            node_id       = stmt.attrib.get(f'{{{ns["rdf"]}}}nodeID')
            subject_elem  = stmt.find('rdf:subject',   ns)
            pred_elem     = stmt.find('rdf:predicate', ns)
            object_elem   = stmt.find('rdf:object',    ns)
            title_elem    = stmt.find('dcterms:title', ns)

            if subject_elem is not None and pred_elem is not None and object_elem is not None:
                testcase.links.append(TestCaseLink(
                    node_id   = node_id,
                    subject   = subject_elem.attrib.get(rdf_resource_attr),
                    predicate = pred_elem.attrib.get(rdf_resource_attr),
                    target    = object_elem.attrib.get(rdf_resource_attr),
                    title     = title_elem.text if title_elem is not None else None,
                ))

        # Extra rdf:Description blocks with rdf:about (not the main one)
        for desc in root.findall(".//rdf:Description[@rdf:about]", ns):
            about = desc.attrib.get(rdf_about)
            if about == testcase.uri:
                continue
            elems = []
            for elem in desc:
                elems.append((elem.tag, dict(elem.attrib), elem.text.strip() if elem.text else ""))
            testcase.extra_descriptions[about] = elems

        return testcase

    # -------------------------------------------------------------------------
    # RDF/XML serialisation
    # -------------------------------------------------------------------------

    def to_etree(self) -> ET._ElementTree:
        NSMAP  = self.namespaces or {'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
        rdf_ns = NSMAP['rdf']
        rdf    = ET.Element(ET.QName(rdf_ns, 'RDF'), nsmap=NSMAP)

        if self.uri:
            desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                 {ET.QName(rdf_ns, 'about'): self.uri})
        else:
            desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'))

        def add(tag_ns: str, tag: str, text=None, attrib=None):
            el = ET.SubElement(desc, ET.QName(NSMAP[tag_ns], tag), attrib or {})
            if text:
                el.text = text

        if self.title is not None:
            add('dcterms', 'title', self.title,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.identifier is not None:
            add('dcterms', 'identifier', self.identifier,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.description is not None:
            add('dcterms', 'description', self.description,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.created is not None:
            add('dcterms', 'created', self.created,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.modified is not None:
            add('dcterms', 'modified', self.modified,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.creator:
            add('dcterms', 'creator',     None, {f'{{{rdf_ns}}}resource': self.creator})
        if self.contributor:
            add('dcterms', 'contributor', None, {f'{{{rdf_ns}}}resource': self.contributor})
        if self.type:
            add('rdf', 'type', None, {f'{{{rdf_ns}}}resource': self.type})
        if self.relation:
            add('dcterms', 'relation', None, {f'{{{rdf_ns}}}resource': self.relation})
        if self.short_id:
            add('oslc', 'shortId', self.short_id,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.short_identifier:
            add('rqm_qm', 'shortIdentifier', self.short_identifier,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.script_step_count:
            add('rqm_qm', 'scriptStepCount', self.script_step_count,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#long'})
        if self.weight:
            add('rqm_qm', 'weight', self.weight,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.is_locked:
            add('rqm_qm', 'isLocked', self.is_locked,
                {f'{{{rdf_ns}}}datatype': 'http://www.w3.org/2001/XMLSchema#boolean'})

        # Known tags — skip during pass-through replay so we don't duplicate them
        known_tags = {
            'title', 'description', 'identifier', 'created', 'modified',
            'creator', 'contributor', 'type', 'relation', 'shortId',
            'shortIdentifier', 'scriptStepCount', 'weight', 'isLocked',
            # usesTestScript is emitted explicitly below
            'usesTestScript',
        }

        # Pass-through elements (categories, priority, state, etc.)
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

        # Emit oslc_qm:usesTestScript — one element per script URI
        oslc_qm_ns = NSMAP.get('oslc_qm', 'http://open-services.net/ns/qm#')
        for ts_uri in self.test_scripts:
            ET.SubElement(desc, ET.QName(oslc_qm_ns, 'usesTestScript'),
                          {ET.QName(rdf_ns, 'resource'): ts_uri})

        # Reified rdf:Statement blocks (validatesRequirement links)
        for link in self.links:
            attribs = {}
            if link.node_id:
                attribs[ET.QName(rdf_ns, 'nodeID')] = link.node_id
            stmt = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'), attribs)
            ET.SubElement(stmt, ET.QName(rdf_ns, 'subject'),
                          {ET.QName(rdf_ns, 'resource'): link.subject or self.uri})
            ET.SubElement(stmt, ET.QName(rdf_ns, 'predicate'),
                          {ET.QName(rdf_ns, 'resource'): link.predicate})
            ET.SubElement(stmt, ET.QName(rdf_ns, 'object'),
                          {ET.QName(rdf_ns, 'resource'): link.target})
            ET.SubElement(stmt, ET.QName(rdf_ns, 'type'),
                          {ET.QName(rdf_ns, 'resource'): rdf_ns + 'Statement'})
            if link.title:
                ET.SubElement(stmt, ET.QName(NSMAP['dcterms'], 'title')).text = link.title

        # Extra rdf:Description blocks (sub-resources, version resource, etc.)
        for about, elems in self.extra_descriptions.items():
            xdesc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'),
                                  {ET.QName(rdf_ns, 'about'): about})
            for tag, attrib, text in elems:
                el = ET.SubElement(xdesc, ET.QName(tag), attrib)
                if text:
                    el.text = text

        return ET.ElementTree(rdf)

    def is_xml_equal(self, other: 'TestCase') -> bool:
        def clean(xml: ET._ElementTree) -> bytes:
            return ET.tostring(xml.getroot(), encoding='utf-8', method='c14n')
        return clean(self.to_etree()) == clean(other.to_etree())
