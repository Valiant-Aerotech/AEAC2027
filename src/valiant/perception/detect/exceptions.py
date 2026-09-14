"""CV module exceptions. Folded under the companion error contract."""

from valiant.core.errors import PerceptionDegraded, ValiantError


class CVError(ValiantError):
    """Base class for CV module errors."""


class LowConfidenceError(CVError):
    """Detection confidence below threshold."""


class BadFrameError(CVError, PerceptionDegraded):
    """Frame capture failed or frame is invalid."""
