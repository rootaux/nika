from typing import Protocol


class DataflowAnalyzer(Protocol):
    def find_traces(self, context, sources, sinks): ...
