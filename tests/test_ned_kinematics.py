"""LOCAL NED kinematics: rotations, distances, approach goals, speed taper."""

from __future__ import annotations

import math

import numpy as np

from valiant.core.kinematics import (
    ApproachPhase,
    VehiclePose,
    compute_approach_goal,
    distance_3d,
    ned_to_body_vector,
    ned_to_body_velocity,
    rot_body_from_ned,
    speed_scaled_by_range,
    velocity_toward_goal,
)


def test_rot_round_trip():
    v_ned = np.array([1.0, 0.5, -0.2])
    pose = VehiclePose(roll=0.1, pitch=-0.05, yaw=0.7, ok=True)
    v_body = ned_to_body_vector(pose, v_ned)
    v_back = rot_body_from_ned(pose.roll, pose.pitch, pose.yaw) @ v_body
    np.testing.assert_allclose(v_back, v_ned, atol=1e-9)


def test_distance_3d_includes_z():
    pose = VehiclePose(x=0.0, y=0.0, z=-5.0, ok=True)
    assert distance_3d(pose, (1.0, 0.0, -1.1)) >= math.hypot(1.0, 3.9)


def test_ned_to_body_velocity_yaw_only_matches_horizontal():
    pose = VehiclePose(yaw=0.0, ok=True)
    vx, vy, vz = ned_to_body_velocity(pose, 0.1, 0.2, -0.05)
    assert (vx, vy, vz) == (0.1, 0.2, -0.05)


def test_approach_goal_cruises_while_far():
    pose = VehiclePose(x=0.0, y=0.0, z=-30.0, ok=True)
    goal = compute_approach_goal(
        pose,
        (100.0, 0.0, 0.0),
        cruise_alt_m=30.0,
        descend_range_m=15.0,
        align_to_target=False,
        alt_offset_m=0.0,
        min_clearance_m=2.0,
    )
    assert goal.phase is ApproachPhase.CRUISE
    assert goal.position_ned[2] == -30.0


def test_approach_goal_descends_inside_range():
    pose = VehiclePose(x=95.0, y=0.0, z=-30.0, ok=True)
    goal = compute_approach_goal(
        pose,
        (100.0, 0.0, 0.0),
        cruise_alt_m=30.0,
        descend_range_m=15.0,
        align_to_target=False,
        alt_offset_m=2.0,
        min_clearance_m=2.0,
    )
    assert goal.phase is ApproachPhase.ALIGN
    v = velocity_toward_goal(pose, goal, speed_m_s=1.0, max_vz=1.0, kp_z=0.22)
    # NED vz is positive down, so descending toward a lower target is positive.
    assert v[2] > 0.0


def test_approach_goal_never_below_min_clearance():
    pose = VehiclePose(x=99.0, y=0.0, z=-5.0, ok=True)
    goal = compute_approach_goal(
        pose,
        (100.0, 0.0, 0.0),
        cruise_alt_m=None,
        descend_range_m=15.0,
        align_to_target=True,
        alt_offset_m=0.0,
        min_clearance_m=2.0,
    )
    assert goal.position_ned[2] == -2.0


def test_retreat_overrides_the_goal():
    pose = VehiclePose(x=99.0, y=0.0, z=-5.0, ok=True)
    goal = compute_approach_goal(
        pose,
        (100.0, 0.0, 0.0),
        cruise_alt_m=30.0,
        descend_range_m=15.0,
        align_to_target=True,
        alt_offset_m=0.0,
        min_clearance_m=2.0,
        retreat_to_ned=(0.0, 0.0, -30.0),
    )
    assert goal.phase is ApproachPhase.RETREAT
    np.testing.assert_allclose(goal.position_ned, [0.0, 0.0, -30.0])


def test_speed_taper_stops_at_the_stopping_distance():
    assert speed_scaled_by_range(2.0, 50.0, stop_range_m=5.0, slow_zone_m=10.0) == 2.0
    assert speed_scaled_by_range(2.0, 5.0, stop_range_m=5.0, slow_zone_m=10.0) == 0.0
    assert speed_scaled_by_range(2.0, 4.0, stop_range_m=5.0, slow_zone_m=10.0) == 0.0
    # Quadratic, so halfway through the slow zone is a quarter of the speed.
    assert speed_scaled_by_range(2.0, 10.0, stop_range_m=5.0, slow_zone_m=10.0) == 0.5
    assert speed_scaled_by_range(2.0, None, stop_range_m=5.0, slow_zone_m=10.0) == 2.0
