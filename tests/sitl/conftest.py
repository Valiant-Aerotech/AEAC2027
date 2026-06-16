"""SITL integration tests — require ArduPilot SITL on tcp:127.0.0.1:5760."""

from __future__ import annotations

import pytest
from pymavlink import mavutil

SITL_CONNECTION = "tcp:127.0.0.1:5760"


def sitl_heartbeat_available(timeout_s: float = 3.0) -> bool:
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


@pytest.fixture
def sitl_master(sitl_available: bool):
    if not sitl_available:
        pytest.skip("ArduPilot SITL not running on tcp:127.0.0.1:5760")
    master = mavutil.mavlink_connection(SITL_CONNECTION)
    master.wait_heartbeat(timeout=5)
    yield master
    master.close()
