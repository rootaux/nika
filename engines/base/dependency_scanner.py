from typing import Protocol


class DependencyScanner(Protocol):
    def scan_dependencies(self, context): ...
