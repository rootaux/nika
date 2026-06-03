from languages.base.language_pack import LanguagePack

from .rule_resolver import resolve_java_rules_path
from .source_discovery import select_source_definitions


class JavaLanguagePack(LanguagePack):
    language = "java"

    def get_source_definitions(self, source_types: list[str]) -> dict[str, list[str]]:
        return select_source_definitions(source_types)

    def resolve_rules_path(self, vulnerability_id: str) -> str:
        return resolve_java_rules_path(vulnerability_id)
