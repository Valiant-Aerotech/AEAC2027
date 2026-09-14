"""Competition telemetry packet (CONOPS 5.2.3.3.b).

Field names follow the CONOPS list. Extra keys are rejected so a future
schema change cannot silently ship a field the server will not score.
"""

from __future__ import annotations

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

# Horizontal GPS accuracy worse than this is treated as invalid-GPS for scoring.
INVALID_GPS_ACCURACY_M = 50.0


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

    def gps_valid(self) -> bool:
        if abs(self.lat) < 1e-8 and abs(self.lon) < 1e-8:
            return False
        if not (-90.0 <= self.lat <= 90.0 and -180.0 <= self.lon <= 180.0):
            return False
        return self.accuracy_m <= INVALID_GPS_ACCURACY_M

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
