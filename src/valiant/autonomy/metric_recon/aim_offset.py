"""Virtual servo aim point for edge-proximity clearance."""

from __future__ import annotations

import math
from dataclasses import dataclass

from valiant.autonomy.metric_recon.edge_proximity import classify_edges
from valiant.autonomy.packets import EdgeProximity, TargetHit


def metres_to_pixels_x(
    lateral_m: float,
    range_m: float,
    frame_w: int,
    hfov_deg: float,
) -> float:
    """Convert lateral metres at range_m to horizontal pixels (pinhole)."""
    if range_m <= 0 or frame_w <= 0:
        return 0.0
    half_hfov = math.radians(hfov_deg / 2.0)
    half_width_m = range_m * math.tan(half_hfov)
    return lateral_m * (frame_w / 2.0) / max(half_width_m, 1e-6)


def metres_to_pixels_y(
    vertical_m: float,
    range_m: float,
    frame_h: int,
    vfov_deg: float,
) -> float:
    """Convert vertical metres at range_m to vertical pixels (pinhole)."""
    if range_m <= 0 or frame_h <= 0:
        return 0.0
    half_vfov = math.radians(vfov_deg / 2.0)
    half_height_m = range_m * math.tan(half_vfov)
    return vertical_m * (frame_h / 2.0) / max(half_height_m, 1e-6)


def _axis_ok(required_delta: float, actual_delta: float) -> bool:
    if required_delta <= 1.0:
        return True
    return abs(actual_delta) >= required_delta * 0.85


@dataclass(frozen=True)
class AimResult:
    aim_x: int
    aim_y: int
    delta_x_px: float
    delta_y_px: float
    lateral_offset_m: float
    vertical_offset_m: float
    lateral_ok: bool
    vertical_ok: bool
    body_alt_bias_m: float

    @property
    def body_clearance_ok(self) -> bool:
        return self.lateral_ok and self.vertical_ok


def compute_aim_point(
    hit: TargetHit,
    frame_w: int,
    frame_h: int,
    cfg: dict,
    edges: EdgeProximity,
    *,
    range_m: float,
    hfov_deg: float,
    vfov_deg: float,
) -> AimResult:
    """
    Return virtual aim point shifting body away from triggered edges.

    Lateral: left -> aim_x increases; right -> aim_x decreases.
    Vertical: bottom (floor) -> aim_y decreases (climb); top (ceiling) -> aim_y increases.
    body_alt_bias_m: gimbal-mode vertical body shift (+ = hold higher).
    """
    metric = cfg.get("metric_recon", {})
    body_half_w = float(metric.get("body_half_width_m", 0.25))
    margin_w = float(metric.get("clearance_margin_m", 0.10))
    body_half_h = float(metric.get("body_half_height_m", 0.15))
    margin_h = float(metric.get("vertical_clearance_margin_m", 0.10))

    lateral_offset_m = body_half_w + margin_w
    vertical_offset_m = body_half_h + margin_h
    delta_x = metres_to_pixels_x(lateral_offset_m, range_m, frame_w, hfov_deg) if edges.lateral else 0.0
    delta_y = metres_to_pixels_y(vertical_offset_m, range_m, frame_h, vfov_deg) if edges.vertical else 0.0

    unclamped_x = float(hit.cx)
    if edges.left:
        unclamped_x = hit.cx + delta_x
    elif edges.right:
        unclamped_x = hit.cx - delta_x

    unclamped_y = float(hit.cy)
    body_alt_bias_m = 0.0
    if edges.bottom:
        unclamped_y = hit.cy - delta_y
        body_alt_bias_m += vertical_offset_m
    elif edges.top:
        unclamped_y = hit.cy + delta_y
        body_alt_bias_m -= vertical_offset_m

    aim_x = int(round(max(0.0, min(frame_w - 1, unclamped_x))))
    aim_y = int(round(max(0.0, min(frame_h - 1, unclamped_y))))

    lateral_ok = not edges.lateral or _axis_ok(delta_x, float(aim_x - hit.cx))
    vertical_ok = not edges.vertical or _axis_ok(delta_y, float(aim_y - hit.cy))

    return AimResult(
        aim_x=aim_x,
        aim_y=aim_y,
        delta_x_px=delta_x,
        delta_y_px=delta_y,
        lateral_offset_m=lateral_offset_m if edges.lateral else 0.0,
        vertical_offset_m=vertical_offset_m if edges.vertical else 0.0,
        lateral_ok=lateral_ok,
        vertical_ok=vertical_ok,
        body_alt_bias_m=body_alt_bias_m,
    )


def compute_aim_pixel(
    hit: TargetHit,
    frame_w: int,
    frame_h: int,
    cfg: dict,
    *,
    range_m: float,
    hfov_deg: float,
) -> tuple[int, int, float, float, bool]:
    """Legacy lateral-only API; prefer compute_aim_point."""
    from valiant.autonomy.metric_recon.edge_proximity import classify_edges

    edges = classify_edges(hit, frame_w, frame_h, cfg)
    if not edges.lateral:
        edges = EdgeProximity(left=hit.cx < frame_w // 2, right=hit.cx >= frame_w // 2)
    vfov = float(cfg.get("camera", {}).get("vfov_deg", cfg.get("fov", {}).get("vfov_deg", 52.0)))
    result = compute_aim_point(
        hit, frame_w, frame_h, cfg, edges,
        range_m=range_m, hfov_deg=hfov_deg, vfov_deg=vfov,
    )
    return (
        result.aim_x,
        result.aim_y,
        result.delta_x_px,
        result.lateral_offset_m,
        result.lateral_ok,
    )
