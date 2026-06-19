"""MAVLink connection helpers shared across missions."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from pymavlink import mavutil

from valiant.common.mavlink_io import attach_io_lock, mavlink_io

STATUSTEXT_MAX_LEN = 50

_SEVERITY_BY_NAME: dict[str, int] = {
    "emergency": mavutil.mavlink.MAV_SEVERITY_EMERGENCY,
    "alert": mavutil.mavlink.MAV_SEVERITY_ALERT,
    "critical": mavutil.mavlink.MAV_SEVERITY_CRITICAL,
    "error": mavutil.mavlink.MAV_SEVERITY_ERROR,
    "warning": mavutil.mavlink.MAV_SEVERITY_WARNING,
    "notice": mavutil.mavlink.MAV_SEVERITY_NOTICE,
    "info": mavutil.mavlink.MAV_SEVERITY_INFO,
    "debug": mavutil.mavlink.MAV_SEVERITY_DEBUG,
}


@dataclass
class GcsStatustextOptions:
    """How companion STATUSTEXT is emitted for GCS / Mission Planner."""

    severity: int = mavutil.mavlink.MAV_SEVERITY_NOTICE
    debug: bool = False
    sitl: bool = False
    mp_use_autopilot_sysid: bool = False
    sitl_mp_mirror: str | None = None


def parse_statustext_severity(name: str) -> int:
    return _SEVERITY_BY_NAME.get(name.lower(), mavutil.mavlink.MAV_SEVERITY_NOTICE)


def gcs_statustext_options_from_cfg(cfg: dict, *, sitl: bool) -> GcsStatustextOptions:
    gcs = cfg.get("gcs_monitor", {})
    mp_sysid = gcs.get("mp_use_autopilot_sysid", sitl)
    return GcsStatustextOptions(
        severity=parse_statustext_severity(str(gcs.get("statustext_severity", "notice"))),
        debug=bool(gcs.get("debug_statustext", False)),
        sitl=sitl,
        mp_use_autopilot_sysid=bool(mp_sysid),
        sitl_mp_mirror=gcs.get("sitl_mp_mirror") or None,
    )


def encode_statustext(message: str, prefix: str = "") -> bytes:
    """MAVLink2 STATUSTEXT field: up to 50 bytes, null-padded."""
    text = f"{prefix}{message}"[:STATUSTEXT_MAX_LEN]
    raw = text.encode("utf-8", errors="replace")[:STATUSTEXT_MAX_LEN]
    return raw.ljust(STATUSTEXT_MAX_LEN, b"\0")


@dataclass
class MavlinkConnectError(ConnectionError):
    """MAVLink link could not be opened or heartbeat was not received."""

    connection: str
    baud: int
    cause: Exception
    attempts: int = 1
    hints: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.hints:
            self.hints = connection_error_hints(self.connection, self.cause)

    def __str__(self) -> str:
        return (
            f"Could not connect to {self.connection!r} @ {self.baud} baud "
            f"({self.cause})"
        )


def connection_error_hints(connection: str, cause: Exception) -> list[str]:
    """Actionable hints for common MAVLink connection failures."""
    hints: list[str] = []
    cause_s = str(cause).lower()
    conn_l = connection.lower()

    if conn_l.startswith("/dev/") and sys.platform == "win32":
        hints.append(
            "Pi UART paths only work on the Raspberry Pi. From a Windows GCS laptop, "
            "use the telemetry radio COM port."
        )
        hints.append(
            "Example: python tools\\valiant.py gcs verify-safety --connection COM5"
        )
        hints.append("Set COM port in config/rpas.yaml (mavlink.connection).")
    elif conn_l.startswith("/dev/") and (
        "cannot find" in cause_s or "no such file" in cause_s or "not found" in cause_s
    ):
        hints.append(
            "UART device missing. On Pi: FC TELEM wired to GPIO serial, serial enabled in raspi-config."
        )
        hints.append("Or pass --connection with the correct port.")

    if conn_l.startswith("com") or "could not open port" in cause_s:
        hints.append("Check USB telemetry radio is plugged in (Device Manager -> Ports).")
        hints.append("Update config/rpas.yaml mavlink.connection to match (e.g. COM5).")

    if conn_l.startswith("tcp:") or conn_l.startswith("udp"):
        if "refused" in cause_s or "10061" in cause_s or "111" in cause_s:
            hints.append("Start SITL first: .\\tools\\launch_sitl.ps1")
        if "timeout" in cause_s or "timed out" in cause_s or "heartbeat" in cause_s:
            hints.append("No FC heartbeat - is the vehicle powered and the link up?")

    if "permission" in cause_s or "access is denied" in cause_s:
        hints.append("Close Mission Planner or other apps using the same COM port.")

    if not hints:
        hints.append("Pass --connection to override the config default.")

    return hints


def format_mavlink_connect_error(exc: MavlinkConnectError | Exception) -> str:
    """Multi-line user-facing message for a connect failure."""
    if not isinstance(exc, MavlinkConnectError):
        return f"Could not connect: {exc}"

    lines = [
        "Could not connect to flight controller",
        f"  Connection: {exc.connection} @ {exc.baud} baud",
        f"  Reason: {exc.cause}",
    ]
    if exc.attempts > 1:
        lines.append(f"  Attempts: {exc.attempts}")
    for hint in exc.hints:
        lines.append(f"  -> {hint}")
    return "\n".join(lines)


def print_mavlink_connect_error(
    exc: MavlinkConnectError | Exception,
    *,
    prefix: str = "[MAVLink]",
) -> None:
    """Print a friendly connect failure (no traceback)."""
    if isinstance(exc, MavlinkConnectError):
        print(f"{prefix} FAIL: Could not connect to flight controller")
        print(f"  Connection: {exc.connection} @ {exc.baud} baud")
        print(f"  Reason: {exc.cause}")
        if exc.attempts > 1:
            print(f"  Attempts: {exc.attempts}")
        for hint in exc.hints:
            print(f"  -> {hint}")
    else:
        print(f"{prefix} FAIL: {exc}")


def connect(
    connection_string: str,
    baud: int = 57600,
    *,
    wait_heartbeat: bool = True,
    source_system: int = 255,
    source_component: int = 191,
    retries: int = 5,
    retry_delay_s: float = 2.0,
) -> mavutil.mavfile:
    """Open a MAVLink connection.

    Uses source_component=191 (companion computer) for commands and heartbeats.
    """
    import time

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            master = mavutil.mavlink_connection(
                connection_string,
                baud=baud,
                source_system=source_system,
                source_component=source_component,
            )
            if wait_heartbeat:
                master.wait_heartbeat(timeout=15)
            return attach_io_lock(master)
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                print(
                    f"[MAVLink] Connect attempt {attempt}/{retries} failed "
                    f"({exc}); retry in {retry_delay_s}s..."
                )
                time.sleep(retry_delay_s)
    raise MavlinkConnectError(
        connection_string,
        baud,
        last_err,  # type: ignore[arg-type]
        attempts=retries,
    )


def send_statustext(
    master: mavutil.mavfile,
    message: str,
    prefix: str = "",
    *,
    severity: int | None = None,
    debug: bool = False,
) -> None:
    """Send a HUD message (max 50 chars) using the connection's mavlink identity."""
    sev = severity if severity is not None else mavutil.mavlink.MAV_SEVERITY_INFO
    payload = encode_statustext(message, prefix)
    with mavlink_io(master):
        master.mav.statustext_send(sev, payload)
    if debug:
        shown = payload.split(b"\0", 1)[0].decode("utf-8", errors="replace")
        print(f"[GCS] STATUSTEXT sys={master.mav.srcSystem} comp={master.mav.srcComponent} -> {shown!r}")


