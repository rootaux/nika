import json
import os

from models.sink import Sink


def _metavar_metadata(extra: dict) -> dict:
    normalized = {}
    for name, value in (extra.get("metavars") or {}).items():
        if not isinstance(value, dict):
            continue
        entry = {}
        if value.get("abstract_content") is not None:
            entry["abstract_content"] = value.get("abstract_content")
        propagated = value.get("propagated_value")
        if isinstance(propagated, dict):
            entry["propagated_value"] = propagated.get("svalue_abstract_content")
        if entry:
            normalized[name] = entry
    return normalized


def _result_metadata(result: dict, extra: dict) -> dict:
    metadata = dict(extra.get("metadata") or {})
    if result.get("check_id"):
        metadata["rule_id"] = result.get("check_id")
    metavars = _metavar_metadata(extra)
    if metavars:
        metadata["metavars"] = metavars
    return metadata


def translate_opengrep_results(raw, repo_path: str) -> list[Sink]:
    payload = json.loads(raw) if isinstance(raw, str) else raw
    sinks = []
    seen = set()

    for result in payload.get("results", []):
        path = result.get("path", "")
        if os.path.isabs(path):
            path = os.path.relpath(path, repo_path)

        start = result.get("start", {}) or {}
        end = result.get("end", {}) or {}
        extra = result.get("extra", {}) or {}

        line_number = start.get("line", 0)
        key = (path, line_number)
        if key in seen:
            continue
        seen.add(key)

        sinks.append(
            Sink(
                rule_id=result.get("check_id"),
                file_path=path,
                line_number=line_number,
                line_number_end=end.get("line"),
                code=(extra.get("lines") or "").strip(),
                metadata=_result_metadata(result, extra),
            )
        )

    return sinks
