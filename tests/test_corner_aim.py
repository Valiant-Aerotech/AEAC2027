"""Corner aim offset geometry tests."""

from __future__ import annotations

import math

from valiant.autonomy.metric_recon.aim_offset import (
    compute_aim_point,
    metres_to_pixels_x,
    metres_to_pixels_y,
)
from valiant.autonomy.metric_recon.edge_proximity import classify_edges
from valiant.autonomy.packets import TargetHit


def _cfg() -> dict:
    return {
        "metric_recon": {
            "body_half_width_m": 0.25,
            "clearance_margin_m": 0.10,
            "body_half_height_m": 0.15,
            "vertical_clearance_margin_m": 0.10,
            "corner_edge_frac": 0.18,
            "corner_min_bbox_area_px": 800,
        },
        "camera": {"vfov_deg": 52.0},
    }


def _hit(cx: int, cy: int = 240) -> TargetHit:
    return TargetHit(cx=cx, cy=cy, area=1200, bbox=(cx - 20, cy - 20, cx + 20, cy + 20))


def test_metres_to_pixels_x_sanity():
    delta = metres_to_pixels_x(0.35, 1.0, 1280, 66.0)
    half_hfov = math.radians(33.0)
    expected = 0.35 * 640.0 / (1.0 * math.tan(half_hfov))
    assert abs(delta - expected) < 1.0
    assert 300 < delta < 400


def _lateral_aim(hit: TargetHit):
    edges = classify_edges(hit, 1280, 720, _cfg())
    return compute_aim_point(
        hit, 1280, 720, _cfg(), edges,
        range_m=1.0, hfov_deg=66.0, vfov_deg=52.0,
    )


def test_left_edge_aim_shifts_right():
    hit = _hit(80)
    result = _lateral_aim(hit)
    assert result.aim_y == hit.cy
    assert result.lateral_offset_m == 0.35
    assert result.aim_x > hit.cx
    assert abs(result.aim_x - (hit.cx + result.delta_x_px)) < 2
    assert result.lateral_ok


def test_right_edge_aim_shifts_left():
    hit = _hit(1200)
    result = _lateral_aim(hit)
    assert result.aim_x < hit.cx
    assert abs(result.aim_x - (hit.cx - result.delta_x_px)) < 2
    assert result.lateral_ok


def test_clamp_marks_body_clearance_not_ok():
    hit = _hit(1279)
    edges = classify_edges(hit, 1280, 720, _cfg())
    result = compute_aim_point(
        hit, 1280, 720, _cfg(), edges,
        range_m=0.2, hfov_deg=66.0, vfov_deg=52.0,
    )
    assert result.aim_x == 0
    assert result.delta_x_px > 1000
    assert not result.lateral_ok


def test_metres_to_pixels_y_sanity():
    delta = metres_to_pixels_y(0.25, 1.0, 720, 52.0)
    assert delta > 100


def test_bottom_edge_aim_shifts_up():
    hit = _hit(640, 680)
    edges = classify_edges(hit, 1280, 720, _cfg())
    result = compute_aim_point(
        hit, 1280, 720, _cfg(), edges,
        range_m=1.0, hfov_deg=66.0, vfov_deg=52.0,
    )
    assert result.aim_y < hit.cy
    assert result.body_alt_bias_m > 0
    assert result.vertical_ok


def test_top_edge_aim_shifts_down():
    hit = _hit(640, 40)
    edges = classify_edges(hit, 1280, 720, _cfg())
    result = compute_aim_point(
        hit, 1280, 720, _cfg(), edges,
        range_m=1.0, hfov_deg=66.0, vfov_deg=52.0,
    )
    assert result.aim_y > hit.cy
    assert result.body_alt_bias_m < 0
