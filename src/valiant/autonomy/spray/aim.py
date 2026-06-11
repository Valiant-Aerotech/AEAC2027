"""Aim angle and lock confirmation from metric geometry."""

from __future__ import annotations

import math

from valiant.autonomy.packets import MetricPacket


def aim_angles_deg(metric: MetricPacket, cfg: dict) -> tuple[float, float]:
    """Return (yaw_offset_deg, pitch_offset_deg) from pixel offset and FOV."""
    cam = cfg.get("camera", {})
    hfov = cam.get("hfov_deg", 66.0)
    vfov = cam.get("vfov_deg", 52.0)

    # Assume frame centre = boresight; scale offset to degrees
    # Normalized offset in [-1, 1] per axis (approximate using deadband scale)
    deadband = cfg.get("auto_nav", {}).get("deadband_px", 40)
    scale = max(deadband * 4, 1)

    dx, dy = metric.pixel_offset
    yaw_deg = (dx / scale) * (hfov / 4.0)
    pitch_deg = (dy / scale) * (vfov / 4.0)
    return yaw_deg, pitch_deg


def aim_error_magnitude_deg(metric: MetricPacket, cfg: dict) -> float:
    yaw, pitch = aim_angles_deg(metric, cfg)
    return math.sqrt(yaw * yaw + pitch * pitch)


def is_aimed(metric: MetricPacket, cfg: dict) -> bool:
    """Return True when pixel offset is within deadband."""
    deadband = cfg.get("auto_nav", {}).get("deadband_px", 40)
    dx, dy = metric.pixel_offset
    return abs(dx) < deadband and abs(dy) < deadband
