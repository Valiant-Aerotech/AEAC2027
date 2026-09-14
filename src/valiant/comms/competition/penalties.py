"""Seven CONOPS 5.2.3 telemetry penalty types.

Each type is capped at five occurrences; the criterion floors at zero. The
estimator exists so the crew can see which problems are still worth fixing
mid-flight: once a type has fired five times it is free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

OCCURRENCE_CAP = 5
BURST_WINDOW_S = 15.0
DISCONNECT_FIRST_S = 30.0
DISCONNECT_REPEAT_S = 15.0
SLOW_RATE_S = 1.1
FAST_RATE_S = 0.4
LATENCY_LIMIT_S = 15.0

POINTS = {
    "traffic_keepout": 5,
    "disconnect": 5,
    "disconnect_tick": 1,
    "startup_armed": 2,
    "invalid_gps": 2,
    "timestamp_latency": 2,
    "slow_rate": 1,
    "fast_rate": 1,
}


class PenaltyType(str, Enum):
    TRAFFIC_KEEPOUT = "traffic_keepout"
    DISCONNECT = "disconnect"
    STARTUP_ARMED = "startup_armed"
    INVALID_GPS = "invalid_gps"
    TIMESTAMP_LATENCY = "timestamp_latency"
    SLOW_RATE = "slow_rate"
    FAST_RATE = "fast_rate"


@dataclass
class PenaltyEvent:
    kind: PenaltyType
    points: int
    at_s: float
    detail: str = ""


@dataclass
class PenaltyBook:
    events: list[PenaltyEvent] = field(default_factory=list)
    _last_burst: dict[PenaltyType, float] = field(default_factory=dict)
    _counts: dict[PenaltyType, int] = field(default_factory=dict)
    _disconnect_open_at: float | None = None

    def count(self, kind: PenaltyType) -> int:
        return self._counts.get(kind, 0)

    def remaining(self, kind: PenaltyType) -> int:
        return max(0, OCCURRENCE_CAP - self.count(kind))

    def total_points(self) -> int:
        return sum(e.points for e in self.events)

    def _record(self, kind: PenaltyType, points: int, now: float, detail: str) -> PenaltyEvent | None:
        if self.count(kind) >= OCCURRENCE_CAP:
            return None
        event = PenaltyEvent(kind=kind, points=points, at_s=now, detail=detail)
        self.events.append(event)
        self._counts[kind] = self.count(kind) + 1
        return event

    def _burst_ok(self, kind: PenaltyType, now: float) -> bool:
        last = self._last_burst.get(kind)
        if last is not None and now - last < BURST_WINDOW_S:
            return False
        self._last_burst[kind] = now
        return True

    def traffic_keepout(self, now: float, *, detail: str = "") -> PenaltyEvent | None:
        return self._record(PenaltyType.TRAFFIC_KEEPOUT, POINTS["traffic_keepout"], now, detail)

    def startup_armed(self, now: float) -> PenaltyEvent | None:
        return self._record(PenaltyType.STARTUP_ARMED, POINTS["startup_armed"], now, "armed before telemetry")

    def invalid_gps(self, now: float) -> PenaltyEvent | None:
        if not self._burst_ok(PenaltyType.INVALID_GPS, now):
            return None
        return self._record(PenaltyType.INVALID_GPS, POINTS["invalid_gps"], now, "invalid GPS while armed")

    def timestamp_latency(self, now: float, delta_s: float) -> PenaltyEvent | None:
        if delta_s <= LATENCY_LIMIT_S:
            return None
        if not self._burst_ok(PenaltyType.TIMESTAMP_LATENCY, now):
            return None
        return self._record(
            PenaltyType.TIMESTAMP_LATENCY,
            POINTS["timestamp_latency"],
            now,
            f"timestamp delta {delta_s:.1f}s",
        )

    def rate(self, now: float, interval_s: float) -> PenaltyEvent | None:
        if interval_s > SLOW_RATE_S:
            if not self._burst_ok(PenaltyType.SLOW_RATE, now):
                return None
            return self._record(PenaltyType.SLOW_RATE, POINTS["slow_rate"], now, f"interval {interval_s:.2f}s")
        if 0 < interval_s < FAST_RATE_S:
            if not self._burst_ok(PenaltyType.FAST_RATE, now):
                return None
            return self._record(PenaltyType.FAST_RATE, POINTS["fast_rate"], now, f"interval {interval_s:.2f}s")
        return None

    def note_packet(self, now: float) -> None:
        """A packet went out; close any open disconnect window."""
        self._disconnect_open_at = None

    def note_silence(self, now: float, last_packet_at: float | None, *, armed: bool) -> PenaltyEvent | None:
        """Call when the scheduler ticks and no packet was sent.

        First occurrence at 30 s of silence while armed: -5. Each further
        15 s: -1. Both count toward the five-occurrence cap on DISCONNECT.
        """
        if not armed or last_packet_at is None:
            return None
        gap = now - last_packet_at
        if gap < DISCONNECT_FIRST_S:
            return None
        if self._disconnect_open_at is None:
            self._disconnect_open_at = last_packet_at + DISCONNECT_FIRST_S
            return self._record(PenaltyType.DISCONNECT, POINTS["disconnect"], now, "30s silence")
        if now - self._disconnect_open_at >= DISCONNECT_REPEAT_S:
            self._disconnect_open_at = now
            return self._record(PenaltyType.DISCONNECT, POINTS["disconnect_tick"], now, "disconnect tick")
        return None
