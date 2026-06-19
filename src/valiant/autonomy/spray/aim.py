"""Aim lock confirmation from metric geometry."""

from __future__ import annotations

from valiant.autonomy.packets import MetricPacket


def is_aimed(metric: MetricPacket, cfg: dict) -> bool:
    """Return True when pixel offset and altitude are within tolerance."""
    deadband = cfg.get("auto_nav", {}).get("deadband_px", 40)
    dx, dy = metric.pixel_offset
    if abs(dx) >= deadband or abs(dy) >= deadband:
        return False
    tol = cfg.get("metric_recon", {}).get(
        "alt_align_tolerance_m",
        cfg.get("sitl", {}).get("alt_align_tolerance_m", 0.25),
    )
    if metric.altitude_error_m is not None and abs(metric.altitude_error_m) > tol:
        return False
    return True
