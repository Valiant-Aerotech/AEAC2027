"""ArduCopter SITL preflight: GUIDED, arm, takeoff (single MAVLink session)."""

from __future__ import annotations

import math
import time

from pymavlink import mavutil

from valiant.core.mavlink_io import mavlink_io
from valiant_mav.mode import (
    ensure_guided,
    ensure_guided as ensure_sitl_guided,
    flight_mode_from_heartbeat as _flight_mode_from_heartbeat,
)
from valiant_mav.takeoff import (
    _ekf_flags_nav_ready,
    _is_sitl_nav_ready,
    _parse_ekf_statustext,
    arm_guided_takeoff,
    wait_altitude_settled,
    wait_ekf_ready as _wait_sitl_ready,
)

__all__ = [
    "arm_guided_takeoff",
    "ensure_guided",
    "ensure_sitl_guided",
    "verify_sitl_motion_ready",
    "wait_altitude_settled",
    "wait_for_guided_trigger",
]


def _vehicle_heartbeat(master: mavutil.mavfile, hb) -> bool:
    return hb is not None and hb.get_srcSystem() == master.target_system


def _current_gps_fix(master: mavutil.mavfile) -> int:
    fix = 0
    deadline = time.time() + 0.5
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(type="GPS_RAW_INT", blocking=True, timeout=0.2)
        if msg is not None and msg.get_srcSystem() == master.target_system:
            fix = max(fix, int(msg.fix_type))
    return fix


def wait_for_guided_trigger(
    master: mavutil.mavfile,
    *,
    min_alt_m: float,
    alt_tolerance_m: float = 0.35,
    require_armed: bool = True,
    require_gps: bool = True,
    min_gps_fix: int = 3,
    poll_s: float = 0.2,
    on_standby=None,
) -> tuple[float, float, float, float]:
    """Block until pilot selects GUIDED at target altitude.

    Returns (x0, y0, z0, yaw0) snapshot at trigger.
    """
    from valiant.core.pose import drain_vehicle_pose

    print(f"[Orbit] Standby: arm, climb to ~{min_alt_m:.0f} m, select GUIDED on RC")
    while True:
        with mavlink_io(master):
            hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=poll_s)
        armed = False
        mode = master.flightmode or "UNKNOWN"
        if hb is not None and _vehicle_heartbeat(master, hb):
            armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            mode = _flight_mode_from_heartbeat(master, hb)
        pose = drain_vehicle_pose(master)
        alt_m = -pose.z if pose.ok else 0.0
        if on_standby is not None:
            on_standby(mode=mode, armed=armed, alt_m=alt_m, pose=pose)
        if require_armed and not armed:
            time.sleep(poll_s)
            continue
        if mode != "GUIDED":
            time.sleep(poll_s)
            continue
        if require_gps and _current_gps_fix(master) < min_gps_fix:
            time.sleep(poll_s)
            continue
        if not pose.ok or alt_m < min_alt_m - alt_tolerance_m:
            time.sleep(poll_s)
            continue
        if pose.ok:
            print(
                f"[Orbit] GUIDED trigger at alt={alt_m:.1f} m "
                f"yaw={math.degrees(pose.yaw):.0f} deg"
            )
            return pose.x, pose.y, pose.z, pose.yaw
        time.sleep(poll_s)


def verify_sitl_motion_ready(
    master: mavutil.mavfile,
    *,
    min_alt_m: float = 2.0,
    require_guided: bool = True,
    sample_s: float = 4.0,
) -> tuple[bool, str]:
    """Return (ready, reason) for velocity-command flight (armed, airborne, GUIDED)."""
    from valiant.core.pose import drain_vehicle_pose

    deadline = time.time() + sample_s
    pose = drain_vehicle_pose(master)
    armed = False
    mode = "UNKNOWN"
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(
                type=["HEARTBEAT", "LOCAL_POSITION_NED"],
                blocking=True, timeout=0.5,
            )
        if msg is None:
            continue
        if msg.get_srcSystem() != master.target_system:
            continue
        if msg.get_type() == "HEARTBEAT":
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            mode = _flight_mode_from_heartbeat(master, msg)
        pose = drain_vehicle_pose(master, pose)

    alt_m = -pose.z if pose.ok else 0.0
    if not armed:
        return False, "not armed"
    if not pose.ok or alt_m < min_alt_m:
        return False, f"alt={alt_m:.1f}m"
    if require_guided and mode != "GUIDED":
        if mode == "UNKNOWN":
            return True, f"airborne alt={alt_m:.1f}m (mode pending)"
        return False, f"mode={mode!r}"
    return True, f"GUIDED alt={alt_m:.1f}m"
