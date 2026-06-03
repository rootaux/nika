from typing import Protocol


class SinkFinder(Protocol):
    def find_sinks(self, context, rules_path: str): ...
