"""Tests for multi-mission synthetic SITL camera."""

from __future__ import annotations

from valiant.common.synthetic_target_camera import SyntheticTargetCamera


def test_synthetic_multi_has_world_scene():
    cam = SyntheticTargetCamera("tests/fixtures/sitl_synthetic_multi.json")
    assert cam.world_scene is not None
    assert len(cam.world_scene.get("targets", [])) == 2


def test_synthetic_multi_produces_target():
    cam = SyntheticTargetCamera("tests/fixtures/sitl_synthetic_multi.json")
    frame = cam.get_frame()
    assert frame is not None
    pkt = cam.get_synthetic_cv_packet()
    assert pkt is not None and pkt.has_dry_target


def test_synthetic_multi_extinguish_and_advance():
    cam = SyntheticTargetCamera("tests/fixtures/sitl_synthetic_multi.json")
    cam.get_frame()
    cam.mark_extinguished_engaged()
    assert cam.world_scene["targets"][0].get("extinguished")
    assert cam.advance_to_next_mission()
    pkt = cam.get_synthetic_cv_packet()
    assert pkt is not None and pkt.has_dry_target


def test_legacy_timeline_still_works():
    cam = SyntheticTargetCamera("tests/fixtures/sitl_approach.json")
    assert cam.world_scene is None
    assert cam.get_frame() is not None


def test_synthetic_keyframes_follow_wall_range():
    from valiant.common.sitl_physics import VehiclePose

    cam = SyntheticTargetCamera("tests/fixtures/sitl_synthetic_multi.json")
    cam.set_vehicle_pose(VehiclePose(x=0.0, y=0.0, z=-2.8, ok=True))
    cam.get_frame()
    far_depth = float(cam.depth_mm[0, 0]) / 1000.0
    far_area = cam.get_synthetic_cv_packet().dry[0].area

    cam.set_vehicle_pose(VehiclePose(x=3.85, y=0.3, z=-1.5, ok=True))
    cam.get_frame()
    close_depth = float(cam.depth_mm[0, 0]) / 1000.0
    close_area = cam.get_synthetic_cv_packet().dry[0].area

    assert far_depth > close_depth
    assert close_area > far_area


def test_synthetic_without_pose_defaults_to_far_keyframe():
    cam = SyntheticTargetCamera("tests/fixtures/sitl_synthetic_multi.json")
    cam.get_frame()
    depth = float(cam.depth_mm[0, 0]) / 1000.0
    assert depth >= 3.4
