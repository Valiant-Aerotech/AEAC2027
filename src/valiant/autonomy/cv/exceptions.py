"""CV module exceptions for orchestrator recovery."""


class CVError(Exception):
    """Base class for CV module errors."""


class LowConfidenceError(CVError):
    """Detection confidence below threshold."""


class BadFrameError(CVError):
    """Frame capture failed or frame is invalid."""
