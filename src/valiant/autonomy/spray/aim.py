"""Aim lock confirmation from metric geometry."""

from __future__ import annotations

from valiant.autonomy.packets import MetricPacket


def _deadband_px(cfg: dict) -> float:
    return float(cfg.get("auto_nav", {}).get("deadband_px", 40))


def _spray_deadband_px(cfg: dict, *, edge_target: bool) -> float:
    nav = cfg.get("auto_nav", {})
    deadband = _deadband_px(cfg)
    spray_db = float(nav.get("spray_deadband_px", deadband))
    if edge_target:
        spray_db = max(spray_db, deadband)
    return spray_db


def _spray_vertical_deadband_px(cfg: dict, *, edge_vertical: bool) -> float:
    nav = cfg.get("auto_nav", {})
    deadband = _deadband_px(cfg)
    spray_db = float(nav.get("spray_vertical_deadband_px", nav.get("spray_deadband_px", deadband)))
    if edge_vertical:
        spray_db = max(spray_db, deadband)
    return spray_db


def is_body_aligned(metric: MetricPacket, cfg: dict) -> bool:
    """True when virtual servo aim (pixel_offset) is within deadband."""
    deadband = _deadband_px(cfg)
    dx, dy = metric.pixel_offset
    return abs(dx) < deadband and abs(dy) < deadband


def is_target_aligned(metric: MetricPacket, cfg: dict) -> bool:
    """True when detected target centre is within spray deadband."""
    spray_db = _spray_deadband_px(cfg, edge_target=metric.edge_proximity.any_edge)
    vert_db = _spray_vertical_deadband_px(cfg, edge_vertical=metric.edge_vertical)
    if metric.target_offset is not None:
        dx, dy = metric.target_offset
    else:
        dx, dy = metric.pixel_offset
    return abs(dx) < spray_db and abs(dy) < vert_db


def is_aimed(metric: MetricPacket, cfg: dict) -> bool:
    """Return True when body and target alignment and altitude are within tolerance."""
    if not is_body_aligned(metric, cfg):
        return False
    if not is_target_aligned(metric, cfg):
        return False
    tol = cfg.get("metric_recon", {}).get(
        "alt_align_tolerance_m",
        cfg.get("sitl", {}).get("alt_align_tolerance_m", 0.25),
    )
    if metric.altitude_error_m is not None and abs(metric.altitude_error_m) > tol:
        return False
    return True
