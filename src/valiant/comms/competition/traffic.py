"""Airspace traffic from the competition server.

Keepaway distance is a placeholder until the server spec is read
(see docs/conops-2027.md). Horizontal distance uses an equirectangular
approximation; good enough inside the Medicine Hat site.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from valiant.core.geo import offset_lat_lon

# Placeholder until aeac.mylonics.com documents the cylinder.
DEFAULT_KEEPOUT_RADIUS_M = 30.0
DEFAULT_KEEPOUT_HEIGHT_M = 30.0
TASK2_STANDOFF_M = 100.0

_METRES_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class TrafficAircraft:
    uav_id: str
    lat: float
    lon: float
    alt_agl_m: float
    keepout_radius_m: float = DEFAULT_KEEPOUT_RADIUS_M
    keepout_height_m: float = DEFAULT_KEEPOUT_HEIGHT_M


def horizontal_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mean_lat = math.radians((lat1 + lat2) / 2.0)
    dn = (lat2 - lat1) * _METRES_PER_DEG_LAT
    de = (lon2 - lon1) * _METRES_PER_DEG_LAT * math.cos(mean_lat)
    return math.hypot(dn, de)


def inside_keepout(
    lat: float,
    lon: float,
    alt_agl_m: float,
    other: TrafficAircraft,
) -> bool:
    if abs(alt_agl_m - other.alt_agl_m) > other.keepout_height_m:
        return False
    return horizontal_distance_m(lat, lon, other.lat, other.lon) < other.keepout_radius_m


def parse_traffic(payload: list[dict]) -> tuple[TrafficAircraft, ...]:
    out = []
    for item in payload:
        out.append(
            TrafficAircraft(
                uav_id=str(item["id"]),
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                alt_agl_m=float(item.get("alt_agl_m", item.get("alt", 0.0))),
                keepout_radius_m=float(item.get("keepout_radius_m", DEFAULT_KEEPOUT_RADIUS_M)),
                keepout_height_m=float(item.get("keepout_height_m", DEFAULT_KEEPOUT_HEIGHT_M)),
            )
        )
    return tuple(out)


def offset_from(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    return offset_lat_lon(lat, lon, north_m, east_m)
