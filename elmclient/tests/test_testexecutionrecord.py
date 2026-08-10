"""Round-trip and create_minimal tests for TestExecutionRecord."""
import lxml.etree as ET
from elmclient.testexecutionrecord import TestExecutionRecord

REAL_TER_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF
    xmlns:rqm_auto="http://jazz.net/ns/auto/rqm#"
    xmlns:acp="http://jazz.net/ns/acp#"
    xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/"
    xmlns:acc="http://open-services.net/ns/core/acc#"
    xmlns:process="http://jazz.net/ns/process#"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:skos="http://www.w3.org/2004/02/skos/core#"
    xmlns:jrs="http://jazz.net/ns/jrs#"
    xmlns:oslc_auto="http://open-services.net/ns/auto#"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:bp="http://open-services.net/ns/basicProfile#"
    xmlns:cmx="http://open-services.net/ns/cm-x#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:rqm_lm="http://jazz.net/ns/qm/rqm/labmanagement#"
    xmlns:oslc="http://open-services.net/ns/core#"
    xmlns:owl="http://www.w3.org/2002/07/owl#"
    xmlns:rqm_process="http://jazz.net/xmlns/prod/jazz/rqm/process/1.0/"
    xmlns:jazz="http://jazz.net/ns/jazz#"
    xmlns:oslc_config="http://open-services.net/ns/config#"
    xmlns:oslc_cm="http://open-services.net/ns/cm#"
    xmlns:rqm_qm="http://jazz.net/ns/qm/rqm#"
    xmlns:oslc_qm="http://open-services.net/ns/qm#"
    xmlns:oslc_rm="http://open-services.net/ns/rm#"
    xmlns:foaf="http://xmlns.com/foaf/0.1/" >
