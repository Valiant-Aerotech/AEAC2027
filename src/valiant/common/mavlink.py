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
