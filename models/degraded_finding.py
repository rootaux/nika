class DegradedFinding:
    """Represents a vulnerability check that could not complete due to an engine failure."""

    def __init__(self, vulnerability_id: str, reason: str):
        self.vulnerability_id = vulnerability_id
        self.reason = reason
