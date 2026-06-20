"""Tests for SITL pose polling (drain / wait / refresh)."""

from __future__ import annotations

from valiant.common.ned_kinematics import VehiclePose
from valiant.common.sitl_physics import (
    drain_vehicle_pose,
    refresh_vehicle_pose,
    wait_vehicle_pose,
)


class _FakeMsg:
    def __init__(self, mtype: str, **fields):
        self._type = mtype
        for key, val in fields.items():
            setattr(self, key, val)

    def get_type(self) -> str:
        return self._type

    def get_srcSystem(self) -> int:
        return 1


class _FakeMaster:
    def __init__(self, messages: list[_FakeMsg]):
        self._messages = list(messages)
        self.target_system = 1

    def recv_match(self, *, type, blocking=False, timeout=0.5):
        del type, timeout
        if not blocking and not self._messages:
            return None
        if not self._messages:
            return None
        return self._messages.pop(0)


def _ned_msg(x: float, y: float = 0.0, z: float = -10.0) -> _FakeMsg:
    return _FakeMsg(
        "LOCAL_POSITION_NED",
        x=x,
        y=y,
        z=z,
        vx=0.0,
        vy=0.0,
        vz=0.0,
    )


def test_wait_vehicle_pose_updates_position_with_previous_ok(monkeypatch):
    """Regression: previous.ok must not skip draining new LOCAL_POSITION_NED."""
    monkeypatch.setattr(
        "valiant.common.mavlink.request_sitl_telemetry_streams",
        lambda _master: None,
    )
    previous = VehiclePose(x=2.0, y=0.0, z=-10.0, ok=True)
    master = _FakeMaster([_ned_msg(2.5, 1.0)])

    pose = wait_vehicle_pose(master, timeout_s=1.0, need_position=True, previous=previous)

    assert pose.ok
    assert abs(pose.x - 2.5) < 1e-6
    assert abs(pose.y - 1.0) < 1e-6


def test_refresh_vehicle_pose_drains_inbox():
    previous = VehiclePose(x=0.0, y=0.0, z=-10.0, ok=True)
    master = _FakeMaster([_ned_msg(3.0, 4.0), _ned_msg(5.0, 6.0)])

    pose = refresh_vehicle_pose(master, previous, block_timeout_s=0.0)

    assert abs(pose.x - 5.0) < 1e-6
    assert abs(pose.y - 6.0) < 1e-6


def test_refresh_vehicle_pose_blocks_for_fresh_sample():
    previous = VehiclePose(x=0.0, y=0.0, z=-10.0, ok=True)
    master = _FakeMaster([_ned_msg(2.0, 1.0)])

    pose = refresh_vehicle_pose(master, previous, block_timeout_s=0.2)

    assert abs(pose.x - 2.0) < 1e-6
    assert abs(pose.y - 1.0) < 1e-6


def test_drain_vehicle_pose_keeps_previous_when_inbox_empty():
    previous = VehiclePose(x=1.0, y=2.0, z=-10.0, ok=True)
    master = _FakeMaster([])

    pose = drain_vehicle_pose(master, previous)

    assert abs(pose.x - 1.0) < 1e-6
    assert abs(pose.y - 2.0) < 1e-6
