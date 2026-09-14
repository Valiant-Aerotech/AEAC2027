"""SITL integration tests - require ArduPilot SITL on tcp:127.0.0.1:5760."""

from __future__ import annotations

import socket

import pytest
from pymavlink import mavutil

from valiant.core.config import load_config
from valiant.core.flight.preflight import _wait_sitl_ready, arm_guided_takeoff, verify_sitl_motion_ready

SITL_HOST = "127.0.0.1"
SITL_PORT = 5760
SITL_CONNECTION = f"tcp:{SITL_HOST}:{SITL_PORT}"
_EKF_BOOT_WAIT_S = 90.0


def sitl_port_open(timeout_s: float = 1.0) -> bool:
    """Cheap TCP probe before touching pymavlink.

    ``mavutil.mavlink_connection`` on a TCP URL retries the connect for a long
    time when nothing is listening, which used to wedge a plain ``pytest`` run
    for minutes. A socket probe fails in milliseconds.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex((SITL_HOST, SITL_PORT)) == 0


def sitl_heartbeat_available(timeout_s: float = 3.0) -> bool:
    if not sitl_port_open():
        return False
    try:
        master = mavutil.mavlink_connection(SITL_CONNECTION)
        master.wait_heartbeat(timeout=timeout_s)
        master.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def sitl_available() -> bool:
    return sitl_heartbeat_available()


@pytest.fixture(scope="session")
def sitl_master(sitl_available: bool):
    """Single shared MAVLink connection kept open for all SITL tests."""
    if not sitl_available:
        pytest.skip("ArduPilot SITL not running on tcp:127.0.0.1:5760")
    master = mavutil.mavlink_connection(SITL_CONNECTION)
    master.wait_heartbeat(timeout=10)
    try:
        _wait_sitl_ready(master, _EKF_BOOT_WAIT_S)
    except RuntimeError as exc:
        master.close()
        pytest.skip(str(exc))

    cfg = load_config()
    takeoff_alt = float(cfg.get("sitl", {}).get("takeoff_alt_m", 5.0))
    preflight_timeout = float(cfg.get("sitl", {}).get("preflight_timeout_s", 75.0))
    ready, reason = verify_sitl_motion_ready(master, min_alt_m=takeoff_alt * 0.85, sample_s=5.0)
    if not ready:
        try:
            arm_guided_takeoff(
                master,
                takeoff_alt_m=takeoff_alt,
                timeout_s=preflight_timeout,
                ekf_wait_s=10.0,
            )
        except RuntimeError as exc:
            master.close()
            pytest.skip(f"SITL preflight failed: {exc}")
    else:
        print(f"[SITL conftest] Session ready ({reason})")

    yield master
    master.close()
