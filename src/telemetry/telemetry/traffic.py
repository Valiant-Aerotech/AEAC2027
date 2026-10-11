"""Airspace traffic from the competition server.

Keepaway distance is a placeholder until the server spec is read
(see docs/conops.md). Horizontal distance uses an equirectangular
approximation; good enough inside the Medicine Hat site.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

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
    heading_deg: float | None = None


def offset_m(lat: float, lon: float, other_lat: float, other_lon: float) -> tuple[float, float]:
    """North and east offset, in metres, from the other aircraft to ``lat, lon``."""
    mean_lat = math.radians((lat + other_lat) / 2.0)
    north = (lat - other_lat) * _METRES_PER_DEG_LAT
    east = (lon - other_lon) * _METRES_PER_DEG_LAT * math.cos(mean_lat)
    return north, east


def horizontal_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    north, east = offset_m(lat1, lon1, lat2, lon2)
    return math.hypot(north, east)


def inside_keepout(
    lat: float,
    lon: float,
    alt_agl_m: float,
    other: TrafficAircraft,
) -> bool:
    if abs(alt_agl_m - other.alt_agl_m) > other.keepout_height_m:
        return False
    return horizontal_distance_m(lat, lon, other.lat, other.lon) < other.keepout_radius_m


def _traffic_rows(payload: object) -> list:
    if isinstance(payload, dict):
        body = payload.get("payload")
        if isinstance(body, dict):
            rows = body.get("traffic", [])
        else:
            rows = payload.get("traffic", payload.get("aircraft", []))
        return list(rows or [])
    if isinstance(payload, list):
        return payload
    return []


def _row_position(item: dict) -> dict:
    position = item.get("position")
    if isinstance(position, dict):
        return position
    return item


def parse_traffic(payload: object) -> tuple[TrafficAircraft, ...]:
    """Read a traffic event, ``{"traffic": [...]}``, or a list of rows.

    Live rows use ``aircraftIndex`` and ``position.lat/lon/altitude/direction``.
    ``direction`` is stored and not used for avoidance in this pass.
    """
    out = []
    for item in _traffic_rows(payload):
        if not isinstance(item, dict):
            continue
        position = _row_position(item)
        index = item.get("aircraftIndex", item.get("id", item.get("uavId")))
        if index is None or "lat" not in position or "lon" not in position:
            continue
        direction = position.get("direction", item.get("direction"))
        altitude = position.get("altitude", position.get("alt_agl_m", position.get("alt", 0.0)))
        out.append(
            TrafficAircraft(
                uav_id=str(index),
                lat=float(position["lat"]),
                lon=float(position["lon"]),
                alt_agl_m=float(altitude or 0.0),
                keepout_radius_m=float(item.get("keepout_radius_m", DEFAULT_KEEPOUT_RADIUS_M)),
                keepout_height_m=float(item.get("keepout_height_m", DEFAULT_KEEPOUT_HEIGHT_M)),
                heading_deg=None if direction is None else float(direction),
            )
        )
    return tuple(out)
