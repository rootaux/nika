from pathlib import Path


def resolve_java_rules_path(vulnerability_id: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / "rules" / vulnerability_id / "java")
