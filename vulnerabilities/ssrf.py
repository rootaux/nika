from vulnerabilities.base.base_vulnerability import BaseVulnerability
from vulnerabilities.base.stages import (
    discover_sources,
    finalize_findings,
    match_rule_sinks,
    review_traces_with_llm,
    run_dataflow,
)


class SsrfVulnerability(BaseVulnerability):
    vulnerability_id = "ssrf"
    title = "Server-Side Request Forgery"
    description = (
        "Server-Side Request Forgery (SSRF) vulnerability allows attackers to "
        "make requests from the server on behalf of the attacker."
    )
    supported_languages = ["java"]
    required_engine_roles = ["sink_finder", "source_finder", "dataflow_analyzer"]
    source_types = ["remote_input"]
    prompt_kind = "trace"
    stages = [
        match_rule_sinks,
        discover_sources,
        run_dataflow,
        review_traces_with_llm,
        finalize_findings,
    ]
    optional_stages = [review_traces_with_llm]
    review_mode = "optional"
    system_prompt = (
        "Review this trace for SSRF risk. Treat outbound requests influenced by "
        "user input as vulnerable unless the destination is fixed or strongly "
        "allowlisted. If validation might be bypassed or the controls are unclear, "
        "return NEED_MANUAL_REVIEW."
    )
    human_prompt = (
        "Analyze this SSRF trace and decide whether attacker-controlled input can "
        "influence the request URL, host, path, or destination without effective "
        "restrictions."
    )
    fallback_explanation = (
        "Trace reached an outbound request sink. Confirm whether untrusted input can "
        "control the destination or internal network access."
    )
    fallback_remediation = (
        "Use fixed destinations or strict allowlists for hosts, schemes, and ports "
        "before making outbound requests."
    )
    fallback_code_fix = (
        "Do not build request destinations directly from user input; map input to "
        "approved endpoints instead."
    )
