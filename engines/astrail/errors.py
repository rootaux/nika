class AstrailEngineError(RuntimeError):
    """Raised when an Astrail query fails (timeout, malformed JSON, connection refused)."""

    pass
