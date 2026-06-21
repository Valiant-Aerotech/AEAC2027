"""Edge proximity classification tests."""

from __future__ import annotations

from valiant.autonomy.metric_recon.edge_proximity import classify_edges
from valiant.autonomy.packets import TargetHit


def _hit(cx: int, cy: int, area: int = 1200) -> TargetHit:
    return TargetHit(cx=cx, cy=cy, area=area, bbox=(cx - 20, cy - 20, cx + 20, cy + 20))


def _cfg() -> dict:
    return {"metric_recon": {"corner_edge_frac": 0.18, "corner_min_bbox_area_px": 800}}


def test_center_not_edge():
    e = classify_edges(_hit(640, 360), 1280, 720, _cfg())
    assert not e.any_edge


def test_left_edge():
    e = classify_edges(_hit(80, 360), 1280, 720, _cfg())
    assert e.left and not e.right


def test_right_edge():
    e = classify_edges(_hit(1200, 360), 1280, 720, _cfg())
    assert e.right and not e.left


def test_bottom_edge():
    e = classify_edges(_hit(640, 680), 1280, 720, _cfg())
    assert e.bottom and not e.top


def test_top_edge():
    e = classify_edges(_hit(640, 40), 1280, 720, _cfg())
    assert e.top and not e.bottom


def test_diagonal_bottom_left():
    e = classify_edges(_hit(80, 680), 1280, 720, _cfg())
    assert e.left and e.bottom
    assert e.labels() == ("L", "B")
