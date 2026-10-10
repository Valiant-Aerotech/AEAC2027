"""Competition telemetry packet (CONOPS 5.2.3.3.b).

Field names follow the CONOPS list. Extra keys are rejected so a future
schema change cannot silently ship a field the server will not score.

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


def _finite(value: float) -> bool:
    return math.isfinite(value)


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
    armed: bool = True

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

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, armed: bool = True) -> TelemetryPacket:
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
            armed=armed,
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
        armed: bool = True,
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
            armed=armed,
        )
