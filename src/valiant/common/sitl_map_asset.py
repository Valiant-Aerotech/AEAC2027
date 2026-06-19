"""Load stitched satellite map for SITL top-down view."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from valiant.common.config import repo_root
from valiant.common.sitl_geo import SitlHome, lat_lon_to_tile_fraction


@dataclass(frozen=True)
class SitlMapAsset:
    """Satellite mosaic aligned to SITL home (LOCAL NED origin)."""

    image_bgr: np.ndarray
    home_lat_deg: float
    home_lon_deg: float
    zoom: int
    meters_per_pixel: float
    home_px_x: float
    home_px_y: float
    attribution: str = "Esri World Imagery"

    @classmethod
    def load(cls, manifest_path: str | Path) -> SitlMapAsset | None:
        path = Path(manifest_path)
        if not path.is_file():
            path = repo_root() / manifest_path
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
        img_path = path.parent / meta["image"]
        image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image is None:
            return None
        return cls(
            image_bgr=image,
            home_lat_deg=float(meta["home_lat_deg"]),
            home_lon_deg=float(meta["home_lon_deg"]),
            zoom=int(meta["zoom"]),
            meters_per_pixel=float(meta["meters_per_pixel"]),
            home_px_x=float(meta["home_px_x"]),
            home_px_y=float(meta["home_px_y"]),
            attribution=str(meta.get("attribution", "Esri World Imagery")),
        )

    @classmethod
    def default(cls) -> SitlMapAsset | None:
        return cls.load(repo_root() / "tests" / "fixtures" / "sitl_map" / "manifest.json")

    def ned_to_map_px(self, north_m: float, east_m: float) -> tuple[float, float]:
        """LOCAL NED metres (x=north, y=east) -> mosaic pixel (north up)."""
        mpp = self.meters_per_pixel
        mx = self.home_px_x + east_m / mpp
        my = self.home_px_y - north_m / mpp
        return mx, my

    def crop_drone_centered(
        self,
        north_m: float,
        east_m: float,
        *,
        width: int,
        height: int,
        view_radius_m: float,
    ) -> np.ndarray:
        """Extract viewport with drone at centre; north up, east right."""
        mpp_view = (2.0 * view_radius_m) / min(width, height)
        drone_mx, drone_my = self.ned_to_map_px(north_m, east_m)
        half_w = width / 2.0
        half_h = height / 2.0
        src_w = width * (mpp_view / self.meters_per_pixel)
        src_h = height * (mpp_view / self.meters_per_pixel)
        x0 = drone_mx - src_w / 2.0
        y0 = drone_my - src_h / 2.0
        matrix = np.array(
            [[src_w / width, 0, x0], [0, src_h / height, y0]],
            dtype=np.float32,
        )
        return cv2.warpAffine(
            self.image_bgr,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(32, 32, 36),
        )


def build_manifest_for_stitch(
    home: SitlHome,
    *,
    zoom: int,
    x_tile_min: int,
    y_tile_min: int,
    canvas_w: int,
    canvas_h: int,
    radius_m: float,
) -> dict:
    xf, yf = lat_lon_to_tile_fraction(home.lat_deg, home.lon_deg, zoom)
    home_px_x = (xf - x_tile_min) * 256
    home_px_y = (yf - y_tile_min) * 256
    return {
        "home_lat_deg": home.lat_deg,
        "home_lon_deg": home.lon_deg,
        "radius_m": radius_m,
        "zoom": zoom,
        "width_px": canvas_w,
        "height_px": canvas_h,
        "meters_per_pixel": 156_543.03392 * math.cos(math.radians(home.lat_deg)) / (2**zoom),
        "home_px_x": home_px_x,
        "home_px_y": home_px_y,
        "x_tile_min": x_tile_min,
        "y_tile_min": y_tile_min,
        "image": "satellite.jpg",
        "attribution": "Tiles © Esri - Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    }
