import os
import re

import pytest
import yaml

pytestmark = pytest.mark.e2e

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "expected.yaml"), "r", encoding="utf-8") as handle:
    EXPECTED = yaml.safe_load(handle)

POSITIVE = EXPECTED.get("positive", {})
NEGATIVE = EXPECTED.get("negative", {})
CATEGORY_ALIASES = {
    "sensitive_logging": ["sensitivelogging", "sensitivedatalogging"],
    "ssrf": ["ssrf", "serversiderequestforgery"],
    "xxe": ["xxe", "xmlexternalentityinjection"],
}


def _findings_in(findings, fixture_file):
    return [f for f in findings if (f.get("filename") or "").endswith(fixture_file)]


def _category_matches(finding, category):
    expected = CATEGORY_ALIASES.get(
        category,
        [re.sub(r"[^a-z0-9]", "", category.lower())],
    )
    actual = re.sub(r"[^a-z0-9]", "", (finding.get("vulnerability") or "").lower())
    return any(alias in actual for alias in expected)


@pytest.mark.parametrize("category", sorted(POSITIVE))
def test_vulnerability_detected(golden_findings, category):
    spec = POSITIVE[category]
    matches = _findings_in(golden_findings, spec["fixture"])
    if not matches and spec.get("xfail"):
        pytest.xfail(spec["xfail"])
    reported = sorted({(f.get("vulnerability"), f.get("filename")) for f in golden_findings})
    assert matches, (
        f"{category}: expected a finding in {spec['fixture']}, got none.\nAll findings: {reported}"
    )
    assert any(_category_matches(f, category) for f in matches), (
        f"{category}: expected a category-correct finding in {spec['fixture']}, "
        f"got {[f.get('vulnerability') for f in matches]}"
    )


@pytest.mark.parametrize("category", sorted(POSITIVE))
def test_fixture_not_reported_as_other_category(golden_findings, category):
    spec = POSITIVE[category]
    matches = _findings_in(golden_findings, spec["fixture"])
    wrong_category = [f for f in matches if not _category_matches(f, category)]
    assert not wrong_category, (
        f"{category}: fixture {spec['fixture']} was also reported under another category: "
        f"{[f.get('vulnerability') for f in wrong_category]}"
    )


@pytest.mark.parametrize("category", sorted(NEGATIVE))
def test_safe_code_not_flagged(golden_findings, category):
    spec = NEGATIVE[category]
    matches = _findings_in(golden_findings, spec["fixture"])
    assert not matches, (
        f"{category}: safe fixture {spec['fixture']} was flagged (false positive): "
        f"{[f.get('vulnerability') for f in matches]}"
    )
