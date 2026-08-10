"""Round-trip and create_minimal tests for TestResult."""
import lxml.etree as ET
from elmclient.testresult import TestResult

REAL_TR_XML = b"""\
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
<rdf:Description rdf:about="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.ExecutionResult/_USaPqKUlEfC---XKwFe08Q/_UTaVMKUlEfC---XKwFe08Q">
<acc:accessContext rdf:resource="https://jazz.ibm.com:9443/qm/acclist#_Q5AVwqUjEfC---XKwFe08Q"/>
<dcterms:isVersionOf rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.ExecutionResult/_USaPqKUlEfC---XKwFe08Q"/>
<rdf:type rdf:resource="http://open-services.net/ns/config#VersionResource"/>
</rdf:Description>
<rdf:Description rdf:about="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.ExecutionResult/_USaPqKUlEfC---XKwFe08Q">
<rqm_qm:pointsAttempted rdf:datatype="http://www.w3.org/2001/XMLSchema#long">100</rqm_qm:pointsAttempted>
<rqm_qm:testedBy rdf:resource="https://jazz.ibm.com:9443/jts/users/ibm"/>
<dcterms:creator rdf:resource="https://jazz.ibm.com:9443/jts/users/tammy"/>
<oslc_qm:producedByTestExecutionRecord rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.TestcaseExecutionRecord/_QyOGYKUlEfC---XKwFe08Q"/>
<rqm_qm:pointsDeferred rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:pointsDeferred>
<oslc:shortId rdf:datatype="http://www.w3.org/2001/XMLSchema#int">41</oslc:shortId>
<rqm_qm:scriptStepCountSkipped rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:scriptStepCountSkipped>
<acc:accessContext rdf:resource="https://jazz.ibm.com:9443/qm/acclist#_Q5AVwqUjEfC---XKwFe08Q"/>
<rqm_qm:scriptStepCount rdf:datatype="http://www.w3.org/2001/XMLSchema#long">1</rqm_qm:scriptStepCount>
<dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2025-10-09T15:33:34.234Z</dcterms:created>
<rqm_qm:stepResultsUpdateStatus rdf:resource="http://jazz.net/ns/qm/rqm#NOMODIFICATION"/>
<rqm_qm:scriptStepCountBlocked rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:scriptStepCountBlocked>
<rqm_qm:testSchedule rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.process.TestPhase/_Nkwr4aUlEfC---XKwFe08Q"/>
<dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">_USaPqKUlEfC---XKwFe08Q</dcterms:identifier>
<rqm_qm:pointsFailed rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:pointsFailed>
<rqm_qm:verdict rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/shape/resource/com.ibm.rqm.execution.ExecutionResult#com.ibm.rqm.execution.common.state.passed"/>
<rqm_qm:startTime rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2025-10-09T15:33:34.234Z</rqm_qm:startTime>
<dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Process_email_requests_Firefox_DB2_WAS_Windows_S1</dcterms:title>
<dcterms:contributor rdf:resource="https://jazz.ibm.com:9443/jts/users/tammy"/>
<rqm_qm:isRollup rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">false</rqm_qm:isRollup>
<rqm_qm:weight rdf:datatype="http://www.w3.org/2001/XMLSchema#long">100</rqm_qm:weight>
<process:projectArea rdf:resource="https://jazz.ibm.com:9443/qm/process/project-areas/_Q5AVwqUjEfC---XKwFe08Q"/>
<oslc_qm:reportsOnTestPlan rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.planning.VersionedTestPlan/_MZucIaUlEfC---XKwFe08Q"/>
<oslc_qm:status rdf:datatype="http://www.w3.org/2001/XMLSchema#string">com.ibm.rqm.execution.common.state.passed</oslc_qm:status>
<rqm_qm:pointsBlocked rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:pointsBlocked>
<oslc_config:component rdf:resource="https://jazz.ibm.com:9443/qm/oslc_config/resources/com.ibm.team.vvc.Component/_Rh7W96UjEfC---XKwFe08Q"/>
<acp:accessControl rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/accessControl/_Q5AVwqUjEfC---XKwFe08Q"/>
<rqm_qm:endTime rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2025-10-09T15:34:08.323Z</rqm_qm:endTime>
<oslc_qm:reportsOnTestCase rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.planning.VersionedTestCase/_K1zLQ6UlEfC---XKwFe08Q"/>
<rqm_qm:pointsSkipped rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:pointsSkipped>
<oslc:serviceProvider rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/services.xml"/>
<rqm_qm:scriptStepCountAttempted rdf:datatype="http://www.w3.org/2001/XMLSchema#long">1</rqm_qm:scriptStepCountAttempted>
<rqm_qm:isCurrentForBuild rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">false</rqm_qm:isCurrentForBuild>
<rqm_qm:totalPoints rdf:datatype="http://www.w3.org/2001/XMLSchema#long">100</rqm_qm:totalPoints>
<rqm_qm:pointsPassed rdf:datatype="http://www.w3.org/2001/XMLSchema#long">100</rqm_qm:pointsPassed>
<rqm_qm:containsStepResult rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.execution.ExecutionElementResult/_UStKkaUlEfC---XKwFe08Q"/>
<oslc_qm:runsOnTestEnvironment rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rational.test.lm.AssetConfiguration/_OteAYqUlEfC---XKwFe08Q"/>
<rqm_qm:scriptStepCountDeferred rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:scriptStepCountDeferred>
<oslc_qm:executesTestScript rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/resources/com.ibm.rqm.planning.VersionedExecutionScript/_I24AcaUlEfC---XKwFe08Q"/>
<rqm_process:hasWorkflowState rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/process-info/_Q5AVwqUjEfC---XKwFe08Q/workflowstate/com.ibm.rqm.process.testcaseresult.workflow/com.ibm.rqm.planning.common.new"/>
<oslc:instanceShape rdf:resource="https://jazz.ibm.com:9443/qm/oslc_qm/contexts/_Q5AVwqUjEfC---XKwFe08Q/shape/resource/com.ibm.rqm.execution.ExecutionResult"/>
<rqm_qm:pointsPermFailed rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:pointsPermFailed>
<rqm_qm:pointsInconclusive rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:pointsInconclusive>
<rqm_qm:shortIdentifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">41</rqm_qm:shortIdentifier>
<rqm_qm:isLocked rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">false</rqm_qm:isLocked>
<rqm_qm:scriptStepCountPassed rdf:datatype="http://www.w3.org/2001/XMLSchema#long">1</rqm_qm:scriptStepCountPassed>
<rqm_qm:scriptStepCountFailed rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:scriptStepCountFailed>
<rqm_qm:isCurrent rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</rqm_qm:isCurrent>
<rqm_qm:scriptStepCountPermFailed rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:scriptStepCountPermFailed>
<rqm_process:testcaseWorkflowState rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/process-info/_Q5AVwqUjEfC---XKwFe08Q/workflowstate/com.ibm.rqm.process.testcase.workflow/com.ibm.rqm.planning.common.approved"/>
<rqm_qm:totalRunTime rdf:datatype="http://www.w3.org/2001/XMLSchema#long">34089</rqm_qm:totalRunTime>
<dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2025-10-09T15:33:38.982Z</dcterms:modified>
<rqm_qm:scriptStepCountInconclusive rdf:datatype="http://www.w3.org/2001/XMLSchema#long">0</rqm_qm:scriptStepCountInconclusive>
<rdf:type rdf:resource="http://open-services.net/ns/qm#TestResult"/>
<rqm_qm:numberOfIterations rdf:datatype="http://www.w3.org/2001/XMLSchema#long">1</rqm_qm:numberOfIterations>
<rqm_process:testplanWorkflowState rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/process-info/_Q5AVwqUjEfC---XKwFe08Q/workflowstate/com.ibm.rqm.process.testplan.workflow/com.ibm.rqm.planning.common.new"/>
<rqm_process:testscriptWorkflowState rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/process-info/_Q5AVwqUjEfC---XKwFe08Q/workflowstate/com.ibm.rqm.process.testscript.workflow/com.ibm.rqm.planning.common.approved"/>
<dcterms:relation rdf:resource="https://jazz.ibm.com:9443/qm/service/com.ibm.rqm.integration.service.IIntegrationService/resources/_Q5AVwqUjEfC---XKwFe08Q/executionresult/urn:com.ibm.rqm:executionresult:41"/>
</rdf:Description>
</rdf:RDF>"""


