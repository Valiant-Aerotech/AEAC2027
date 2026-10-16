"""Airspace traffic from the competition server.

The server sends ``horizontalKeepAway`` and ``verticalKeepAway`` on each
traffic row. Those are stored when present. A row that omits them uses the
30 m placeholder. Horizontal distance uses an equirectangular approximation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import NoReturn

# Placeholder until aeac.mylonics.com documents the cylinder.
DEFAULT_KEEPOUT_RADIUS_M = 30.0
DEFAULT_KEEPOUT_HEIGHT_M = 30.0
TASK2_STANDOFF_M = 100.0

_METRES_PER_DEG_LAT = 111_320.0
TRAFFIC_SNAPSHOT_VERSION = 1


class TrafficSnapshotError(ValueError):
    """A traffic event or ROS snapshot violates the traffic contract."""


@dataclass(frozen=True)
class TrafficAircraft:
    uav_id: str
    lat: float
    lon: float
    alt_agl_m: float
    keepout_radius_m: float = DEFAULT_KEEPOUT_RADIUS_M
    keepout_height_m: float = DEFAULT_KEEPOUT_HEIGHT_M
    heading_deg: float | None = None


@dataclass(frozen=True)
class TrafficSnapshot:
    version: int
    session_id: str
    sequence: int
    aircraft: tuple[TrafficAircraft, ...]


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


def _fail(message: str) -> NoReturn:
    raise TrafficSnapshotError(message)


def _traffic_rows(payload: object) -> list[object]:
    if isinstance(payload, dict):
        if "event" in payload:
            if payload.get("event") != "traffic":
                _fail("not a traffic event")
            body = payload.get("payload")
            if not isinstance(body, dict) or "traffic" not in body:
                _fail("traffic event has no traffic list")
            rows = body["traffic"]
        elif "traffic" in payload:
            rows = payload["traffic"]
        else:
            _fail("unrecognized traffic envelope")
        if not isinstance(rows, list):
            _fail("traffic must be a list")
        return rows
    _fail("traffic envelope must be an object")


def _row_position(item: dict) -> dict:
    position = item.get("position")
    if isinstance(position, dict):
        return position
    _fail("aircraft position must be an object")


def _keepaway_m(item: dict, *keys: str, default: float) -> float:
    """First present keep-away, otherwise the 30 m placeholder."""
    for key in keys:
        if key in item and item[key] is not None:
            return _finite_number(item[key], key, positive=True)
    return default


def _finite_number(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        _fail(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        _fail(f"{name} must be a finite number")
    if not math.isfinite(number) or (positive and number <= 0.0):
        _fail(f"{name} must be {'positive and ' if positive else ''}finite")
    return number


def _aircraft_id(value: object) -> str:
    if value is None or isinstance(value, bool):
        _fail("aircraft ID is required")
    aircraft_id = str(value)
    if not aircraft_id:
        _fail("aircraft ID cannot be empty")
    return aircraft_id


def parse_traffic(
    payload: object,
) -> tuple[TrafficAircraft, ...]:
    """Read a traffic event, ``{"traffic": [...]}``, or a list of rows.

    Live rows use ``aircraftIndex`` and ``position.lat/lon/altitude/direction``.
    ``horizontalKeepAway`` and ``verticalKeepAway`` override the 30 m
    placeholder. ``direction`` is stored and not used for avoidance.
    """
    out: list[TrafficAircraft] = []
    seen_ids: set[str] = set()
    for item in _traffic_rows(payload):
        if not isinstance(item, dict):
            _fail("each traffic row must be an object")
        position = _row_position(item)
        index = item.get("aircraftIndex", item.get("id", item.get("uavId")))
        aircraft_id = _aircraft_id(index)
        if aircraft_id in seen_ids:
            _fail(f"duplicate aircraft ID: {aircraft_id}")
        seen_ids.add(aircraft_id)
        if "lat" not in position or "lon" not in position or "altitude" not in position:
            _fail(f"aircraft {aircraft_id} has an incomplete position")
        direction = position.get("direction", item.get("direction"))
        out.append(
            TrafficAircraft(
                uav_id=aircraft_id,
                lat=_finite_number(position["lat"], "lat"),
                lon=_finite_number(position["lon"], "lon"),
                alt_agl_m=_finite_number(position["altitude"], "altitude"),
                keepout_radius_m=_keepaway_m(
                    item,
                    "horizontalKeepAway",
                    "keepout_radius_m",
                    default=DEFAULT_KEEPOUT_RADIUS_M,
                ),
                keepout_height_m=_keepaway_m(
                    item,
                    "verticalKeepAway",
                    "keepout_height_m",
                    default=DEFAULT_KEEPOUT_HEIGHT_M,
                ),
                heading_deg=None if direction is None else _finite_number(direction, "direction"),
            )
        )
    return tuple(out)


def traffic_json(snapshot: TrafficSnapshot) -> str:
    """Serialize a versioned traffic snapshot for `/aeac/traffic`."""
    rows = [
        {
            "alt_agl_m": item.alt_agl_m,
            "id": item.uav_id,
            "keepout_height_m": item.keepout_height_m,
            "keepout_radius_m": item.keepout_radius_m,
            "lat": item.lat,
            "lon": item.lon,
            "heading_deg": item.heading_deg,
        }
        for item in snapshot.aircraft
    ]
    payload = {
        "aircraft": rows,
        "sequence": snapshot.sequence,
        "session_id": snapshot.session_id,
        "version": snapshot.version,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def parse_traffic_json(text: str) -> TrafficSnapshot:
    """Strictly reconstruct a versioned `/aeac/traffic` snapshot."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        _fail("traffic snapshot is not valid JSON")
    if not isinstance(payload, dict):
        _fail("traffic snapshot must be an object")
    if payload.get("version") != TRAFFIC_SNAPSHOT_VERSION:
        _fail("unsupported traffic snapshot version")
    session_id = payload.get("session_id")
    sequence = payload.get("sequence")
    rows = payload.get("aircraft")
    if not isinstance(session_id, str) or not session_id:
        _fail("session_id must be a non-empty string")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        _fail("sequence must be a non-negative integer")
    if not isinstance(rows, list):
        _fail("aircraft must be a list")
    out: list[TrafficAircraft] = []
    seen_ids: set[str] = set()
    for item in rows:
        required = {"id", "lat", "lon", "alt_agl_m", "keepout_radius_m", "keepout_height_m", "heading_deg"}
        if not isinstance(item, dict) or not required.issubset(item):
            _fail("aircraft row is incomplete")
        aircraft_id = _aircraft_id(item["id"])
        if aircraft_id in seen_ids:
            _fail(f"duplicate aircraft ID: {aircraft_id}")
        seen_ids.add(aircraft_id)
        heading = item["heading_deg"]
        out.append(
            TrafficAircraft(
                uav_id=aircraft_id,
                lat=_finite_number(item["lat"], "lat"),
                lon=_finite_number(item["lon"], "lon"),
                alt_agl_m=_finite_number(item["alt_agl_m"], "alt_agl_m"),
                keepout_radius_m=_finite_number(item["keepout_radius_m"], "keepout_radius_m", positive=True),
                keepout_height_m=_finite_number(item["keepout_height_m"], "keepout_height_m", positive=True),
                heading_deg=None if heading is None else _finite_number(heading, "heading_deg"),
            )
        )
    return TrafficSnapshot(TRAFFIC_SNAPSHOT_VERSION, session_id, sequence, tuple(out))
