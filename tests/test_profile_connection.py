"""Tests for flight profile MAVLink connection selection."""

from __future__ import annotations

import sys

from valiant.autonomy.flight.profile import (
    mavlink_connection_for_gcs,
    mavlink_connection_for_host,
)


def test_gcs_connection_uses_telemetry_radio_not_pi_uart():
    cfg = {
        "mavlink": {"connection": "COM5", "rpi_connection": "/dev/ttyAMA0"},
        "camera": {"source": "rpi_local"},
    }
    conn, baud = mavlink_connection_for_gcs(cfg)
    assert conn == "COM5"
    assert baud == 57600


def test_host_on_linux_with_rpi_local_uses_uart():
    cfg = {
        "mavlink": {"connection": "COM5", "rpi_connection": "/dev/ttyAMA0", "baud": 57600},
        "camera": {"source": "rpi_local"},
    }
    if sys.platform.startswith("linux"):
        conn, _ = mavlink_connection_for_host(cfg)
        assert conn == "/dev/ttyAMA0"
    else:
        conn, _ = mavlink_connection_for_host(cfg)
        assert conn == "COM5"


def test_host_without_rpi_local_uses_connection():
    cfg = {
        "mavlink": {"connection": "tcp:127.0.0.1:5760", "rpi_connection": "/dev/ttyAMA0"},
        "camera": {"source": "sitl"},
    }
    conn, _ = mavlink_connection_for_host(cfg)
    assert conn == "tcp:127.0.0.1:5760"
