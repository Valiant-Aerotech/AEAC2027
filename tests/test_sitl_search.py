"""Tests for SITL SEARCHING reposition logic."""

from __future__ import annotations

import json
import math
from pathlib import Path

from valiant.autonomy.sitl_search import compute_search_motion, scale_approach_speed
from valiant.common.sitl_physics import VehiclePose

SCENE = json.loads(Path("tests/fixtures/sitl_physics_wall.json").read_text(encoding="utf-8"))


def test_search_backs_up_past_wall():
    pose = VehiclePose(x=6.2, y=-0.1, z=-3.1, yaw=0.0, ok=True)
    motion = compute_search_motion(pose, SCENE, wall_standoff_m=1.0)
    assert motion is not None
    assert motion.vn < 0


def test_search_creeps_north_when_far_south_even_if_facing_south():
    pose = VehiclePose(x=-6.0, y=0.0, z=-3.1, yaw=math.pi, ok=True)
    motion = compute_search_motion(pose, SCENE)
    assert motion is not None
    assert motion.vn > 0


def test_approach_speed_zero_at_wall():
    pose = VehiclePose(x=4.1, y=0.0, z=-3.1, ok=True)
    spd = scale_approach_speed(pose, SCENE, 0.25, wall_standoff_m=1.0)
    assert spd == 0.0


def test_approach_speed_predictive_brake():
    pose = VehiclePose(x=3.2, y=0.0, z=-3.1, vx=0.5, ok=True)
    spd = scale_approach_speed(pose, SCENE, 0.25, wall_standoff_m=1.2, slow_zone_m=3.0)
    assert spd == 0.0


def test_altitude_vz_descends_toward_target():
    from valiant.autonomy.sitl_search import compute_altitude_vz

    pose = VehiclePose(x=1.0, y=0.0, z=-3.0, ok=True)
    vz = compute_altitude_vz(pose, SCENE, min_ground_clearance_m=2.0, kp_z=0.25)
    assert vz > 0.0


def test_altitude_vz_holds_clearance_not_target_height():
    from valiant.autonomy.sitl_search import compute_altitude_vz

    pose = VehiclePose(x=1.0, y=0.0, z=-2.0, ok=True)
    vz = compute_altitude_vz(pose, SCENE, min_ground_clearance_m=2.0, kp_z=0.25)
    assert abs(vz) < 1e-6


def test_altitude_vz_climbs_when_too_low():
    from valiant.autonomy.sitl_search import compute_altitude_vz

    pose = VehiclePose(x=3.5, y=0.0, z=-0.8, ok=True)
    vz = compute_altitude_vz(pose, SCENE, min_ground_clearance_m=2.0, kp_z=0.25)
    assert vz < 0.0


def test_reposition_retreats_south_and_climbs():
    from valiant.autonomy.sitl_search import compute_reposition_motion

    pose = VehiclePose(x=3.5, y=-0.5, z=-1.0, ok=True)
    vx, vy, vz, done = compute_reposition_motion(
        pose, retreat_alt_m=2.5, retreat_home_north_m=1.0
    )
    assert vx < 0.0
    assert vz < 0.0
    assert not done