def _send_statustext_with_identity(
    master: mavutil.mavfile,
    message: str,
    prefix: str,
    *,
    system_id: int,
    component_id: int,
    severity: int,
    debug: bool,
) -> None:
    with mavlink_io(master):
        saved_sys = master.mav.srcSystem
        saved_comp = master.mav.srcComponent
        try:
            master.mav.srcSystem = system_id
            master.mav.srcComponent = component_id
            payload = encode_statustext(message, prefix)
            master.mav.statustext_send(severity, payload)
        finally:
            master.mav.srcSystem = saved_sys
            master.mav.srcComponent = saved_comp
    if debug:
        shown = encode_statustext(message, prefix).split(b"\0", 1)[0].decode(
            "utf-8", errors="replace"
        )
        print(f"[GCS] STATUSTEXT sys={system_id} comp={component_id} -> {shown!r}")


def send_statustext_for_gcs(
    master: mavutil.mavfile,
    message: str,
    prefix: str = "",
    *,
    options: GcsStatustextOptions | None = None,
    mirror: mavutil.mavfile | None = None,
) -> None:
    """Send STATUSTEXT for GCS visibility (companion + optional SITL MP relay path)."""
    opts = options or GcsStatustextOptions()
    send_statustext(
        master,
        message,
        prefix,
        severity=opts.severity,
        debug=opts.debug,
    )
    if opts.sitl and opts.mp_use_autopilot_sysid and master.target_system:
        _send_statustext_with_identity(
            master,
            message,
            prefix,
            system_id=master.target_system,
            component_id=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER,
            severity=opts.severity,
            debug=opts.debug,
        )
    if mirror is not None:
        send_statustext(
            mirror,
            message,
            prefix,
            severity=opts.severity,
            debug=opts.debug,
        )


