"""Packet timestamps.

The Pi 5 has no battery-backed clock. A wall time before 2026 is not a
legal competition timestamp: every packet would score latency or a
disconnect. Callers refuse the live socket until the clock is plausible.
This module does not read GPS time.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

PLAUSIBLE_AFTER = datetime(2026, 10, 10, tzinfo=timezone.utc).timestamp()


def packet_time(clock=None) -> float:
    """Unix time for a packet. ``clock`` replaces ``time.time`` in tests."""
    fn = time.time if clock is None else clock
    return float(fn())


def clock_is_plausible(clock=None) -> bool:
    return packet_time(clock) >= PLAUSIBLE_AFTER
