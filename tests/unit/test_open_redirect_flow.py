from types import SimpleNamespace

from models.sink import Sink
from models.source import Source
from models.trace import Trace
from vulnerabilities import open_redirect as open_redirect_mod
from vulnerabilities.open_redirect import (
    _flow_to_sink,
    _flow_key,
    _request_inputs,
    enrich_open_redirect_flows,
)


def test_request_inputs_extracts_spring_request_param():
    signature = (
        "public void redirect(@RequestParam String next, "
        "HttpServletResponse response)"
    )

    assert _request_inputs(signature, "") == {"next": "@RequestParam"}


def test_request_inputs_unions_configured_defaults(monkeypatch):
    monkeypatch.setattr(
        open_redirect_mod,
        "_open_redirect_args",
        lambda: {
            "request_accessors": ["param"],
            "request_annotations": ["CustomParam"],
        },
    )
    signature = (
        "public void redirect(@CustomParam String direct, "
        "HttpServletRequest request)"
    )
    body = 'String next = request.param("next");'

    inputs = _request_inputs(signature, body)

    assert inputs["direct"] == "@CustomParam"
    assert inputs["next"] == "request.param"


def test_flow_to_sink_marks_direct_request_param_redirect():
    body = """
    public void redirect(@RequestParam String next, HttpServletResponse response) {
        response.sendRedirect(next);
    }
    """
    metadata = _flow_to_sink(
        body,
        "public void redirect(@RequestParam String next, HttpServletResponse response)",
        "response.sendRedirect(next);",
        "next",
    )

    assert metadata["request_controlled"] is True
    assert metadata["source_param"] == "next"
    assert metadata["source_kind"] == "@RequestParam"
    assert metadata["sink_argument"] == "next"
    assert "@RequestParam next -> response.sendRedirect(next);" in metadata["flow_summary"]


def test_flow_to_sink_drops_constant_redirect_target():
    body = """
    public void redirect(@RequestParam String next, HttpServletResponse response) {
        response.sendRedirect("/home");
    }
    """
    metadata = _flow_to_sink(
        body,
        "public void redirect(@RequestParam String next, HttpServletResponse response)",
        'response.sendRedirect("/home");',
        '"/home"',
    )

    assert metadata["request_controlled"] is False
    assert metadata["flow_confidence"] == "not_request_controlled"


def test_flow_to_sink_follows_local_assignment():
    body = """
    public void redirect(@RequestParam String next, HttpServletResponse response) {
        String target = "/go?next=" + next;
        response.sendRedirect(target);
    }
    """
    metadata = _flow_to_sink(
        body,
        "public void redirect(@RequestParam String next, HttpServletResponse response)",
        "response.sendRedirect(target);",
        "target",
    )

    assert metadata["request_controlled"] is True
    assert metadata["flow_confidence"] == "local-derived"
    assert 'target = "/go?next=" + next' in metadata["flow_summary"]


def test_flow_to_sink_includes_validation_evidence():
    body = """
    public void redirect(@RequestParam String next, HttpServletResponse response) {
        if (!next.startsWith("/")) {
            throw new RuntimeException("blocked");
        }
        response.sendRedirect(next);
    }
    """
    metadata = _flow_to_sink(
        body,
        "public void redirect(@RequestParam String next, HttpServletResponse response)",
        "response.sendRedirect(next);",
        "next",
    )

    assert "startsWith" in metadata["validation_evidence"]


def test_validation_evidence_unions_configured_terms(monkeypatch):
    monkeypatch.setattr(
        open_redirect_mod,
        "_open_redirect_args",
        lambda: {"validation_terms": ["approvedRedirectTarget"]},
    )
    body = """
    public void redirect(@RequestParam String next, HttpServletResponse response) {
        if (!approvedRedirectTarget(next)) {
            throw new RuntimeException("blocked");
        }
        response.sendRedirect(next);
    }
    """
    metadata = _flow_to_sink(
        body,
        "public void redirect(@RequestParam String next, HttpServletResponse response)",
        "response.sendRedirect(next);",
        "next",
    )

    assert "approvedRedirectTarget" in metadata["validation_evidence"]


def _state_for_engine_flow():
    source = Source(
        symbol="com.example.RedirectController.redirect:void(java.lang.String)",
        file_path="Controller.java",
        line_number=1,
        code=(
            "public void redirect(@RequestParam String next, "
            "HttpServletResponse response)"
        ),
    )
    sink = Sink(
        rule_id="java-open-redirect-sinks-servlet",
        file_path="Controller.java",
        line_number=10,
        line_number_end=10,
        code="response.sendRedirect(next);",
    )
    trace = Trace(
        sink_file_path="Controller.java",
        sink_line_number=10,
        source_symbol=source.symbol,
    )
    return SimpleNamespace(sources=[source], sinks=[sink], traces=[trace])


class _OpenRedirectEngine:
    def __init__(self, flows):
        self.flows = flows

    def find_open_redirect_flows(self, *args, **kwargs):
        return self.flows


def test_enrich_open_redirect_flows_retains_engine_negative_as_evidence():
    state = _state_for_engine_flow()
    key = _flow_key(state.sources[0].symbol, "Controller.java", 10)
    context = SimpleNamespace(
        path="",
        engines={
            "dataflow_analyzer": _OpenRedirectEngine(
                {
                    key: {
                        "requestControlled": False,
                        "sinkArgument": "next",
                        "flowConfidence": "not_request_controlled",
                    }
                }
            )
        },
    )

    enrich_open_redirect_flows(None, context, state)

    assert len(state.traces) == 1
    metadata = state.traces[0].sink.metadata
    assert metadata["request_controlled"] is False
    assert metadata["sink_argument"] == "next"
    assert metadata["flow_confidence"] == "not_request_controlled"


def test_enrich_open_redirect_flows_uses_engine_target_argument_metadata():
    state = _state_for_engine_flow()
    key = _flow_key(state.sources[0].symbol, "Controller.java", 10)
    context = SimpleNamespace(
        path="",
        engines={
            "dataflow_analyzer": _OpenRedirectEngine(
                {
                    key: {
                        "requestControlled": True,
                        "sinkArgument": "next",
                        "sourceParam": "next",
                        "sourceKind": "@RequestParam",
                        "flowSummary": "next -> response.sendRedirect(next)",
                        "flowConfidence": "cpg-target-argument",
                    }
                }
            )
        },
    )

    enrich_open_redirect_flows(None, context, state)

    assert len(state.traces) == 1
    metadata = state.traces[0].sink.metadata
    assert metadata["request_controlled"] is True
    assert metadata["source_param"] == "next"
    assert metadata["flow_confidence"] == "cpg-target-argument"
