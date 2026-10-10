"""CONOPS 5.2.3.6 course-time stopwatch.

Time count begins at takeoff and ends when the UAV reaches the search-area
boundary. Scoring is relative to other bidders (Table 5); this module only
measures elapsed transit time.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class CourseTimer:
    """Monotonic stopwatch for takeoff → search-area boundary."""

    def __init__(self, *, time_fn: Callable[[], float] | None = None) -> None:
        self._time = time_fn or time.monotonic
        self._started_at: float | None = None
        self._finished_at: float | None = None

    def start(self) -> None:
        """Mark takeoff (or restart). Clears any previous finish."""
        self._started_at = self._time()
        self._finished_at = None

    def finish(self) -> None:
        """Mark arrival at the search-area boundary."""
        if self._started_at is None:
            raise RuntimeError("CourseTimer.finish() called before start()")
        if self._finished_at is None:
            self._finished_at = self._time()

    def elapsed_s(self) -> float:
        """Seconds since start(); frozen after finish()."""
        if self._started_at is None:
            return 0.0
        end = self._finished_at if self._finished_at is not None else self._time()
        return end - self._started_at

    @property
    def done(self) -> bool:
        """True once finish() has been called after start()."""
        return self._finished_at is not None

    @property
    def started(self) -> bool:
        return self._started_at is not None
