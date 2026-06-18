"""Tests for SITL 3D target projection."""

from __future__ import annotations

from valiant.common.sitl_physics import VehiclePose, project_target_ned


def test_project_target_ahead_of_drone():
    pose = VehiclePose(x=0, y=0, z=-5, roll=0, pitch=0, yaw=0, ok=True)
    proj = project_target_ned(
        (4.0, 0.0, -5.0),
        pose,
        gimbal_pitch_deg=0,
        target_diameter_m=0.2,
        frame_w=640,
        frame_h=480,
        hfov_deg=66,
        vfov_deg=52,
    )
    assert proj is not None
    assert proj.visible
    assert 300 <= proj.cx <= 340
    assert abs(proj.depth_m - 4.0) < 0.2


def test_project_target_oblique_right():
    pose = VehiclePose(x=0, y=0, z=-3, yaw=0, ok=True)
    proj = project_target_ned(
        (3.0, -2.0, -2.0),
        pose,
        gimbal_pitch_deg=15,
        target_diameter_m=0.2,
        frame_w=640,
        frame_h=480,
        hfov_deg=66,
        vfov_deg=52,
    )
    assert proj is not None
    assert proj.visible
    assert proj.cx != 320