def request_sys_status_stream(master: mavutil.mavfile, rate_hz: int = 2) -> None:
    """Ask the FC to stream SYS_STATUS (battery_remaining)."""
    with mavlink_io(master):
        master.mav.request_data_stream_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
            rate_hz,
            1,
        )


def request_message_interval(master: mavutil.mavfile, message_id: int, rate_hz: float) -> None:
    """Request a MAVLink message rate (ArduPilot 4.x; replaces legacy DATA_STREAM)."""
    if rate_hz <= 0:
        interval_us = -1
    else:
        interval_us = int(1_000_000 / rate_hz)
    with mavlink_io(master):
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            0,
            float(message_id),
            float(interval_us),
            0,
            0,
            0,
            0,
            0,
        )


def request_guided_telemetry_streams(master: mavutil.mavfile) -> None:
    """LOCAL_POSITION_NED + ATTITUDE for guided velocity and orbit control."""
    request_message_interval(master, mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 20)
    request_message_interval(master, mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 20)
    request_sys_status_stream(master, rate_hz=2)


def request_sitl_telemetry_streams(master: mavutil.mavfile) -> None:
    """Alias for request_guided_telemetry_streams (SITL and field GUIDED)."""
    request_guided_telemetry_streams(master)


def command_yaw_relative(
    master: mavutil.mavfile,
    angle_deg: float,
    *,
    rate_deg_s: float = 25.0,
    clockwise: bool = True,
) -> None:
    """ArduPilot GUIDED yaw via MAV_CMD_CONDITION_YAW (relative heading)."""
    direction = 1.0 if clockwise else -1.0
    with mavlink_io(master):
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            0,
            abs(angle_deg),
            rate_deg_s,
            direction,
            1,  # relative to current heading
            0,
            0,
            0,
        )


def send_companion_heartbeat(master: mavutil.mavfile) -> None:
    """Companion heartbeat (onboard computer, not GCS)."""
    with mavlink_io(master):
        master.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )


def send_gcs_heartbeat(master: mavutil.mavfile) -> None:
    """Legacy GCS heartbeat (avoid during SITL; use send_companion_heartbeat)."""
    with mavlink_io(master):
        master.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )


def send_rtl(master: mavutil.mavfile) -> None:
    """Command return-to-launch via MAV_CMD_NAV_RETURN_TO_LAUNCH."""
    with mavlink_io(master):
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )


def send_land(master: mavutil.mavfile) -> None:
    """Command immediate LAND mode (companion backup when FC safety script absent)."""
    mapping = master.mode_mapping()
    land_id = mapping.get("LAND")
    if land_id is not None:
        with mavlink_io(master):
            master.set_mode(land_id)
        return
    with mavlink_io(master):
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )
