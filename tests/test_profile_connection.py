"""Tests for flight profile MAVLink connection selection."""

from __future__ import annotations

from unittest.mock import patch

from valiant.autonomy.flight.profile import (
    mavlink_connection_for_gcs,
    mavlink_connection_for_host,
)

_RPI_LOCAL_CFG = {
    "mavlink": {"connection": "COM5", "rpi_connection": "/dev/ttyAMA0", "baud": 57600},
    "camera": {"source": "rpi_local"},
}


def test_gcs_connection_uses_telemetry_radio_not_pi_uart():
    conn, baud = mavlink_connection_for_gcs(_RPI_LOCAL_CFG)
    assert conn == "COM5"
    assert baud == 57600


def test_host_on_linux_with_rpi_local_uses_uart():
    with patch("valiant.autonomy.flight.profile.sys.platform", "linux"):
        conn, _ = mavlink_connection_for_host(_RPI_LOCAL_CFG)
    assert conn == "/dev/ttyAMA0"


def test_host_on_windows_with_rpi_local_uses_com():
    with patch("valiant.autonomy.flight.profile.sys.platform", "win32"):
        conn, _ = mavlink_connection_for_host(_RPI_LOCAL_CFG)
    assert conn == "COM5"


def test_host_without_rpi_local_uses_connection():
    cfg = {
        "mavlink": {"connection": "tcp:127.0.0.1:5760", "rpi_connection": "/dev/ttyAMA0"},
        "camera": {"source": "sitl"},
    }
    conn, _ = mavlink_connection_for_host(cfg)
    assert conn == "tcp:127.0.0.1:5760"
