"""Competition telemetry packet (CONOPS 5.2.3.3.b).

Python field names stay stable for logs and the penalty book. ``to_wire``
is the camelCase payload the competition websocket accepts.

Invalid-GPS rules match Comp Server Support (Waleed, 2026-09-27): no-fix is
lat and lon both 0, or horizontal accuracy non-finite or <= 0. There is no
upper accuracy ceiling. Non-finite numerics and out-of-range lat/lon are
validation rejects, not invalid-GPS scores — see ``validation_reject_reason``.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

REQUIRED_FIELDS = (
    "id",
    "timestamp",
    "lat",
    "lon",
    "alt_agl_m",
    "accuracy_m",
    "battery_pct",
    "flight_mode",
    "link_quality",
)

FLIGHT_MODES = frozenset({"off", "idle", "link-lost", "failsafe", "armed-pilot", "armed-automatic"})
ARMED_MODES = frozenset({"armed-pilot", "armed-automatic"})


def _finite(value: float) -> bool:
    return math.isfinite(value)


def _link_bit(value: float) -> int | None:
    if value == 0 or value == 0.0:
        return 0
    if value == 1 or value == 1.0:
        return 1
    return None


@dataclass(frozen=True)
class TelemetryPacket:
    uav_id: str
    timestamp: float
    lat: float
    lon: float
    alt_agl_m: float
    accuracy_m: float
    battery_pct: float
    flight_mode: str
    link_quality: float
    rc_link_quality: float | None = None

    @property
    def armed(self) -> bool:
        return self.flight_mode in ARMED_MODES

    def validation_reject_reason(self) -> str | None:
        """Return a reject reason, or None if the packet may be scored.

        Non-finite numerics and lat/lon outside WGS84 bounds are rejected
        before invalid-GPS scoring (organizer rule: validation, not
        ``invalid_gps``).
        """
        numeric = {
            "timestamp": self.timestamp,
            "lat": self.lat,
            "lon": self.lon,
            "alt_agl_m": self.alt_agl_m,
            "accuracy_m": self.accuracy_m,
            "battery_pct": self.battery_pct,
            "link_quality": self.link_quality,
        }
        for name, value in numeric.items():
            if not _finite(value):
                return f"non-finite {name}"
        if not (-90.0 <= self.lat <= 90.0 and -180.0 <= self.lon <= 180.0):
            return "lat/lon out of range"
        if self.flight_mode not in FLIGHT_MODES:
            return "flight mode"
        if not 0.0 <= self.battery_pct <= 100.0:
            return "battery"
        if _link_bit(self.link_quality) is None:
            return "link status"
        if self.rc_link_quality is not None and _link_bit(self.rc_link_quality) is None:
            return "link status"
        return None

    def gps_valid(self) -> bool:
        """True unless no-fix (0, 0) or horizontal accuracy is unusable.

        Call only after ``validation_reject_reason`` is None. A large positive
        accuracy is valid. Non-finite accuracy is also treated as invalid so a
        direct call cannot slip through, but the client rejects non-finite
        fields first and does not score them as invalid GPS.
        """
        if self.lat == 0.0 and self.lon == 0.0:
            return False
        if not _finite(self.accuracy_m) or self.accuracy_m <= 0.0:
            return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.uav_id,
            "timestamp": self.timestamp,
            "lat": self.lat,
            "lon": self.lon,
            "alt_agl_m": self.alt_agl_m,
            "accuracy_m": self.accuracy_m,
            "battery_pct": self.battery_pct,
            "flight_mode": self.flight_mode,
            "link_quality": self.link_quality,
        }

    def to_wire(self, *, unix_time: float | None = None) -> dict[str, Any]:
        """CamelCase payload for the competition websocket.

        ``verticalPositionAccuracy`` copies horizontal accuracy.
        ``rcLinkStatus`` uses ``rc_link_quality`` when that bit is set, and
        otherwise copies the telemetry link bit. Both are 0 or 1.
        """
        link = _link_bit(self.link_quality)
        bit = 0 if link is None else link
        rc_source = self.link_quality if self.rc_link_quality is None else self.rc_link_quality
        rc = _link_bit(rc_source)
        rc_bit = bit if rc is None else rc
        return {
            "uavId": self.uav_id,
            "unixTime": self.timestamp if unix_time is None else unix_time,
            "latitude": self.lat,
            "longitude": self.lon,
            "altitudeAGL": self.alt_agl_m,
            "horizontalPositionAccuracy": self.accuracy_m,
            "verticalPositionAccuracy": self.accuracy_m,
            "batteryPercentage": self.battery_pct,
            "mode": self.flight_mode,
            "telemetryLinkStatus": bit,
            "rcLinkStatus": rc_bit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryPacket:
        missing = [name for name in REQUIRED_FIELDS if name not in data]
        extra = [key for key in data if key not in REQUIRED_FIELDS]
        if missing:
            raise ValueError(f"packet missing fields: {missing}")
        if extra:
            raise ValueError(f"packet has unknown fields: {extra}")
        return cls(
            uav_id=str(data["id"]),
            timestamp=float(data["timestamp"]),
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            alt_agl_m=float(data["alt_agl_m"]),
            accuracy_m=float(data["accuracy_m"]),
            battery_pct=float(data["battery_pct"]),
            flight_mode=str(data["flight_mode"]),
            link_quality=float(data["link_quality"]),
        )

    @classmethod
    def now(
        cls,
        uav_id: str,
        *,
        lat: float,
        lon: float,
        alt_agl_m: float,
        accuracy_m: float,
        battery_pct: float,
        flight_mode: str,
        link_quality: float,
        clock=time.time,
    ) -> TelemetryPacket:
        return cls(
            uav_id=uav_id,
            timestamp=float(clock()),
            lat=lat,
            lon=lon,
            alt_agl_m=alt_agl_m,
            accuracy_m=accuracy_m,
            battery_pct=battery_pct,
            flight_mode=flight_mode,
            link_quality=link_quality,
        )
