from types import SimpleNamespace

from vulnerabilities.base.security_agent_reviewer import _evidence_thread_id


def test_evidence_thread_id_changes_per_trace_sink():
    vulnerability = SimpleNamespace(vulnerability_id="sql_injection")
    first = SimpleNamespace(
        source_symbol="A.find:String(java.lang.String)",
        sink_file_path="A.java",
        sink_line_number=10,
    )
    second = SimpleNamespace(
        source_symbol="B.fetch:String(java.lang.String)",
        sink_file_path="B.java",
        sink_line_number=20,
    )

    assert _evidence_thread_id(vulnerability, first) != _evidence_thread_id(vulnerability, second)


def test_evidence_thread_id_is_stable_for_same_evidence():
    vulnerability = SimpleNamespace(vulnerability_id="sql_injection")
    evidence = SimpleNamespace(
        source_symbol="A.find:String(java.lang.String)",
        sink_file_path="A.java",
        sink_line_number=10,
    )

    assert _evidence_thread_id(vulnerability, evidence) == _evidence_thread_id(vulnerability, evidence)
