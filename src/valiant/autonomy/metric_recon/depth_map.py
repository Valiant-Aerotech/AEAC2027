"""Sample depth at RGB pixel coordinates from a depth frame."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

import numpy as np

from valiant.autonomy.packets import TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt


def map_rgb_to_depth_px(
    cx: int,
    cy: int,
    calib: dict[str, Any] | None,
) -> tuple[int, int]:
    """Map RGB pixel to depth frame coordinates using calibration."""
    if not calib:
        return cx, cy
    rgb_map = calib.get("rgb_to_depth", calib)
    sx = float(rgb_map.get("scale_x", 1.0))
    sy = float(rgb_map.get("scale_y", 1.0))
    ox = float(rgb_map.get("offset_x", 0.0))
    oy = float(rgb_map.get("offset_y", 0.0))
    return int(round(cx * sx + ox)), int(round(cy * sy + oy))


def sample_depth_m(
    depth_mm: npt.NDArray[np.uint16],
    cx: int,
    cy: int,
    *,
    patch_radius: int = 5,
    calib: dict[str, Any] | None = None,
) -> float | None:
    """Median depth in a square patch around (cx, cy), returned in metres."""
    if depth_mm is None or depth_mm.size == 0:
        return None
    dx, dy = map_rgb_to_depth_px(cx, cy, calib)
    h, w = depth_mm.shape[:2]
    dx = int(np.clip(dx, 0, w - 1))
    dy = int(np.clip(dy, 0, h - 1))
    r = max(patch_radius, 1)
    y0, y1 = max(0, dy - r), min(h, dy + r + 1)
    x0, x1 = max(0, dx - r), min(w, dx + r + 1)
    patch = depth_mm[y0:y1, x0:x1]
    valid = patch[(patch > 0) & (patch < 60000)]
    if valid.size == 0:
        return None
    depth_scale = 0.001
    if calib:
        depth_scale = float(calib.get("depth_scale", depth_scale))
    offset_m = float(calib.get("depth_offset_m", 0.0)) if calib else 0.0
    return float(np.median(valid)) * depth_scale + offset_m


def sample_depth_at_bbox(
    depth_mm: npt.NDArray[np.uint16],
    hit: TargetHit,
    *,
    calib: dict[str, Any] | None = None,
) -> float | None:
    """Median depth over target bbox in depth frame."""
    if depth_mm is None or depth_mm.size == 0:
        return None
    x1, y1, x2, y2 = hit.bbox
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    radius = max((x2 - x1) // 2, (y2 - y1) // 2, 3)
    window = int(calib.get("depth_sample_window_px", 5)) if calib else 5
    return sample_depth_m(depth_mm, cx, cy, patch_radius=max(radius, window), calib=calib)
