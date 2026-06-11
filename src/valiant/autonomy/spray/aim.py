"""Aim lock confirmation from metric geometry."""

from __future__ import annotations

from valiant.autonomy.packets import MetricPacket


def is_aimed(metric: MetricPacket, cfg: dict) -> bool:
    """Return True when pixel offset is within deadband."""
    deadband = cfg.get("auto_nav", {}).get("deadband_px", 40)
    dx, dy = metric.pixel_offset
    return abs(dx) < deadband and abs(dy) < deadband
