"""Map RGB target pixels to depth frame coordinates using calibration."""

from __future__ import annotations

from typing import Any

import numpy as np


def rgb_to_depth_pixel(
    cx: int,
    cy: int,
    rgb_w: int,
    rgb_h: int,
    cal: dict[str, Any],
) -> tuple[int, int]:
    """Affine map from RGB pixel to depth sensor pixel."""
    mapping = cal.get("rgb_to_depth", {})
    scale_x = mapping.get("scale_x", 1.0)
    scale_y = mapping.get("scale_y", 1.0)
    offset_x = mapping.get("offset_x", 0.0)
    offset_y = mapping.get("offset_y", 0.0)

    depth_w = mapping.get("depth_width") or cal.get("depth_width")
    depth_h = mapping.get("depth_height") or cal.get("depth_height")

    dx = int(round(cx * scale_x + offset_x))
    dy = int(round(cy * scale_y + offset_y))

    if depth_w is not None:
        dx = max(0, min(int(depth_w) - 1, dx))
    if depth_h is not None:
        dy = max(0, min(int(depth_h) - 1, dy))

    return dx, dy


def sample_depth_m(
    depth_mm,
    cx: int,
    cy: int,
    *,
    window_px: int = 5,
    cal: dict[str, Any] | None = None,
    invalid_mm: int = 0,
    max_mm: int = 6000,
) -> float | None:
    """Median depth in mm window around (cx, cy), converted to meters."""
    if depth_mm is None:
        return None

    cal = cal or {}
    half = max(1, window_px // 2)
    h, w = depth_mm.shape[:2]
    x0 = max(0, cx - half)
    x1 = min(w, cx + half + 1)
    y0 = max(0, cy - half)
    y1 = min(h, cy + half + 1)

    patch = depth_mm[y0:y1, x0:x1].astype("float64")
    valid = (patch > invalid_mm) & (patch <= max_mm)
    if not valid.any():
        return None

    median_mm = float(np.median(patch[valid]))
    scale = cal.get("depth_scale", 0.001)
    offset_m = cal.get("depth_offset_m", 0.0)
    return median_mm * scale + offset_m
