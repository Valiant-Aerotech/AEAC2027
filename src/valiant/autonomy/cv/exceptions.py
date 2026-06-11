"""CV module exceptions for orchestrator recovery."""


class CVError(Exception):
    """Base class for CV module errors."""


class TargetLostError(CVError):
    """No dry target visible for too many consecutive frames."""


class LowConfidenceError(CVError):
    """Detection confidence below threshold."""


class BadFrameError(CVError):
    """Frame capture failed or frame is invalid."""
