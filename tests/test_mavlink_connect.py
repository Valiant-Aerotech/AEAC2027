"""Tests for MAVLink connection error formatting."""

from __future__ import annotations

from unittest.mock import patch

from valiant.common.mavlink import (
    MavlinkConnectError,
    connection_error_hints,
    format_mavlink_connect_error,
)


def test_connection_hints_pi_path_on_windows():
    cause = OSError(2, "The system cannot find the path specified.")
    with patch("valiant.common.mavlink.sys.platform", "win32"):
        hints = connection_error_hints("/dev/ttyAMA0", cause)
    assert any("GCS laptop" in h for h in hints)
    assert any("COM5" in h for h in hints)


def test_connection_hints_pi_path_on_linux():
    cause = OSError(2, "No such file or directory")
    with patch("valiant.common.mavlink.sys.platform", "linux"):
        hints = connection_error_hints("/dev/ttyAMA0", cause)
    assert any("raspi-config" in h for h in hints)


def test_connection_hints_com_port_failure():
    cause = Exception("could not open port 'COM99'")
    hints = connection_error_hints("COM99", cause)
    assert any("Device Manager" in h for h in hints)


def test_connection_hints_sitl_tcp_refused():
    cause = ConnectionRefusedError(10061, "connection refused")
    hints = connection_error_hints("tcp:127.0.0.1:5760", cause)
    assert any("launch_sitl" in h for h in hints)


def test_mavlink_connect_error_includes_hints():
    exc = MavlinkConnectError(
        "/dev/ttyAMA0",
        57600,
        OSError(2, "No such file"),
        attempts=5,
    )
    text = format_mavlink_connect_error(exc)
    assert "57600" in text
    assert "Attempts: 5" in text
    assert "->" in text


def test_mavlink_connect_error_str():
    exc = MavlinkConnectError("COM5", 57600, OSError("access denied"))
    assert "COM5" in str(exc)
    assert "57600" in str(exc)
