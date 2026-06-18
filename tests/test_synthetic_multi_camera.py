"""Unit tests for multi-target synthetic camera and pose-linked keyframes."""

from __future__ import annotations

import json
from pathlib import Path

from valiant.common.sitl_physics import VehiclePose
from valiant.common.synthetic_target_camera import SyntheticTargetCamera

SCENE_PATH = Path("tests/fixtures/sitl_synthetic_multi.json")
SCENE = json.loads(SCENE_PATH.read_text(encoding="utf-8"))


def test_multi_target_camera_loads_two_missions():
    cam = SyntheticTargetCamera(SCENE_PATH)
    assert cam.world_scene is not None
    frame = cam.get_frame()
    assert frame is not None
    pkt = cam.get_synthetic_cv_packet()
    assert pkt is not None and pkt.has_dry_target


def test_keyframes_track_wall_range_not_wall_clock():
    cam = SyntheticTargetCamera(SCENE_PATH)
    cam.set_vehicle_pose(VehiclePose(x=0.0, y=0.0, z=-5.0, ok=True))
    cam.get_frame()
    far = cam.get_synthetic_cv_packet()
    cam.set_vehicle_pose(VehiclePose(x=4.25, y=0.0, z=-1.1, ok=True))
    cam.get_frame()
    near = cam.get_synthetic_cv_packet()
    assert far is not None and near is not None
    assert far.dry[0].bbox[2] - far.dry[0].bbox[0] < near.dry[0].bbox[2] - near.dry[0].bbox[0]


def test_near_pose_depth_within_fire_range():
    cam = SyntheticTargetCamera(SCENE_PATH)
    cam.set_vehicle_pose(VehiclePose(x=4.25, y=0.3, z=-1.1, ok=True))
    cam.get_frame()
    pkt = cam.get_synthetic_cv_packet()
    assert pkt is not None
    depth_mm = cam.depth_mm
    assert depth_mm is not None
    depth_m = float(depth_mm[0, 0]) / 1000.0
    assert depth_m <= 0.95


def test_advance_mission_switches_target():
    cam = SyntheticTargetCamera(SCENE_PATH)
    cam.get_frame()
    cam.mark_extinguished_engaged()
    assert cam.advance_to_next_mission()
    cam.get_frame()
    pkt = cam.get_synthetic_cv_packet()
    assert pkt is not None and pkt.has_dry_target
