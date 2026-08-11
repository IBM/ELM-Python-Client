from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple, Union
import lxml.etree as ET

if TYPE_CHECKING:
    from elmclient.testcase import TestCase


@dataclass
class TestPlanLink:
    """Represents a reified rdf:Statement for a validatesRequirementCollection link."""
    node_id: Optional[str] = None
    subject: Optional[str] = None
    predicate: str = ""
    target: str = ""
    title: Optional[str] = None


@dataclass
class TestPlan:
    @classmethod
    def create_minimal(cls, title: str) -> 'TestPlan':
        namespaces = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'dcterms': 'http://purl.org/dc/terms/',
            'oslc_qm': 'http://open-services.net/ns/qm#',
            'rqm_auto': 'http://jazz.net/ns/auto/rqm#',
            'acp': 'http://jazz.net/ns/acp#',
            'calm': 'http://jazz.net/xmlns/prod/jazz/calm/1.0/',
            'acc': 'http://open-services.net/ns/core/acc#',
            'process': 'http://jazz.net/ns/process#',
            'skos': 'http://www.w3.org/2004/02/skos/core#',
            'jrs': 'http://jazz.net/ns/jrs#',
            'oslc_auto': 'http://open-services.net/ns/auto#',
            'xsd': 'http://www.w3.org/2001/XMLSchema#',
            'bp': 'http://open-services.net/ns/basicProfile#',
            'cmx': 'http://open-services.net/ns/cm-x#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
            'rqm_lm': 'http://jazz.net/ns/qm/rqm/labmanagement#',
            'oslc': 'http://open-services.net/ns/core#',
            'owl': 'http://www.w3.org/2002/07/owl#',
            'rqm_process': 'http://jazz.net/xmlns/prod/jazz/rqm/process/1.0/',
            'jazz': 'http://jazz.net/ns/jazz#',
            'oslc_config': 'http://open-services.net/ns/config#',
            'oslc_cm': 'http://open-services.net/ns/cm#',
            'rqm_qm': 'http://jazz.net/ns/qm/rqm#',
            'oslc_rm': 'http://open-services.net/ns/rm#',
            'foaf': 'http://xmlns.com/foaf/0.1/'
        }

        tp = cls(
            uri="",
            title=title,
            type="http://open-services.net/ns/qm#TestPlan",
            namespaces=namespaces
        )

        tp.elements.append((
            '{http://purl.org/dc/terms/}title',
            {'{http://www.w3.org/2001/XMLSchema#}datatype': 'http://www.w3.org/2001/XMLSchema#string'},
            title
        ))
        tp.elements.append((
            '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}type',
            {'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource': 'http://open-services.net/ns/qm#TestPlan'},
            None
        ))

        return tp

    uri: str = ""
    title: Optional[str] = None
    description: Optional[str] = None
    identifier: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    creator: Optional[str] = None
    contributor: Optional[str] = None
    type: Optional[str] = None
    relation: Optional[str] = None
    short_id: Optional[str] = None
    short_identifier: Optional[str] = None
    is_locked: Optional[str] = None
    # oslc_qm:usesTestCase — multi-valued direct properties, no reified statement
    test_cases: List[str] = field(default_factory=list)
    # reified rdf:Statements — only used for validatesRequirementCollection
    links: List[TestPlanLink] = field(default_factory=list)
    namespaces: Dict[str, str] = field(default_factory=dict)
    elements: List[Tuple[str, Dict[str, str], Optional[str]]] = field(default_factory=list)
    extra_descriptions: Dict[str, List[Tuple[str, Dict[str, str], Optional[str]]]] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # validatesRequirementCollection helpers
    # Stored as BOTH a reified rdf:Statement (-> links) AND a direct property
    # element on the main description (-> elements), identical to how TestCase
    # handles validatesRequirement.
    # -------------------------------------------------------------------------

    def add_validatesRequirementCollectionLink(self, target: str, title: Optional[str] = None):
        """Add a validatesRequirementCollection link to a requirement collection (e.g. a DNG module)."""
        self.links.append(TestPlanLink(
            subject=self.uri,
            predicate="http://open-services.net/ns/qm#validatesRequirementCollection",
            target=target,
            title=title
        ))
        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns = self.namespaces.get('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        tag = '{' + oslc_qm_ns + '}validatesRequirementCollection'
        attrib = {'{' + rdf_ns + '}resource': target}
        self.elements.append((tag, attrib, None))

    def delete_validatesRequirementCollectionLink(self, target: str) -> bool:
        """Remove a validatesRequirementCollection link by target URI.

        Returns True if at least one link was removed, False if none matched.
        """
        initial_links = len(self.links)
        self.links = [
            link for link in self.links
            if not (
                link.predicate == "http://open-services.net/ns/qm#validatesRequirementCollection"
                and link.target == target
            )
        ]

        rdf_ns = self.namespaces.get('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        validate_tag = '{' + oslc_qm_ns + '}validatesRequirementCollection'
        self.elements = [
            e for e in self.elements
            if not (
                e[0] == validate_tag
                and e[1].get('{' + rdf_ns + '}resource') == target
            )
        ]

        return len(self.links) < initial_links

    # -------------------------------------------------------------------------
    # usesTestCase helpers
    # Stored as plain direct properties only (no reified statement).
    # -------------------------------------------------------------------------

    def add_usesTestCase(self, target: Union[str, 'TestCase']):
        """Add an oslc_qm:usesTestCase reference.

        *target* can be either a plain URI string or a ``TestCase`` object,
        in which case ``testcase.uri`` is used.
        """
        if not isinstance(target, str):
            target = target.uri
        if target not in self.test_cases:
            self.test_cases.append(target)
        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns = self.namespaces.get('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        tag = '{' + oslc_qm_ns + '}usesTestCase'
        attrib = {'{' + rdf_ns + '}resource': target}
        # Only add to elements if not already present
        already = any(
            e[0] == tag and e[1].get('{' + rdf_ns + '}resource') == target
            for e in self.elements
        )
        if not already:
            self.elements.append((tag, attrib, None))

    def remove_usesTestCase(self, target: Union[str, 'TestCase']) -> bool:
        """Remove an oslc_qm:usesTestCase reference.

        *target* can be either a plain URI string or a ``TestCase`` object,
        in which case ``testcase.uri`` is used.
        Returns True if the test case was found and removed, False otherwise.
        """
        if not isinstance(target, str):
            target = target.uri
        initial_len = len(self.test_cases)
        self.test_cases = [tc for tc in self.test_cases if tc != target]

        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns = self.namespaces.get('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        tc_tag = '{' + oslc_qm_ns + '}usesTestCase'
        self.elements = [
            e for e in self.elements
            if not (
                e[0] == tc_tag
                and e[1].get('{' + rdf_ns + '}resource') == target
            )
        ]

        return len(self.test_cases) < initial_len

    # -------------------------------------------------------------------------
    # RDF/XML parsing
    # -------------------------------------------------------------------------

    @staticmethod
    def from_etree(etree: ET._ElementTree) -> 'TestPlan':
        root = etree.getroot()
        namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        ns = namespaces.copy()

        rdf_about = f'{{{ns["rdf"]}}}about'

        # Find all rdf:Description elements with rdf:about
        about_elements = root.findall(".//rdf:Description[@rdf:about]", ns)

        # Identify the main test plan element:
        # - 'VersionedTestPlan' must be in the URI
        # - no '#' in the URI (excludes sub-resources like #ApplicationSecurity)
        # - the part after 'VersionedTestPlan/' has no further '/' (excludes
        #   version sub-resources like .../VersionedTestPlan/_id1/_id2)
        main_elem = None
        for elem in about_elements:
            uri = elem.attrib.get(rdf_about)
            if uri and 'VersionedTestPlan' in uri and '#' not in uri:
                after = uri.split('VersionedTestPlan/')[1]
                if '/' not in after:
                    main_elem = elem
                    break

        if main_elem is None:
            raise ValueError("No main rdf:Description for a TestPlan (VersionedTestPlan without '#') found")

        uri = main_elem.attrib[rdf_about]
        testplan = TestPlan(uri=uri, namespaces=namespaces)

        rdf_resource_attr = f'{{{ns["rdf"]}}}resource'

        for elem in main_elem:
            tag = elem.tag
            text = elem.text.strip() if elem.text else ""
            attrib = dict(elem.attrib)
            short_tag = ET.QName(tag).localname
            testplan.elements.append((tag, attrib, text))

            if short_tag == 'title' and tag.startswith('{http://purl.org/dc/terms/}'):
                testplan.title = text
            elif short_tag == 'description':
                testplan.description = text
            elif short_tag == 'identifier':
                testplan.identifier = text
            elif short_tag == 'created':
                testplan.created = text
            elif short_tag == 'modified':
                testplan.modified = text
            elif short_tag == 'creator':
                testplan.creator = attrib.get(rdf_resource_attr)
            elif short_tag == 'contributor':
                testplan.contributor = attrib.get(rdf_resource_attr)
            elif short_tag == 'type' and rdf_resource_attr in attrib:
                testplan.type = attrib[rdf_resource_attr]
            elif short_tag == 'relation':
                testplan.relation = attrib.get(rdf_resource_attr)
            elif short_tag == 'shortId':
                testplan.short_id = text
            elif short_tag == 'shortIdentifier':
                testplan.short_identifier = text
            elif short_tag == 'isLocked':
                testplan.is_locked = text
            elif short_tag == 'usesTestCase':
                tc_uri = attrib.get(rdf_resource_attr)
                if tc_uri and tc_uri not in testplan.test_cases:
                    testplan.test_cases.append(tc_uri)

        # Parse reified rdf:Statements (used for validatesRequirementCollection)
        for stmt in root.findall('.//rdf:Description[@rdf:nodeID]', ns):
            node_id = stmt.attrib.get(f'{{{ns["rdf"]}}}nodeID')
            subject_elem = stmt.find('rdf:subject', ns)
            predicate_elem = stmt.find('rdf:predicate', ns)
            object_elem = stmt.find('rdf:object', ns)
            title_elem = stmt.find('dcterms:title', ns)

            if subject_elem is not None and predicate_elem is not None and object_elem is not None:
                testplan.links.append(TestPlanLink(
                    node_id=node_id,
                    subject=subject_elem.attrib.get(rdf_resource_attr),
                    predicate=predicate_elem.attrib.get(rdf_resource_attr),
                    target=object_elem.attrib.get(rdf_resource_attr),
                    title=title_elem.text if title_elem is not None else None
                ))

        # Collect all other rdf:Description blocks with rdf:about (not the main one)
        for desc in root.findall(".//rdf:Description[@rdf:about]", ns):
            about = desc.attrib.get(rdf_about)
            if about == testplan.uri:
                continue
            elems = []
            for elem in desc:
                tag = elem.tag
                text = elem.text.strip() if elem.text else ""
                attrib = dict(elem.attrib)
                elems.append((tag, attrib, text))
            testplan.extra_descriptions[about] = elems

        return testplan

    # -------------------------------------------------------------------------
    # RDF/XML serialisation
    # -------------------------------------------------------------------------

    def to_etree(self) -> ET._ElementTree:
        NSMAP = self.namespaces or {'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
        rdf = ET.Element(ET.QName(NSMAP['rdf'], 'RDF'), nsmap=NSMAP)

        if self.uri != "":
            desc = ET.SubElement(rdf, ET.QName(NSMAP['rdf'], 'Description'), {
                ET.QName(NSMAP['rdf'], 'about'): self.uri
            })
        else:
            desc = ET.SubElement(rdf, ET.QName(NSMAP['rdf'], 'Description'))

        def add(tag_ns: str, tag: str, text=None, attrib=None):
            el = ET.SubElement(desc, ET.QName(NSMAP[tag_ns], tag), attrib or {})
            if text:
                el.text = text

        if self.title is not None:
            add('dcterms', 'title', self.title,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.identifier is not None:
            add('dcterms', 'identifier', self.identifier,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.description is not None:
            add('dcterms', 'description', self.description,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.created is not None:
            add('dcterms', 'created', self.created,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.modified is not None:
            add('dcterms', 'modified', self.modified,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.creator:
            add('dcterms', 'creator', None, {f'{{{NSMAP["rdf"]}}}resource': self.creator})
        if self.contributor:
            add('dcterms', 'contributor', None, {f'{{{NSMAP["rdf"]}}}resource': self.contributor})
        if self.type:
            add('rdf', 'type', None, {f'{{{NSMAP["rdf"]}}}resource': self.type})
        if self.relation:
            add('dcterms', 'relation', None, {f'{{{NSMAP["rdf"]}}}resource': self.relation})
        if self.short_id:
            add('oslc', 'shortId', self.short_id,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.short_identifier:
            add('rqm_qm', 'shortIdentifier', self.short_identifier,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.is_locked:
            add('rqm_qm', 'isLocked', self.is_locked,
                {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#boolean'})

        # Known scalar tags — skip these when replaying the raw elements list
        known_tags = {
            'title', 'description', 'identifier', 'created', 'modified',
            'creator', 'contributor', 'type', 'relation', 'shortId',
            'shortIdentifier', 'isLocked',
            # usesTestCase and validatesRequirementCollection are handled below
            'usesTestCase', 'validatesRequirementCollection',
        }

        # Replay unknown / pass-through elements (categories, priority, state, etc.)
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

        # Emit oslc_qm:usesTestCase — one element per test case URI
        oslc_qm_ns = NSMAP.get('oslc_qm', 'http://open-services.net/ns/qm#')
        rdf_ns = NSMAP.get('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        for tc_uri in self.test_cases:
            ET.SubElement(desc, ET.QName(oslc_qm_ns, 'usesTestCase'), {
                ET.QName(rdf_ns, 'resource'): tc_uri
            })

        # Emit oslc_qm:validatesRequirementCollection direct property elements
        # (the reified statements that reference these are emitted separately below)
        for link in self.links:
            if link.predicate == "http://open-services.net/ns/qm#validatesRequirementCollection":
                ET.SubElement(desc, ET.QName(oslc_qm_ns, 'validatesRequirementCollection'), {
                    ET.QName(rdf_ns, 'resource'): link.target
                })

        # Emit reified rdf:Statement blocks for each link
        for link in self.links:
            attribs = {}
            if link.node_id:
                attribs[ET.QName(rdf_ns, 'nodeID')] = link.node_id
            stmt = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'), attribs)
            ET.SubElement(stmt, ET.QName(rdf_ns, 'subject'), {
                ET.QName(rdf_ns, 'resource'): link.subject or self.uri
            })
            ET.SubElement(stmt, ET.QName(rdf_ns, 'predicate'), {
                ET.QName(rdf_ns, 'resource'): link.predicate
            })
            ET.SubElement(stmt, ET.QName(rdf_ns, 'object'), {
                ET.QName(rdf_ns, 'resource'): link.target
            })
            ET.SubElement(stmt, ET.QName(rdf_ns, 'type'), {
                ET.QName(rdf_ns, 'resource'): rdf_ns + 'Statement'
            })
            if link.title:
                ET.SubElement(stmt, ET.QName(NSMAP['dcterms'], 'title')).text = link.title

        # Emit extra_descriptions (sub-resources, version resource, etc.)
        for about, elems in self.extra_descriptions.items():
            extra_desc = ET.SubElement(rdf, ET.QName(rdf_ns, 'Description'), {
                ET.QName(rdf_ns, 'about'): about
            })
            for tag, attrib, text in elems:
                el = ET.SubElement(extra_desc, ET.QName(tag), attrib)
                if text:
                    el.text = text

        return ET.ElementTree(rdf)

    def is_xml_equal(self, other: 'TestPlan') -> bool:
        def clean(xml: ET._ElementTree) -> bytes:
            return ET.tostring(xml.getroot(), encoding='utf-8', method='c14n')

        return clean(self.to_etree()) == clean(other.to_etree())
