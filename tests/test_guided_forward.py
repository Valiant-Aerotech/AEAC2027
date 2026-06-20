"""Tests for anchor-based forward waypoint driving."""

from __future__ import annotations

import math

import pytest

from valiant.autonomy.guided_motion import GuidedMotionRunner
from valiant.autonomy.orbit_math import forward_entry_ned
from valiant.common.ned_kinematics import VehiclePose


class _FakeMaster:
    def __init__(self, poses: list[VehiclePose]):
        self._poses = list(poses)
        self._idx = 0
        self.target_system = 1
        self.target_component = 1
        self.flightmode = "GUIDED"
        self.mav = self

    def mode_mapping(self) -> dict:
        return {"GUIDED": 4, "LOITER": 5}

    def set_mode(self, _mode: int) -> None:
        pass

    def recv_match(self, *, type, blocking=False, timeout=0.5):
        del type, blocking, timeout
        if self._idx < len(self._poses):
            pose = self._poses[self._idx]
            self._idx += 1
            return _FakeNed(pose)
        return None


class _FakeNed:
    def __init__(self, pose: VehiclePose):
        self.x = pose.x
        self.y = pose.y
        self.z = pose.z
        self.vx = pose.vx
        self.vy = pose.vy
        self.vz = pose.vz
        self._sysid = 1

    def get_srcSystem(self) -> int:
        return self._sysid

    def get_type(self) -> str:
        return "LOCAL_POSITION_NED"


def test_forward_entry_ned_along_north():
    ix, iy = forward_entry_ned(0.0, 0.0, 0.0, 2.0)
    assert abs(ix - 2.0) < 1e-6
    assert abs(iy) < 1e-6


def test_forward_entry_ned_along_east():
    ix, iy = forward_entry_ned(1.0, 1.0, math.pi / 2, 3.0)
    assert abs(ix - 1.0) < 1e-6
    assert abs(iy - 4.0) < 1e-6


def test_drive_to_ned_point_arrives(monkeypatch):
    """Simulated pose sequence reaches waypoint and stops."""
    target_x, target_y = 2.0, 0.0
    poses = [
        VehiclePose(x=0.0, y=0.0, z=-10.0, yaw=0.0, ok=True),
        VehiclePose(x=0.5, y=0.0, z=-10.0, yaw=0.0, ok=True),
        VehiclePose(x=1.5, y=0.0, z=-10.0, yaw=0.0, ok=True),
        VehiclePose(x=1.95, y=0.0, z=-10.0, yaw=0.0, ok=True),
    ]
    master = _FakeMaster(poses)
    cfg = {"field_orbit": {"forward_arrival_m": 0.25, "forward_timeout_s": 5.0}}
    motion = GuidedMotionRunner(master, cfg, log_tag="Test")
    motion.set_last_pose(poses[0])
    monkeypatch.setattr(
        "valiant.autonomy.guided_motion.send_companion_heartbeat",
        lambda _m: None,
    )
    end_x, end_y = motion.drive_to_ned_point(
        target_x,
        target_y,
        label="test forward",
        anchor_xy=(0.0, 0.0),
    )
    assert math.hypot(end_x - target_x, end_y - target_y) <= 0.25
