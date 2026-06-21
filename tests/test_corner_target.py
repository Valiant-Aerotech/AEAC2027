"""Corner-target detection heuristic tests."""

from __future__ import annotations

from valiant.autonomy.metric_recon.corner_target import is_corner_target
from valiant.autonomy.packets import TargetHit


def _hit(cx: int, area: int = 1200) -> TargetHit:
    return TargetHit(cx=cx, cy=240, area=area, bbox=(cx - 20, 220, cx + 20, 260))


def _cfg() -> dict:
    return {
        "metric_recon": {
            "corner_edge_frac": 0.18,
            "corner_min_bbox_area_px": 800,
        }
    }


def test_center_target_not_corner():
    assert not is_corner_target(_hit(640), 1280, 720, _cfg())


def test_left_edge_is_corner():
    assert is_corner_target(_hit(80), 1280, 720, _cfg())


def test_small_bbox_not_corner():
    assert not is_corner_target(_hit(80, area=400), 1280, 720, _cfg())


def test_right_edge_is_corner():
    assert is_corner_target(_hit(1200), 1280, 720, _cfg())
