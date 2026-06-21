"""Spray aim dual-alignment tests."""

from __future__ import annotations

from valiant.autonomy.packets import EdgeProximity, MetricPacket
from valiant.autonomy.spray import is_aimed, is_body_aligned, is_target_aligned


def _cfg() -> dict:
    return {"auto_nav": {"deadband_px": 40, "spray_deadband_px": 60}}


def test_center_target_both_aligned():
    metric = MetricPacket(target_px=(640, 360), pixel_offset=(0.0, 0.0), target_offset=(0.0, 0.0))
    assert is_body_aligned(metric, _cfg())
    assert is_target_aligned(metric, _cfg())
    assert is_aimed(metric, _cfg())


def test_corner_body_aligned_target_off_centre():
    metric = MetricPacket(
        target_px=(200, 360),
        pixel_offset=(0.0, 0.0),
        target_offset=(-440.0, 0.0),
        aim_px=(550, 360),
        edge_proximity=EdgeProximity(left=True),
        lateral_clearance_ok=True,
        vertical_clearance_ok=True,
    )
    assert is_body_aligned(metric, _cfg())
    assert not is_target_aligned(metric, _cfg())
    assert not is_aimed(metric, _cfg())


def test_corner_both_aligned_when_target_within_spray_deadband():
    metric = MetricPacket(
        target_px=(600, 360),
        pixel_offset=(0.0, 0.0),
        target_offset=(-40.0, 0.0),
        aim_px=(640, 360),
        edge_proximity=EdgeProximity(left=True),
        lateral_clearance_ok=True,
        vertical_clearance_ok=True,
    )
    assert is_aimed(metric, _cfg())
