"""ArduCopter SITL preflight: GUIDED, arm, takeoff (single MAVLink session)."""

from __future__ import annotations

import time

from pymavlink import mavutil

from valiant.common.mavlink_io import mavlink_io


def _vehicle_heartbeat(master: mavutil.mavfile, hb) -> bool:
    return hb is not None and hb.get_srcSystem() == master.target_system


def _wait_mode(master: mavutil.mavfile, mode: str, timeout_s: float) -> None:
    want = master.mode_mapping()[mode]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with mavlink_io(master):
            hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if _vehicle_heartbeat(master, hb) and hb.custom_mode == want:
            return
    raise RuntimeError(f"Timed out waiting for mode {mode}")


def _wait_sitl_ready(master: mavutil.mavfile, timeout_s: float) -> None:
    """Wait for cold-start EKF/GPS before the first arm (avoids first-run arm timeout)."""
    deadline = time.time() + timeout_s
    ekf_active = False
    gps_nav = False
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(blocking=True, timeout=1)
        if msg is None:
            continue
        mtype = msg.get_type()
        if mtype == "STATUSTEXT":
            text = msg.text.strip("\x00")
            if text:
                print(f"[SITL] FC: {text}")
            low = text.lower()
            if "ekf3 active" in low:
                ekf_active = True
            if "ekf3 imu0 is using gps" in low or "ekf3 imu1 is using gps" in low:
                gps_nav = True
        elif mtype == "HEARTBEAT" and _vehicle_heartbeat(master, msg):
            if ekf_active and gps_nav:
                time.sleep(0.5)
                print("[SITL] EKF/GPS ready")
                return
    print("[SITL] Warning: EKF/GPS ready not confirmed — will retry arm anyway")


def _arm_copter(master: mavutil.mavfile, *, force: bool = True) -> None:
    """Arm motors; force=True skips pre-arm checks (normal for SITL)."""
    force_param = 21196.0 if force else 0.0
    with mavlink_io(master):
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            force_param,
            0,
            0,
            0,
            0,
            0,
        )


def _wait_armed(master: mavutil.mavfile, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_arm = 0.0
    while time.time() < deadline:
        now = time.time()
        if now - last_arm >= 3.0:
            _arm_copter(master, force=True)
            last_arm = now
        with mavlink_io(master):
            msg = master.recv_match(blocking=True, timeout=2)
        if msg is None:
            continue
        mtype = msg.get_type()
        if mtype == "STATUSTEXT":
            text = msg.text.strip("\x00")
            if text:
                print(f"[SITL] FC: {text}")
        elif mtype == "HEARTBEAT" and _vehicle_heartbeat(master, msg):
            if msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                return
    raise RuntimeError("Timed out waiting for armed state")


def _wait_altitude(master: mavutil.mavfile, min_alt_m: float, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=1)
        if msg is not None and msg.get_srcSystem() == master.target_system:
            alt = -float(msg.z)
            if alt >= min_alt_m:
                print(f"[SITL] Airborne at {alt:.1f}m")
                return
    raise RuntimeError(f"Timed out waiting for takeoff ({min_alt_m}m)")


def arm_guided_takeoff(
    master: mavutil.mavfile,
    *,
    takeoff_alt_m: float = 3.0,
    timeout_s: float = 75.0,
    ekf_wait_s: float = 60.0,
) -> None:
    """GUIDED + arm + NAV_TAKEOFF — required before velocity commands move the copter."""
    print("[SITL] Preflight: waiting for EKF/GPS, then GUIDED, arm, takeoff...")
    _wait_sitl_ready(master, ekf_wait_s)
    mode = "GUIDED"
    if mode not in master.mode_mapping():
        raise RuntimeError(f"Mode {mode!r} not available: {master.mode_mapping()}")
    master.set_mode(master.mode_mapping()[mode])
    _wait_mode(master, mode, timeout_s)
    _wait_armed(master, timeout_s)
    print("[SITL] Armed")

    with mavlink_io(master):
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            takeoff_alt_m,
        )
    _wait_altitude(master, takeoff_alt_m * 0.85, timeout_s)
    print(f"[SITL] Takeoff complete (~{takeoff_alt_m}m)")

    master.set_mode(master.mode_mapping()[mode])
    _wait_mode(master, mode, 10.0)
