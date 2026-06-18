"""Unit tests for SITL motion stack."""

from __future__ import annotations

import json
from pathlib import Path

from valiant.autonomy.sitl_motion import (
    RULE_BACKOFF,
    RULE_FOLLOW,
    RULE_HOLD,
    RULE_SEARCH,
    SitlMotionStack,
    search_yaw_rate,
)
from valiant.autonomy.packets import MetricPacket
from valiant.common.sitl_physics import VehiclePose

SCENE = json.loads(Path("tests/fixtures/sitl_physics_wall.json").read_text(encoding="utf-8"))
CFG = {
    "sitl": {
        "backoff_m": 1.5,
        "wall_standoff_m": 1.2,
        "search_speed": 0.10,
        "creep_speed": 0.10,
        "max_north_m": 6.0,
        "max_east_m": 2.0,
        "search_yaw_rate": 0.35,
    },
    "metric_recon": {"fire_distance_m": 0.8},
}


def test_backoff_when_past_wall():
    stack = SitlMotionStack(CFG)
    pose = VehiclePose(x=4.5, y=0.0, z=-3.0, ok=True)
    cmd = stack.decide(
        state="SEARCHING",
        pose=pose,
        scene=SCENE,
        has_target=False,
        metric=None,
        approach_speed=0.2,
    )
    assert cmd is not None
    assert cmd.rule == RULE_BACKOFF
    assert cmd.vx is not None and cmd.vx < 0


def test_aiming_allows_fire_standoff_inside_backoff_zone():
    """AIMING may hold inside backoff_m so fire range is reachable."""
    stack = SitlMotionStack(CFG)
    pose = VehiclePose(x=3.8, y=0.0, z=-1.1, ok=True)
    metric = MetricPacket(
        target_px=(320, 240),
        pixel_offset=(0.0, 0.0),
        distance_m=0.85,
    )
    cmd = stack.decide(
        state="AIMING",
        pose=pose,
        scene=SCENE,
        has_target=True,
        metric=metric,
        approach_speed=0.1,
    )
    assert cmd is not None
    assert cmd.rule != RULE_BACKOFF
    assert cmd.rule in (RULE_FOLLOW, RULE_HOLD)


def test_follow_when_target_visible():
    stack = SitlMotionStack(CFG)
    pose = VehiclePose(x=1.0, y=0.0, z=-3.0, ok=True)
    metric = MetricPacket(
        target_px=(320, 240),
        pixel_offset=(0.0, 0.0),
        distance_m=2.5,
    )
    cmd = stack.decide(
        state="APPROACHING",
        pose=pose,
        scene=SCENE,
        has_target=True,
        metric=metric,
        approach_speed=0.2,
    )
    assert cmd is not None
    assert cmd.rule == RULE_FOLLOW
    assert cmd.approach_speed is not None and cmd.approach_speed > 0


def test_search_yaw_scan_without_scene():
    stack = SitlMotionStack(CFG)
    pose = VehiclePose(x=0.0, y=0.0, z=-3.0, ok=True)
    cmd = stack.decide(
        state="SEARCHING",
        pose=pose,
        scene=None,
        has_target=False,
        metric=None,
        approach_speed=0.2,
    )
    assert cmd is not None
    assert cmd.rule == RULE_SEARCH
    assert cmd.yaw_rate is not None
    assert abs(cmd.yaw_rate) <= CFG["sitl"]["search_yaw_rate"] + 1e-6


def test_search_yaw_rate_oscillates():
    assert search_yaw_rate(0.0, rate=0.35) == 0.0
    assert abs(search_yaw_rate(2.0, rate=0.35, period_s=8.0)) > 0.1


def test_approaching_descends_to_target_altitude():
    stack = SitlMotionStack(
        {
            **CFG,
            "sitl": {
                **CFG["sitl"],
                "cruise_alt_m": 5.0,
                "altitude_kp": 0.22,
                "max_vz": 0.14,
            },
        }
    )
    pose = VehiclePose(x=2.0, y=0.0, z=-5.0, ok=True)
    metric = MetricPacket(
        target_px=(320, 240),
        pixel_offset=(0.0, 0.0),
        distance_m=2.5,
    )
    cmd = stack.decide(
        state="APPROACHING",
        pose=pose,
        scene=SCENE,
        has_target=True,
        metric=metric,
        approach_speed=0.14,
    )
    assert cmd is not None
    assert cmd.rule == RULE_FOLLOW
    assert cmd.vz is not None and cmd.vz > 0.0


def test_geofence_limits_east_drift():
    stack = SitlMotionStack(CFG)
    pose = VehiclePose(x=2.0, y=3.0, z=-3.0, yaw=0.0, ok=True)
    stack.reset_search()
    cmd = stack.decide(
        state="SEARCHING",
        pose=pose,
        scene=SCENE,
        has_target=False,
        metric=None,
        approach_speed=0.2,
    )
    assert cmd is not None
    assert cmd.rule == RULE_SEARCH
    assert cmd.vy is not None
    assert cmd.vy * pose.y < 0 or abs(cmd.vy) < 1e-6
