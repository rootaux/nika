class LanguagePack:
    language = "base"

    def get_source_definitions(self, source_types: list[str]) -> dict[str, list[str]]:
        raise NotImplementedError

    def resolve_rules_path(self, vulnerability_id: str) -> str:
        raise NotImplementedError
