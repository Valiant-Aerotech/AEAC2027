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


def _parse_ekf_statustext(low: str) -> tuple[bool, bool]:
    """Return (ekf_active, gps_nav) flags from a lowercased STATUSTEXT line."""
    ekf_active = "ekf3 active" in low
    gps_nav = "ekf3 imu0 is using gps" in low or "ekf3 imu1 is using gps" in low
    return ekf_active, gps_nav


def _ekf_flags_nav_ready(flags: int) -> bool:
    """EKF horizontal velocity + position (relative or absolute)."""
    vel_horiz = mavutil.mavlink.ESTIMATOR_VELOCITY_HORIZ
    pos_horiz = (
        mavutil.mavlink.ESTIMATOR_POS_HORIZ_REL
        | mavutil.mavlink.ESTIMATOR_POS_HORIZ_ABS
    )
    return bool(flags & vel_horiz) and bool(flags & pos_horiz)


def _is_sitl_nav_ready(
    *,
    ekf_active: bool,
    gps_nav: bool,
    gps_fix: int,
    ekf_flags: int,
) -> bool:
    """True when the FC is safe to arm in GUIDED (cold or warm SITL)."""
    if gps_nav:
        return True
    if gps_fix >= 3 and _ekf_flags_nav_ready(ekf_flags):
        return True
    if ekf_active and gps_fix >= 3:
        return True
    return False


def _wait_sitl_ready(master: mavutil.mavfile, timeout_s: float) -> None:
    """Wait for cold-start EKF/GPS before the first arm (avoids first-run arm timeout)."""
    from valiant.common.mavlink import request_message_interval

    request_message_interval(master, mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, 2)
    request_message_interval(master, mavutil.mavlink.MAVLINK_MSG_ID_EKF_STATUS_REPORT, 2)

    deadline = time.time() + timeout_s
    ekf_active = False
    gps_nav = False
    gps_fix = 0
    ekf_flags = 0
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(blocking=True, timeout=1)
        if msg is None:
            continue
        if msg.get_srcSystem() != master.target_system:
            continue
        mtype = msg.get_type()
        if mtype == "STATUSTEXT":
            text = msg.text.strip("\x00")
            if text:
                print(f"[SITL] FC: {text}")
            ekf_hit, gps_hit = _parse_ekf_statustext(text.lower())
            ekf_active = ekf_active or ekf_hit
            gps_nav = gps_nav or gps_hit
        elif mtype == "GPS_RAW_INT":
            gps_fix = max(gps_fix, int(msg.fix_type))
        elif mtype == "EKF_STATUS_REPORT":
            ekf_flags = int(msg.flags)

        if _is_sitl_nav_ready(
            ekf_active=ekf_active,
            gps_nav=gps_nav,
            gps_fix=gps_fix,
            ekf_flags=ekf_flags,
        ):
            time.sleep(0.5)
            print("[SITL] EKF/GPS ready")
            return

    print("[SITL] Warning: EKF/GPS ready not confirmed within timeout")
    raise RuntimeError(
        "SITL EKF/GPS not ready — wait for sim to finish boot or increase sitl.ekf_wait_s"
    )


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


def verify_sitl_motion_ready(
    master: mavutil.mavfile,
    *,
    min_alt_m: float = 2.0,
    require_guided: bool = True,
    sample_s: float = 2.5,
) -> tuple[bool, str]:
    """Return (ready, reason) for velocity-command flight (armed, airborne, GUIDED)."""
    from valiant.common.sitl_physics import drain_vehicle_pose

    deadline = time.time() + sample_s
    pose = drain_vehicle_pose(master)
    armed = False
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(
                type=["HEARTBEAT", "LOCAL_POSITION_NED"],
                blocking=True,
                timeout=0.5,
            )
        if msg is None:
            continue
        if msg.get_srcSystem() != master.target_system:
            continue
        if msg.get_type() == "HEARTBEAT":
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        pose = drain_vehicle_pose(master, pose)

    alt_m = -pose.z if pose.ok else 0.0
    mode = master.flightmode
    if require_guided and mode != "GUIDED":
        return False, f"mode={mode!r}"
    if not armed:
        return False, "not armed"
    if not pose.ok or alt_m < min_alt_m:
        return False, f"alt={alt_m:.1f}m"
    return True, f"GUIDED alt={alt_m:.1f}m"