def _parse() -> TestResult:
    return TestResult.from_etree(ET.ElementTree(ET.fromstring(REAL_TR_XML)))


def test_scalar_fields():
    tr = _parse()
    assert tr.title == 'Process_email_requests_Firefox_DB2_WAS_Windows_S1'
    assert tr.identifier == '_USaPqKUlEfC---XKwFe08Q'
    assert tr.short_id == '41'
    assert tr.short_identifier == '41'
    assert tr.created == '2025-10-09T15:33:34.234Z'
    assert tr.modified == '2025-10-09T15:33:38.982Z'
    assert tr.creator == 'https://jazz.ibm.com:9443/jts/users/tammy'
    assert tr.contributor == 'https://jazz.ibm.com:9443/jts/users/tammy'
    assert tr.type == 'http://open-services.net/ns/qm#TestResult'
    assert tr.status == 'com.ibm.rqm.execution.common.state.passed'
    assert tr.start_time == '2025-10-09T15:33:34.234Z'
    assert tr.end_time == '2025-10-09T15:34:08.323Z'
    assert tr.total_run_time == '34089'
    assert tr.is_rollup == 'false'
    assert tr.is_current == 'true'
    assert tr.is_current_for_build == 'false'
    assert tr.is_locked == 'false'
    assert tr.number_of_iterations == '1'
    assert tr.weight == '100'


