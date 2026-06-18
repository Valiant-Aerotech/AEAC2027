"""MAVLink connection helpers shared across missions."""

from __future__ import annotations

from pymavlink import mavutil

from valiant.common.mavlink_io import attach_io_lock


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

    Uses source_component=191 (companion computer) so STATUSTEXT appears
    in Mission Planner HUD.
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
    raise last_err  # type: ignore[misc]


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


def request_message_interval(master: mavutil.mavfile, message_id: int, rate_hz: float) -> None:
    """Request a MAVLink message rate (ArduPilot 4.x; replaces legacy DATA_STREAM)."""
    if rate_hz <= 0:
        interval_us = -1
    else:
        interval_us = int(1_000_000 / rate_hz)
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


def request_sitl_telemetry_streams(master: mavutil.mavfile) -> None:
    """LOCAL_POSITION_NED + ATTITUDE for physics maps and guided velocity."""
    request_message_interval(master, mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 20)
    request_message_interval(master, mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 20)
    request_sys_status_stream(master, rate_hz=2)


def send_gcs_heartbeat(master: mavutil.mavfile) -> None:
    """Companion/GCS heartbeat — use source_system=255 so we are not the autopilot."""
    from valiant.common.mavlink_io import mavlink_io

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
