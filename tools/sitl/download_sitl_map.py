"""Download Esri World Imagery tiles for SITL top-down map (~2 km radius)."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valiant.common.sitl_geo import (  # noqa: E402
    TILE_SIZE_PX,
    SitlHome,
    lat_lon_to_tile,
    offset_lat_lon,
)
from valiant.common.sitl_map_asset import build_manifest_for_stitch  # noqa: E402

TILE_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)


def _fetch_tile(z: int, x: int, y: int, *, retries: int = 3) -> np.ndarray | None:
    url = TILE_URL.format(z=z, y=y, x=x)
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Valiant-Aerotech-SITL/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None and img.shape[0] == TILE_SIZE_PX:
                return img
        except (urllib.error.URLError, TimeoutError, cv2.error) as exc:
            if attempt >= retries:
                print(f"[map] tile {z}/{x}/{y} failed: {exc}")
                return None
            time.sleep(0.5 * attempt)
    return None


def download_map(
    home: SitlHome,
    out_dir: Path,
    *,
    radius_m: float = 2000.0,
    zoom: int = 16,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    north_lat, _ = offset_lat_lon(home.lat_deg, home.lon_deg, radius_m, 0.0)
    south_lat, _ = offset_lat_lon(home.lat_deg, home.lon_deg, -radius_m, 0.0)
    _, east_lon = offset_lat_lon(home.lat_deg, home.lon_deg, 0.0, radius_m)
    _, west_lon = offset_lat_lon(home.lat_deg, home.lon_deg, 0.0, -radius_m)

    x_min, y_min = lat_lon_to_tile(north_lat, west_lon, zoom)
    x_max, y_max = lat_lon_to_tile(south_lat, east_lon, zoom)

    cols = x_max - x_min + 1
    rows = y_max - y_min + 1
    canvas_w = cols * TILE_SIZE_PX
    canvas_h = rows * TILE_SIZE_PX
    canvas = np.full((canvas_h, canvas_w, 3), (32, 32, 36), dtype=np.uint8)

    total = cols * rows
    done = 0
    print(f"[map] Downloading {total} tiles (zoom {zoom}, ~{radius_m:.0f} m radius)...")
    for ty in range(y_min, y_max + 1):
        for tx in range(x_min, x_max + 1):
            tile = _fetch_tile(zoom, tx, ty)
            done += 1
            if tile is None:
                continue
            ox = (tx - x_min) * TILE_SIZE_PX
            oy = (ty - y_min) * TILE_SIZE_PX
            canvas[oy : oy + TILE_SIZE_PX, ox : ox + TILE_SIZE_PX] = tile
            if done % 10 == 0 or done == total:
                print(f"[map] {done}/{total} tiles")
            time.sleep(0.05)

    image_path = out_dir / "satellite.jpg"
    cv2.imwrite(str(image_path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    manifest = build_manifest_for_stitch(
        home,
        zoom=zoom,
        x_tile_min=x_min,
        y_tile_min=y_min,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        radius_m=radius_m,
    )
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"[map] Saved {image_path} ({canvas_w}x{canvas_h})")
    print(f"[map] Manifest {manifest_path}")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download SITL satellite map tiles")
    parser.add_argument("--home", default="tests/fixtures/sitl_home.json", help="Home JSON path")
    parser.add_argument("--out", default="tests/fixtures/sitl_map", help="Output directory")
    parser.add_argument("--radius-m", type=float, default=2000.0, help="Coverage radius (metres)")
    parser.add_argument("--zoom", type=int, default=16, help="Web mercator zoom level")
    args = parser.parse_args()

    home = SitlHome.load(args.home)
    download_map(home, ROOT / args.out, radius_m=args.radius_m, zoom=args.zoom)


if __name__ == "__main__":
    main()