def test_reference_fields():
    tr = _parse()
    assert 'TestcaseExecutionRecord' in tr.produced_by_tcer
    assert 'VersionedTestCase' in tr.reports_on_test_case
    assert 'VersionedTestPlan' in tr.reports_on_test_plan
    assert 'VersionedExecutionScript' in tr.executes_test_script
    assert 'AssetConfiguration' in tr.runs_on_test_environment
    assert 'ibm' in tr.tested_by
    assert 'TestPhase' in tr.test_schedule
    assert 'state.passed' in tr.verdict


def test_point_counters():
    tr = _parse()
    assert tr.points_attempted == '100'
    assert tr.points_passed == '100'
    assert tr.points_failed == '0'
    assert tr.points_blocked == '0'
    assert tr.points_skipped == '0'
    assert tr.points_deferred == '0'
    assert tr.points_perm_failed == '0'
    assert tr.points_inconclusive == '0'
    assert tr.total_points == '100'


def test_step_counters():
    tr = _parse()
    assert tr.script_step_count == '1'
    assert tr.script_step_count_attempted == '1'
    assert tr.script_step_count_passed == '1'
    assert tr.script_step_count_failed == '0'
    assert tr.script_step_count_blocked == '0'
    assert tr.script_step_count_skipped == '0'
    assert tr.script_step_count_deferred == '0'
    assert tr.script_step_count_perm_failed == '0'
    assert tr.script_step_count_inconclusive == '0'


def test_step_result_urls():
    tr = _parse()
    assert len(tr.step_result_urls) == 1
    assert 'ExecutionElementResult' in tr.step_result_urls[0]


def test_version_resource_in_extra_descriptions():
    tr = _parse()
    assert len(tr.extra_descriptions) == 1
    ver_key = list(tr.extra_descriptions.keys())[0]
    assert '_UTaVMKUlEfC' in ver_key


def test_to_etree_contains_key_tags():
    tr = _parse()
    out_xml = ET.tostring(tr.to_etree().getroot(), pretty_print=True).decode()
    for tag in ('producedByTestExecutionRecord', 'reportsOnTestCase', 'reportsOnTestPlan',
                'status', 'verdict', 'startTime', 'endTime', 'totalRunTime',
                'isRollup', 'isCurrent', 'isLocked', 'pointsPassed',
                'scriptStepCount', 'containsStepResult', 'VersionResource'):
        assert tag in out_xml, f"Missing in serialised output: {tag}"


def test_to_etree_no_duplicate_total_run_time():
    tr = _parse()
    out_xml = ET.tostring(tr.to_etree().getroot()).decode()
    assert out_xml.count('totalRunTime') == 2, \
        f"Expected exactly one open+close tag pair, got count={out_xml.count('totalRunTime')}"


def test_create_minimal():
    tcer_uri = 'https://example.com/qm/resources/com.ibm.rqm.execution.TestcaseExecutionRecord/_abc'
    tc_uri   = 'https://example.com/qm/resources/com.ibm.rqm.planning.VersionedTestCase/_def'
    tp_uri   = 'https://example.com/qm/resources/com.ibm.rqm.planning.VersionedTestPlan/_ghi'
    status   = 'com.ibm.rqm.execution.common.state.passed'

    tr = TestResult.create_minimal(tcer_uri, tc_uri, tp_uri, status)
    assert tr.title == status
    assert tr.status == status
    assert tr.produced_by_tcer == tcer_uri
    assert tr.reports_on_test_case == tc_uri
    assert tr.reports_on_test_plan == tp_uri
    assert tr.type == 'http://open-services.net/ns/qm#TestResult'

    out = ET.tostring(tr.to_etree().getroot()).decode()
    assert 'producedByTestExecutionRecord' in out
    assert 'reportsOnTestCase' in out
    assert 'reportsOnTestPlan' in out
    assert status in out


def test_create_minimal_custom_title():
    tr = TestResult.create_minimal(
        'https://example.com/tcer', 'https://example.com/tc',
        'https://example.com/tp', 'com.ibm.rqm.execution.common.state.failed',
        title='My custom result title',
    )
    assert tr.title == 'My custom result title'


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
