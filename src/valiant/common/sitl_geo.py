"""Geodesy helpers for SITL map tiles and home location."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from valiant.common.config import repo_root

EARTH_RADIUS_M = 6_371_000.0
TILE_SIZE_PX = 256


@dataclass(frozen=True)
class SitlHome:
    lat_deg: float
    lon_deg: float
    alt_m: float = 100.0
    heading_deg: float = 0.0
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> SitlHome:
        return cls(
            lat_deg=float(data["lat_deg"]),
            lon_deg=float(data["lon_deg"]),
            alt_m=float(data.get("alt_m", 100.0)),
            heading_deg=float(data.get("heading_deg", 0.0)),
            name=str(data.get("name", "")),
        )

    def sim_vehicle_location(self) -> str:
        """ArduPilot ``sim_vehicle.py -l`` argument: lat,lon,alt,heading."""
        return f"{self.lat_deg:.7f},{self.lon_deg:.7f},{self.alt_m:.1f},{self.heading_deg:.0f}"

    @classmethod
    def load(cls, path: str | Path | None = None) -> SitlHome:
        if path is None:
            path = repo_root() / "tests" / "fixtures" / "sitl_home.json"
        p = Path(path)
        if not p.is_file():
            p = repo_root() / path
        with open(p, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def parse_dms(dms: str) -> float:
    """Parse ``47°34'33.9\"N`` or ``52°44'03.5\"W`` to signed decimal degrees."""
    text = dms.strip().upper().replace("°", " ").replace("'", " ").replace('"', " ")
    parts = [p for p in text.split() if p]
    if len(parts) < 4:
        raise ValueError(f"Invalid DMS: {dms!r}")
    deg = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    hemi = parts[3][0]
    value = deg + minutes / 60.0 + seconds / 3600.0
    if hemi in ("S", "W"):
        value = -value
    return value


def meters_per_pixel(lat_deg: float, zoom: int) -> float:
    return 156_543.03392 * math.cos(math.radians(lat_deg)) / (2**zoom)


def lat_lon_to_tile_fraction(lat_deg: float, lon_deg: float, zoom: int) -> tuple[float, float]:
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    x = (lon_deg + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def lat_lon_to_tile(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    xf, yf = lat_lon_to_tile_fraction(lat_deg, lon_deg, zoom)
    return int(xf), int(yf)


def tile_to_lat_lon(xtile: float, ytile: float, zoom: int) -> tuple[float, float]:
    n = 2.0**zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * ytile / n)))
    return math.degrees(lat_rad), lon_deg


def offset_lat_lon(lat_deg: float, lon_deg: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * math.cos(math.radians(lat_deg)))
    return lat_deg + dlat, lon_deg + dlon
