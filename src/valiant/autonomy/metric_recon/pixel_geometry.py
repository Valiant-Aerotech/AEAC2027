"""Pixel offset and FOV-based distance estimation."""

from __future__ import annotations

import math

from valiant.autonomy.packets import TargetHit


def pixel_offset(hit: TargetHit, frame_w: int, frame_h: int) -> tuple[float, float]:
    cx, cy = frame_w // 2, frame_h // 2
    return (float(hit.cx - cx), float(hit.cy - cy))


def estimate_distance_fov(
    hit: TargetHit,
    frame_w: int,
    *,
    hfov_deg: float,
    target_diameter_m: float,
) -> float | None:
    """Estimate range from apparent target width and camera HFOV."""
    x1, _, x2, _ = hit.bbox
    bbox_w = max(x2 - x1, 1)
    if frame_w <= 0 or bbox_w <= 0:
        return None

    angular_width_deg = (bbox_w / frame_w) * hfov_deg
    if angular_width_deg < 0.5:
        return None

    half_angle = math.radians(angular_width_deg / 2.0)
    if half_angle < 1e-6:
        return None

    return (target_diameter_m / 2.0) / math.tan(half_angle)


def estimate_side_clearance(
    hit: TargetHit,
    frame_w: int,
    distance_m: float | None,
    *,
    hfov_deg: float,
) -> float | None:
    """Rough lateral clearance from target pixel position and estimated range."""
    if distance_m is None or distance_m <= 0:
        return None

    margin_px = min(hit.cx, frame_w - hit.cx)
    if frame_w <= 0:
        return None

    # Fraction of half-frame width remaining on nearest side
    fraction = margin_px / (frame_w / 2.0)
    half_hfov_rad = math.radians(hfov_deg / 2.0)
    lateral_span_m = distance_m * math.tan(half_hfov_rad)
    return lateral_span_m * fraction