<rdf:Description rdf:about="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.TestcaseExecutionRecord/_QyOGYKUlEfC---XKwFe08Q">
<oslc_qm:runsTestCase rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.planning.VersionedTestCase/_K1zLQ6UlEfC---XKwFe08Q"/>
<oslc_qm:executesTestScript rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.planning.VersionedExecutionScript/_I24AcaUlEfC---XKwFe08Q"/>
<rqm_qm:producesTestResult rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.ExecutionResult/_USaPqKUlEfC---XKwFe08Q"/>
<rqm_qm:currentTestResult rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.ExecutionResult/_USaPqKUlEfC---XKwFe08Q"/>
<rqm_qm:isSuspectResult rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">false</rqm_qm:isSuspectResult>
<rqm_process:hasPriority rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/process-info/_Q5AVwqUjEfC---XKwFe08Q/priority/literal.priority.110"/>
<dcterms:relation rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/resources/_Q5AVwqUjEfC---XKwFe08Q/executionworkitem/urn:com.ibm.rqm:executionworkitem:41"/>
<rqm_qm:lastPassedTestResult rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.ExecutionResult/_USaPqKUlEfC---XKwFe08Q"/>
<dcterms:description rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
</dcterms:description>
<process:projectArea rdf:resource="https://jazz.ibm.com:9443/qm/process/project-areas/_Q5AVwqUjEfC---XKwFe08Q"/>
<dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2025-10-09T15:33:38.982Z</dcterms:modified>
<oslc_config:component rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/resources/com.ibm.team.vvc.Component/_Rh7W96UjEfC---XKwFe08Q"/>
<oslc_qm:runsOnTestEnvironment rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rational.test.lm.AssetConfiguration/_OteAYqUlEfC---XKwFe08Q"/>
<rdf:type rdf:resource="http://open-services.net/ns/qm#TestExecutionRecord"/>
<dcterms:contributor rdf:resource="https://jazz.ibm.com:9443/jts/users/tammy"/>
<oslc:shortId rdf:datatype="http://www.w3.org/2001/XMLSchema#int">41</oslc:shortId>
<acp:accessControl rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/accessControl/_Q5AVwqUjEfC---XKwFe08Q"/>
<rqm_qm:shortIdentifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">41</rqm_qm:shortIdentifier>
<oslc:serviceProvider rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/services.xml"/>
<rqm_qm:estimate rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">18000000</rqm_qm:estimate>
<oslc:instanceShape rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/shape/resource/com.ibm.rqm.execution.TestcaseExecutionRecord"/>
<rqm_qm:testSchedule rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.process.TestPhase/_Nkwr4aUlEfC---XKwFe08Q"/>
<dcterms:creator rdf:resource="https://jazz.ibm.com:9443/jts/users/tammy"/>
<dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2025-10-09T15:33:10.726Z</dcterms:created>
<acc:accessContext rdf:resource="https://jazz.ibm.com:9443/qm/acclist#_Q5AVwqUjEfC---XKwFe08Q"/>
<rqm_qm:timeSpent rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">10800000</rqm_qm:timeSpent>
<rqm_qm:weight rdf:datatype="http://www.w3.org/2001/XMLSchema#int">100</rqm_qm:weight>
<dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Process_email_requests_Firefox_DB2_WAS_Windows_S1</dcterms:title>
<oslc_qm:reportsOnTestPlan rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.planning.VersionedTestPlan/_MZucIaUlEfC---XKwFe08Q"/>
<dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">_QyOGYKUlEfC---XKwFe08Q</dcterms:identifier>
</rdf:Description>
<rdf:Description rdf:about="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.TestcaseExecutionRecord/_QyOGYKUlEfC---XKwFe08Q/_UTGzMKUlEfC---XKwFe08Q">
<acc:accessContext rdf:resource="https://jazz.ibm.com:9443/qm/acclist#_Q5AVwqUjEfC---XKwFe08Q"/>
<dcterms:isVersionOf rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.TestcaseExecutionRecord/_QyOGYKUlEfC---XKwFe08Q"/>
<rdf:type rdf:resource="http://open-services.net/ns/config#VersionResource"/>
</rdf:Description>
</rdf:RDF>"""


def _parse():
    return TestExecutionRecord.from_etree(ET.ElementTree(ET.fromstring(REAL_TER_XML)))


def test_all_scalar_fields_decoded():
    ter = _parse()
    assert ter.title == 'Process_email_requests_Firefox_DB2_WAS_Windows_S1'
    assert ter.identifier == '_QyOGYKUlEfC---XKwFe08Q'
    assert ter.short_id == '41'
    assert ter.short_identifier == '41'
    assert ter.modified == '2025-10-09T15:33:38.982Z'
    assert ter.created == '2025-10-09T15:33:10.726Z'
    assert ter.creator == 'https://jazz.ibm.com:9443/jts/users/tammy'
    assert ter.contributor == 'https://jazz.ibm.com:9443/jts/users/tammy'
    assert ter.type == 'http://open-services.net/ns/qm#TestExecutionRecord'
    assert ter.weight == '100'
    assert ter.estimate == '18000000'
    assert ter.time_spent == '10800000'
    assert ter.is_suspect_result == 'false'


def test_all_reference_fields_decoded():
    ter = _parse()
    assert 'VersionedTestCase' in ter.runs_test_case
    assert 'VersionedExecutionScript' in ter.executes_test_script
    assert 'AssetConfiguration' in ter.runs_on_test_environment
    assert 'VersionedTestPlan' in ter.reports_on_test_plan
    # produces_test_results is now a list (one TCER -> many Test Results)
    assert isinstance(ter.produces_test_results, list)
    assert len(ter.produces_test_results) == 1
    assert 'ExecutionResult' in ter.produces_test_results[0]
    assert 'ExecutionResult' in ter.current_test_result
    assert 'ExecutionResult' in ter.last_passed_test_result
    assert 'TestPhase' in ter.test_schedule


def test_version_resource_in_extra_descriptions():
    ter = _parse()
    assert len(ter.extra_descriptions) == 1
    ver_key = list(ter.extra_descriptions.keys())[0]
    assert '_UTGzMKUlEfC' in ver_key


def test_to_etree_contains_all_known_properties():
    ter = _parse()
    out_xml = ET.tostring(ter.to_etree().getroot(), pretty_print=True).decode()
    for tag in ('runsTestCase', 'executesTestScript', 'runsOnTestEnvironment',
                'reportsOnTestPlan', 'producesTestResult', 'isSuspectResult',
                'estimate', 'timeSpent', 'weight', 'shortIdentifier', 'VersionResource'):
        assert tag in out_xml, f"Missing tag in serialised output: {tag}"


def test_produces_test_results_is_list_and_round_trips():
    ter = _parse()
    # Add a second result URL and verify both round-trip
    second_url = 'https://example.com/qm/resources/com.ibm.rqm.execution.ExecutionResult/_second'
    ter.produces_test_results.append(second_url)
    out_xml = ET.tostring(ter.to_etree().getroot()).decode()
    assert out_xml.count('producesTestResult') == 2  # one self-closing element per URL
    assert second_url in out_xml


def test_create_minimal():
    tc_uri = 'https://example.com/qm/resources/com.ibm.rqm.planning.VersionedTestCase/_abc'
    ter = TestExecutionRecord.create_minimal('My TER', tc_uri)
    assert ter.title == 'My TER'
    assert ter.runs_test_case == tc_uri
    assert ter.type == 'http://open-services.net/ns/qm#TestExecutionRecord'
    # Must be serialisable
    out = ET.tostring(ter.to_etree().getroot()).decode()
    assert 'runsTestCase' in out
    assert 'My TER' in out


def test_setter_no_duplicate_elements():
    ter = _parse()
    new_tc = 'https://example.com/newtc'
    ter.set_runs_test_case(new_tc)
    rc_tags = [e for e in ter.elements if ET.QName(e[0]).localname == 'runsTestCase']
    assert len(rc_tags) == 1
    assert ter.runs_test_case == new_tc


def test_setter_executes_test_script():
    ter = _parse()
    new_ts = 'https://example.com/newscript'
    ter.set_executes_test_script(new_ts)
    assert ter.executes_test_script == new_ts
    ts_tags = [e for e in ter.elements if ET.QName(e[0]).localname == 'executesTestScript']
    assert len(ts_tags) == 1


if __name__ == '__main__':
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f'  PASS  {fn.__name__}')
        except Exception as exc:
            print(f'  FAIL  {fn.__name__}: {exc}')
            failed += 1
    sys.exit(failed)
