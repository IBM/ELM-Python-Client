from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import lxml.etree as ET

@dataclass
class TestCaseLink:
    node_id: Optional[str] = None
    subject: Optional[str] = None
    predicate: str = ""
    target: str = ""
    title: Optional[str] = None

@dataclass
class TestCase:
    @classmethod
    def create_minimal(cls, title: str) -> 'TestCase':
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

        tc = cls(
            uri="",
            title=title,
            type="http://open-services.net/ns/qm#TestCase",
            namespaces=namespaces
        )

        tc.elements.append((
            '{http://purl.org/dc/terms/}title',
            {'{http://www.w3.org/2001/XMLSchema#}datatype': 'http://www.w3.org/2001/XMLSchema#string'},
            title
        ))
        tc.elements.append((
            '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}type',
            {'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource': 'http://open-services.net/ns/qm#TestCase'},
            None
        ))

        return tc
    
    uri: str=""
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
    script_step_count: Optional[str] = None
    weight: Optional[str] = None
    is_locked: Optional[str] = None
    links: List[TestCaseLink] = field(default_factory=list)
    namespaces: Dict[str, str] = field(default_factory=dict)
    elements: List[Tuple[str, Dict[str, str], Optional[str]]] = field(default_factory=list)
    extra_descriptions: Dict[str, List[Tuple[str, Dict[str, str], Optional[str]]]] = field(default_factory=dict)

    def add_link(self, predicate: str, target: str, title: Optional[str] = None):
        self.links.append(TestCaseLink(predicate=predicate, target=target, title=title))

    def add_validatesRequirementLink(self, target: str, title: Optional[str] = None):
        self.links.append(TestCaseLink(
            subject=self.uri,
            predicate="http://open-services.net/ns/qm#validatesRequirement",
            target=target,
            title=title
        ))
        tag = '{' + self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#') + '}validatesRequirement'
        attrib = {'{' + self.namespaces['rdf'] + '}resource': target}
        self.elements.append((tag, attrib, None))

    def delete_link(self, target: str) -> bool:
        initial_length = len(self.links)
        self.links = [link for link in self.links if link.target != target]
        return len(self.links) < initial_length

    def delete_validatesRequirementLink(self, target: str) -> bool:
        initial_links = len(self.links)
        self.links = [link for link in self.links if not (
            link.predicate == "http://open-services.net/ns/qm#validatesRequirement" and link.target == target)
        ]

        uri = self.namespaces.get('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        oslc_qm_ns = self.namespaces.get('oslc_qm', 'http://open-services.net/ns/qm#')
        validate_tag = '{' + oslc_qm_ns + '}validatesRequirement'
        self.elements = [e for e in self.elements if not (
            e[0] == validate_tag and e[1].get('{' + uri + '}resource') == target)
        ]

        return len(self.links) < initial_links

    @staticmethod
    def from_etree(etree: ET._ElementTree) -> 'TestCase':
        root = etree.getroot()
        namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        ns = namespaces.copy()

        # Find all rdf:Description elements with rdf:about
        about_elements = root.findall(".//rdf:Description[@rdf:about]", ns)

        # Identify the main test case element (without '#' in rdf:about)
        main_elem = None
        for elem in about_elements:
            uri = elem.attrib.get(f'{{{ns["rdf"]}}}about')
            #print(uri)
            if uri and 'TestCase' in uri and '#' not in uri:
                main_elem = elem
                break

        if main_elem is None:
            raise ValueError("No main rdf:Description with rdf:about (without '#') found")

        uri = main_elem.attrib[f'{{{ns["rdf"]}}}about']
        testcase = TestCase(uri=uri, namespaces=namespaces)

    
    
    # def from_etree(etree: ET._ElementTree) -> 'TestCase':
        # root = etree.getroot()
        # namespaces = {k if k is not None else '': v for k, v in root.nsmap.items()}
        # ns = namespaces.copy()

        # main_elem = root.find(".//rdf:Description[@rdf:about]", ns)
        # if main_elem is None:
            # raise ValueError("No rdf:Description with rdf:about found")

        # uri = main_elem.attrib[f'{{{ns["rdf"]}}}about']
        # testcase = TestCase(uri=uri, namespaces=namespaces)

        for elem in main_elem:
            tag = elem.tag
            text = elem.text.strip() if elem.text else ""
            attrib = dict(elem.attrib)
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
                testcase.creator = attrib.get(f'{{{ns["rdf"]}}}resource')
            elif short_tag == 'contributor':
                testcase.contributor = attrib.get(f'{{{ns["rdf"]}}}resource')
            elif short_tag == 'type' and f'{{{ns["rdf"]}}}resource' in attrib:
                testcase.type = attrib[f'{{{ns["rdf"]}}}resource']
            elif short_tag == 'relation':
                testcase.relation = attrib.get(f'{{{ns["rdf"]}}}resource')
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

        for stmt in root.findall('.//rdf:Description[@rdf:nodeID]', ns):
            node_id = stmt.attrib.get(f'{{{ns["rdf"]}}}nodeID')
            subject_elem = stmt.find('rdf:subject', ns)
            predicate_elem = stmt.find('rdf:predicate', ns)
            object_elem = stmt.find('rdf:object', ns)
            title_elem = stmt.find('dcterms:title', ns)

            if subject_elem is not None and predicate_elem is not None and object_elem is not None:
                testcase.links.append(TestCaseLink(
                    node_id=node_id,
                    subject=subject_elem.attrib.get(f'{{{ns["rdf"]}}}resource'),
                    predicate=predicate_elem.attrib.get(f'{{{ns["rdf"]}}}resource'),
                    target=object_elem.attrib.get(f'{{{ns["rdf"]}}}resource'),
                    title=title_elem.text if title_elem is not None else None
                ))

        for desc in root.findall(".//rdf:Description[@rdf:about]", ns):
            about = desc.attrib.get(f'{{{ns["rdf"]}}}about')
            if about == testcase.uri:
                continue
            elems = []
            for elem in desc:
                tag = elem.tag
                text = elem.text.strip() if elem.text else ""
                attrib = dict(elem.attrib)
                elems.append((tag, attrib, text))
            testcase.extra_descriptions[about] = elems

        return testcase

    def to_etree(self) -> ET._ElementTree:
        NSMAP = self.namespaces or {'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
        rdf = ET.Element(ET.QName(NSMAP['rdf'], 'RDF'), nsmap=NSMAP)
        if self.uri!="":
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
            add('dcterms', 'title', self.title, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.identifier is not None:
            add('dcterms', 'identifier', self.identifier, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.description is not None:
            add('dcterms', 'description', self.description, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.created is not None:
            add('dcterms', 'created', self.created, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.modified is not None:
            add('dcterms', 'modified', self.modified, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#dateTime'})
        if self.creator:
            add('dcterms', 'creator', None, {f'{{{NSMAP["rdf"]}}}resource': self.creator})
        if self.contributor:
            add('dcterms', 'contributor', None, {f'{{{NSMAP["rdf"]}}}resource': self.contributor})
        if self.type:
            add('rdf', 'type', None, {f'{{{NSMAP["rdf"]}}}resource': self.type})
        if self.relation:
            add('dcterms', 'relation', None, {f'{{{NSMAP["rdf"]}}}resource': self.relation})
        if self.short_id:
            add('oslc', 'shortId', self.short_id, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.short_identifier:
            add('rqm_qm', 'shortIdentifier', self.short_identifier, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#string'})
        if self.script_step_count:
            add('rqm_qm', 'scriptStepCount', self.script_step_count, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#long'})
        if self.weight:
            add('rqm_qm', 'weight', self.weight, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#int'})
        if self.is_locked:
            add('rqm_qm', 'isLocked', self.is_locked, {f'{{{NSMAP["rdf"]}}}datatype': 'http://www.w3.org/2001/XMLSchema#boolean'})

        known_tags = {
            'title', 'description', 'identifier', 'created', 'modified', 'creator', 'contributor',
            'type', 'relation', 'shortId', 'shortIdentifier', 'scriptStepCount', 'weight', 'isLocked'
        }

        for tag, attrib, text in self.elements:
            short_tag = ET.QName(tag).localname
            if short_tag in known_tags:
                continue
            el = ET.SubElement(desc, ET.QName(tag), {
                ET.QName(k) if isinstance(k, str) and ':' in k else k: v for k, v in attrib.items()
            })
            if text:
                el.text = text

        for i, link in enumerate(self.links):
            attribs = {}
            if link.node_id:
                attribs[ET.QName(NSMAP['rdf'], 'nodeID')] = link.node_id
            stmt = ET.SubElement(rdf, ET.QName(NSMAP['rdf'], 'Description'), attribs)
            ET.SubElement(stmt, ET.QName(NSMAP['rdf'], 'subject'), {
                ET.QName(NSMAP['rdf'], 'resource'): link.subject or self.uri
            })
            ET.SubElement(stmt, ET.QName(NSMAP['rdf'], 'predicate'), {
                ET.QName(NSMAP['rdf'], 'resource'): link.predicate
            })
            ET.SubElement(stmt, ET.QName(NSMAP['rdf'], 'object'), {
                ET.QName(NSMAP['rdf'], 'resource'): link.target
            })
            ET.SubElement(stmt, ET.QName(NSMAP['rdf'], 'type'), {
                ET.QName(NSMAP['rdf'], 'resource'): NSMAP['rdf'] + 'Statement'
            })
            if link.title:
                ET.SubElement(stmt, ET.QName(NSMAP['dcterms'], 'title')).text = link.title

        for about, elems in self.extra_descriptions.items():
            desc = ET.SubElement(rdf, ET.QName(NSMAP['rdf'], 'Description'), {
                ET.QName(NSMAP['rdf'], 'about'): about
            })
            for tag, attrib, text in elems:
                el = ET.SubElement(desc, ET.QName(tag), attrib)
                if text:
                    el.text = text

        return ET.ElementTree(rdf)

    def is_xml_equal(self, other: 'TestCase') -> bool:
        def clean(xml: ET._ElementTree) -> bytes:
            return ET.tostring(xml.getroot(), encoding='utf-8', method='c14n')

        return clean(self.to_etree()) == clean(other.to_etree())
