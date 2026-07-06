import json
from types import SimpleNamespace

from agents.security_agent import SecurityAgent


def test_astrail_lookup_tool_returns_structured_error_on_exception():
    class FailingAstrail:
        def get_method_and_file_name(self, code, filename):
            raise RuntimeError("boom")

    agent = SecurityAgent.__new__(SecurityAgent)
    agent.runtime_context = SimpleNamespace(astrail=FailingAstrail())

    lookup_tool = agent._build_astrail_search_method_name_tool()
    result = json.loads(
        lookup_tool.invoke({"code": "call()", "filename": "src/main/java/C.java"})
    )

    assert result["fileName"] == ""
    assert result["methodName"] == ""
    assert result["error"] == "astrail_lookup_failed"
    assert "boom" in result["detail"]
