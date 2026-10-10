"""Table 5 report-submission multiplier window.

CONOPS awards a submission-speed multiplier relative to the end of the flight
window. Exact tiers (documented as constants; multiplier math can come later):

- x150% if submitted ≥ MULTIPLIER_FULL_BEFORE_END_S before window end
- x100% if submitted at MULTIPLIER_CUTOFF_AFTER_END_S after window end
- linear between those two anchors
- x0% if submitted later than MULTIPLIER_CUTOFF_AFTER_END_S after window end

This class only tracks whether a submission is still inside the non-zero
multiplier window (flight window + grace after end).
"""

from __future__ import annotations

import time
from collections.abc import Callable

# CONOPS §2.8: each flight window is approximately 30 minutes.
FLIGHT_WINDOW_S = 30 * 60

# Table 5 report multiplier anchors relative to flight-window end.
MULTIPLIER_FULL_BEFORE_END_S = 5 * 60
MULTIPLIER_CUTOFF_AFTER_END_S = 15 * 60


class ReportWindow:
    """Flight window + post-end grace for a non-zero report multiplier."""

    def __init__(
        self,
        *,
        flight_window_s: float = FLIGHT_WINDOW_S,
        grace_after_end_s: float = MULTIPLIER_CUTOFF_AFTER_END_S,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._flight_window_s = float(flight_window_s)
        self._grace_after_end_s = float(grace_after_end_s)
        self._time = time_fn or time.monotonic
        self._started_at: float | None = None

    def start(self) -> None:
        """Open the flight window clock."""
        self._started_at = self._time()

    def elapsed_s(self) -> float:
        """Seconds since start(); 0 if not started."""
        if self._started_at is None:
            return 0.0
        return self._time() - self._started_at

    @property
    def in_multiplier_window(self) -> bool:
        """True while a submission can still earn a non-zero Table 5 multiplier."""
        if self._started_at is None:
            return False
        limit = self._flight_window_s + self._grace_after_end_s
        return self.elapsed_s() <= limit

    @property
    def started(self) -> bool:
        return self._started_at is not None
