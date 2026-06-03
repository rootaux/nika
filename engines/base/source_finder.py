from typing import Protocol


class SourceFinder(Protocol):
    def find_sources(self, context, source_definitions: dict[str, list[str]]): ...
