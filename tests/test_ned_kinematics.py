"""Tests for NED kinematics module."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from valiant.common.ned_kinematics import (
    ApproachPhase,
    VehiclePose,
    compute_approach_goal,
    compute_altitude_vz,
    distance_3d,
    ned_to_body_velocity,
    ned_to_body_vector,
    rot_body_from_ned,
    velocity_toward_goal,
    wall_north_m,
)

SCENE = json.loads(Path("tests/fixtures/sitl_physics_wall.json").read_text(encoding="utf-8"))


def test_rot_round_trip():
    r = rot_body_from_ned(0.1, -0.05, 0.7)
    v_ned = np.array([1.0, 0.5, -0.2])
    pose = VehiclePose(roll=0.1, pitch=-0.05, yaw=0.7, ok=True)
    v_body = ned_to_body_vector(pose, v_ned)
    v_back = rot_body_from_ned(pose.roll, pose.pitch, pose.yaw) @ v_body
    np.testing.assert_allclose(v_back, v_ned, atol=1e-9)


def test_distance_3d_includes_z():
    pose = VehiclePose(x=0.0, y=0.0, z=-5.0, ok=True)
    target = (1.0, 0.0, -1.1)
    d3 = distance_3d(pose, target)
    assert d3 >= math.hypot(1.0, 3.9)


def test_velocity_toward_goal_descends():
    pose = VehiclePose(x=0.0, y=0.0, z=-5.0, ok=True)
    target = (1.0, 0.0, -1.1)
    goal = compute_approach_goal(
        pose, target, SCENE,
        cruise_alt_m=5.0,
        descent_wall_range_m=4.5,
        align_to_target=True,
        alt_offset_m=-0.15,
        min_clearance_m=1.0,
    )
    assert goal.phase == ApproachPhase.ALIGN
    v = velocity_toward_goal(pose, goal, speed_m_s=0.12, max_vz=0.14, kp_z=0.22)
    assert v[2] > 0.0


def test_compute_altitude_vz_descends():
    pose = VehiclePose(x=1.0, y=0.0, z=-5.0, ok=True)
    vz = compute_altitude_vz(
        pose, SCENE,
        min_ground_clearance_m=1.0,
        kp_z=0.25,
        cruise_alt_m=5.0,
        descent_wall_range_m=4.5,
    )
    assert vz > 0.0


def test_ned_to_body_velocity_yaw_only_matches_horizontal():
    pose = VehiclePose(yaw=0.0, ok=True)
    vx, vy, vz = ned_to_body_velocity(pose, 0.1, 0.2, -0.05)
    assert abs(vx - 0.1) < 1e-6
    assert abs(vy - 0.2) < 1e-6
    assert abs(vz + 0.05) < 1e-6


def test_wall_north_from_scene():
    assert wall_north_m(SCENE) == 5.0
