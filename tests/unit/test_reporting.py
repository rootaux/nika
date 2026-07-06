import pytest

from reporting.html_renderer import HtmlReportRenderer
from reporting.code_reader import escape_html
from reporting.code_reader import CodeSnippetReader
from schema.vulnerability_schema import CallGraphNode, Vulnerability


@pytest.mark.parametrize("raw,expected", [
    ("<script>", "&lt;script&gt;"),
    ("a & b", "a &amp; b"),
    ('x" onmouseover="y', "x&quot; onmouseover=&quot;y"),
    ("it's", "it&#39;s"),
    (None, ""),
])
def test_escape_html(raw, expected):
    assert escape_html(raw) == expected


def test_amp_escaped_first_no_double_encoding():
    assert escape_html("<") == "&lt;"


def test_attribute_breakout_is_neutralized():
    payload = '"><img src=x onerror=alert(1)>'
    out = escape_html(payload)
    assert '"' not in out and "<" not in out and ">" not in out


def test_html_trace_renders_explicit_sink_for_single_node_trace(tmp_path):
    src = tmp_path / "Controller.java"
    src.write_text(
        "\n".join(
            [
                "class Controller {",
                "  @GetMapping(\"/fetch\")",
                "  String fetch(String url) {",
                "    HttpGet request = new HttpGet(url);",
                "    client.execute(request);",
                "  }",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    vulnerability = Vulnerability(
        sink="client.execute(request);",
        callPath="",
        callGraph=[
            CallGraphNode(
                methodname="fetch",
                filename="Controller.java",
                code="String fetch(String url) { ... }",
                methodLineNumberStart=2,
                methodLineNumberEnd=6,
                calleeLineNumber=None,
                isExternal=False,
            )
        ],
        lineNumber=5,
        lineNumberEnd=5,
        filename="Controller.java",
    )

    html = HtmlReportRenderer(CodeSnippetReader(str(tmp_path)))._trace_code_block(vulnerability)

    assert "Source (Controller.java:2)" in html
    assert "Sink (Controller.java:5)" in html
    assert "client.execute(request);" in html
