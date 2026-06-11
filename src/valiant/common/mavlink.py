"""MAVLink connection helpers shared across missions."""

from __future__ import annotations

from pymavlink import mavutil


def connect(
    connection_string: str,
    baud: int = 57600,
    *,
    wait_heartbeat: bool = True,
    source_system: int = 1,
    source_component: int = 191,
) -> mavutil.mavfile:
    """Open a MAVLink connection.

    Uses source_component=191 (companion computer) so STATUSTEXT appears
    in Mission Planner HUD.
    """
    master = mavutil.mavlink_connection(
        connection_string,
        baud=baud,
        source_system=source_system,
        source_component=source_component,
    )
    if wait_heartbeat:
        master.wait_heartbeat()
    return master


def send_statustext(master: mavutil.mavfile, message: str, prefix: str = "") -> None:
    """Send a HUD message (max 50 chars)."""
    text = f"{prefix}{message}"[:50].encode()
    master.mav.statustext_send(mavutil.mavlink.MAV_SEVERITY_INFO, text)


def request_sys_status_stream(master: mavutil.mavfile, rate_hz: int = 2) -> None:
    """Ask the FC to stream SYS_STATUS (battery_remaining)."""
    master.mav.request_data_stream_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
        rate_hz,
        1,
    )


def send_rtl(master: mavutil.mavfile) -> None:
    """Command return-to-launch via MAV_CMD_NAV_RETURN_TO_LAUNCH."""
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
