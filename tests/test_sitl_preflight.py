"""Unit tests for SITL preflight readiness detection."""

from __future__ import annotations

from valiant.autonomy.sitl_preflight import (
    _ekf_flags_nav_ready,
    _is_sitl_nav_ready,
    _parse_ekf_statustext,
)


def test_parse_statustext_gps_nav_implies_ready():
    ekf, gps = _parse_ekf_statustext("ekf3 imu0 is using gps")
    assert not ekf
    assert gps
    assert _is_sitl_nav_ready(ekf_active=False, gps_nav=gps, gps_fix=0, ekf_flags=0)


def test_parse_statustext_ekf_active():
    ekf, gps = _parse_ekf_statustext("ahrs: ekf3 active")
    assert ekf
    assert not gps


def test_ready_from_gps_fix_and_ekf_flags():
    from pymavlink import mavutil

    flags = (
        mavutil.mavlink.ESTIMATOR_VELOCITY_HORIZ
        | mavutil.mavlink.ESTIMATOR_POS_HORIZ_ABS
    )
    assert _ekf_flags_nav_ready(flags)
    assert _is_sitl_nav_ready(
        ekf_active=False,
        gps_nav=False,
        gps_fix=3,
        ekf_flags=flags,
    )


def test_not_ready_without_gps_or_ekf():
    assert not _is_sitl_nav_ready(
        ekf_active=True,
        gps_nav=False,
        gps_fix=0,
        ekf_flags=0,
    )
