"""Vehicle pose from MAVLink.

Reading LOCAL_POSITION_NED and ATTITUDE into a :class:`VehiclePose` is the
same job whether the autopilot is a real Cube or ArduPilot SITL, so it belongs
in core rather than in the simulation package. Everything above core polls
pose through here.
"""

from __future__ import annotations

import time

from valiant.core.errors import FlightPreconditionError
from valiant.core.kinematics import VehiclePose
from valiant.core.mavlink import request_sitl_telemetry_streams
from valiant.core.mavlink_io import mavlink_io


def _apply_pose_message(pose: VehiclePose, msg) -> tuple[bool, bool]:
    """Update pose from MAVLink; return (got_position, got_attitude)."""
    got_pos = got_att = False
    mtype = msg.get_type()
    if mtype == "LOCAL_POSITION_NED":
        pose.x = float(msg.x)
        pose.y = float(msg.y)
        pose.z = float(msg.z)
        pose.vx = float(msg.vx)
        pose.vy = float(msg.vy)
        pose.vz = float(msg.vz)
        pose.ok = True
        got_pos = True
    elif mtype == "ATTITUDE":
        pose.roll = float(msg.roll)
        pose.pitch = float(msg.pitch)
        pose.yaw = float(msg.yaw)
        pose.ok = True
        got_att = True
    elif mtype == "GLOBAL_POSITION_INT":
        pose.lat = float(msg.lat) / 1e7
        pose.lon = float(msg.lon) / 1e7
        pose.alt_agl_m = float(msg.relative_alt) / 1000.0
    return got_pos, got_att


def drain_vehicle_pose(master, previous: VehiclePose | None = None) -> VehiclePose:
    """Non-blocking read of LOCAL_POSITION_NED + ATTITUDE; merges with previous sample."""

    pose = VehiclePose()
    if previous is not None:
        pose.x = previous.x
        pose.y = previous.y
        pose.z = previous.z
        pose.roll = previous.roll
        pose.pitch = previous.pitch
        pose.yaw = previous.yaw
        pose.vx = previous.vx
        pose.vy = previous.vy
        pose.vz = previous.vz
        pose.ok = previous.ok
        pose.lat = previous.lat
        pose.lon = previous.lon
        pose.alt_agl_m = previous.alt_agl_m

    target_sys = getattr(master, "target_system", 0)
    with mavlink_io(master):
        while True:
            msg = master.recv_match(
                type=["LOCAL_POSITION_NED", "ATTITUDE", "GLOBAL_POSITION_INT"],
                blocking=False,
            )
            if msg is None:
                break
            if msg.get_srcSystem() != target_sys:
                continue
            _apply_pose_message(pose, msg)
    return pose


def refresh_vehicle_pose(
    master,
    previous: VehiclePose | None = None,
    *,
    block_timeout_s: float = 0.12,
) -> VehiclePose:
    """Latest pose for closed-loop control; waits briefly for a fresh sample."""

    pose = drain_vehicle_pose(master, previous)
    if block_timeout_s <= 0:
        return pose

    target_sys = getattr(master, "target_system", 0)
    deadline = time.time() + block_timeout_s
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(
                type=["LOCAL_POSITION_NED", "ATTITUDE", "GLOBAL_POSITION_INT"],
                blocking=True,
                timeout=min(0.05, deadline - time.time()),
            )
        if msg is None or msg.get_srcSystem() != target_sys:
            continue
        got_pos, _ = _apply_pose_message(pose, msg)
        if got_pos:
            break
    return pose


def wait_vehicle_pose(
    master,
    timeout_s: float = 15.0,
    *,
    need_position: bool = True,
    need_attitude: bool = False,
    previous: VehiclePose | None = None,
) -> VehiclePose:
    """Block until required pose fields arrive (re-requests SITL telemetry streams)."""

    pose = VehiclePose()
    if previous is not None and previous.ok:
        pose.x = previous.x
        pose.y = previous.y
        pose.z = previous.z
        pose.roll = previous.roll
        pose.pitch = previous.pitch
        pose.yaw = previous.yaw
        pose.vx = previous.vx
        pose.vy = previous.vy
        pose.vz = previous.vz
        pose.ok = True
        pose.lat = previous.lat
        pose.lon = previous.lon
        pose.alt_agl_m = previous.alt_agl_m

    has_position = not need_position
    has_attitude = not need_attitude

    request_sitl_telemetry_streams(master)
    target_sys = getattr(master, "target_system", 0)
    with mavlink_io(master):
        while True:
            msg = master.recv_match(
                type=["LOCAL_POSITION_NED", "ATTITUDE", "GLOBAL_POSITION_INT"],
                blocking=False,
            )
            if msg is None:
                break
            if msg.get_srcSystem() != target_sys:
                continue
            got_pos, got_att = _apply_pose_message(pose, msg)
            if got_pos:
                has_position = True
            if got_att:
                has_attitude = True
    if has_position and has_attitude:
        return pose

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if has_position and has_attitude:
            return pose
        with mavlink_io(master):
            msg = master.recv_match(
                type=["LOCAL_POSITION_NED", "ATTITUDE", "GLOBAL_POSITION_INT"],
                blocking=True,
                timeout=0.5,
            )
        if msg is None or msg.get_srcSystem() != target_sys:
            continue
        got_pos, got_att = _apply_pose_message(pose, msg)
        if got_pos:
            has_position = True
        if got_att:
            has_attitude = True

    missing = []
    if need_position and not has_position:
        missing.append("LOCAL_POSITION_NED")
    if need_attitude and not has_attitude:
        missing.append("ATTITUDE")
    raise FlightPreconditionError(
        f"Timed out waiting for {', '.join(missing)} ({timeout_s:.0f}s)",
        crew_message="No pose from FC",
    )
