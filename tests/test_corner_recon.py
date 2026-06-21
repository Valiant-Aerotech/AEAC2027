"""Reconstructor corner-target integration."""

from __future__ import annotations

from valiant.autonomy.metric_recon import create_metric_reconstructor
from valiant.autonomy.packets import CVPacket, TargetHit


def _corner_cv(cx: int = 80) -> CVPacket:
    hit = TargetHit(cx=cx, cy=240, area=1800, bbox=(cx - 30, 210, cx + 30, 270))
    return CVPacket(dry=[hit], shot=[], method="yolo", timestamp=0.0)


def test_reconstructor_sets_aim_for_left_corner():
    cfg = {
        "metric_recon": {
            "mode": "rangefinder",
            "rangefinder": "fov_estimate",
            "target_diameter_min_m": 0.05,
            "target_diameter_max_m": 0.30,
            "corner_edge_frac": 0.18,
            "corner_min_bbox_area_px": 800,
            "body_half_width_m": 0.25,
            "clearance_margin_m": 0.10,
            "body_half_height_m": 0.15,
            "vertical_clearance_margin_m": 0.10,
        },
        "camera": {"hfov_deg": 66.0, "vfov_deg": 52.0},
    }
    recon = create_metric_reconstructor(None, cfg, sim=True)
    packet = recon.reconstruct(_corner_cv(), 1280, 720)
    assert packet is not None
    assert packet.edge_proximity.left
    assert packet.aim_px is not None
    assert packet.aim_px[0] > packet.target_px[0]
    assert packet.target_offset is not None
    assert abs(packet.target_offset[0]) > abs(packet.pixel_offset[0])


def test_reconstructor_sets_aim_for_bottom_edge():
    cfg = {
        "metric_recon": {
            "mode": "rangefinder",
            "rangefinder": "fov_estimate",
            "target_diameter_min_m": 0.05,
            "target_diameter_max_m": 0.30,
            "corner_edge_frac": 0.18,
            "corner_min_bbox_area_px": 800,
            "body_half_height_m": 0.15,
            "vertical_clearance_margin_m": 0.10,
        },
        "camera": {"hfov_deg": 66.0, "vfov_deg": 52.0},
    }
    hit = TargetHit(cx=640, cy=680, area=1800, bbox=(610, 650, 670, 710))
    cv = CVPacket(dry=[hit], shot=[], method="yolo", timestamp=0.0)
    recon = create_metric_reconstructor(None, cfg, sim=True)
    packet = recon.reconstruct(cv, 1280, 720)
    assert packet is not None
    assert packet.edge_proximity.bottom
    assert packet.aim_px is not None
    assert packet.aim_px[1] < packet.target_px[1]
    assert packet.body_alt_bias_m > 0
