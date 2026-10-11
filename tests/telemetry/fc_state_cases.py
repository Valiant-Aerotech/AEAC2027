"""Plain asserts for the PX4 packet mapper. No ROS."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "telemetry"))

from telemetry.fc_state import (
    ARMING_STATE_ARMED,
    ARMING_STATE_DISARMED,
    FIX_TYPE_2D,
    FIX_TYPE_3D,
    FIX_TYPE_NONE,
    NAVIGATION_STATE_ACRO,
    NAVIGATION_STATE_ALTCTL,
    NAVIGATION_STATE_MANUAL,
    NAVIGATION_STATE_POSCTL,
    NAVIGATION_STATE_STAB,
    STALE_DEAD_AFTER_S,
    ground_bias_m,
    packet_from_fc,
)

OFFBOARD = 14


def packet(**changes):
    fields = dict(
        uav_id="valiant-1",
        arming_state=ARMING_STATE_ARMED,
        nav_state=OFFBOARD,
        failsafe=False,
        gcs_connection_lost=False,
        manual_control_signal_lost=False,
        lat=47.397,
        lon=8.546,
        alt_amsl_m=530.0,
        eph_m=0.15,
        position_age_s=0.1,
        fix_usable=True,
        fix_type=FIX_TYPE_3D,
        home_alt_m=518.0,
        frame_bias_m=0.0,
        battery_pct=80.0,
        clock=lambda: 1_800_000_000.0,
    )
    fields.update(changes)
    return packet_from_fc(**fields)


def test_modes() -> None:
    assert packet(arming_state=ARMING_STATE_DISARMED, gcs_connection_lost=True).flight_mode == "idle"
    assert packet(arming_state=0).flight_mode == "idle"
    assert packet(failsafe=True, gcs_connection_lost=True).flight_mode == "failsafe"
    assert packet(gcs_connection_lost=True).flight_mode == "link-lost"
    assert packet(manual_control_signal_lost=True).flight_mode == "link-lost"
    assert packet(nav_state=NAVIGATION_STATE_MANUAL).flight_mode == "armed-pilot"
    assert packet(nav_state=NAVIGATION_STATE_ALTCTL).flight_mode == "armed-pilot"
    assert packet(nav_state=NAVIGATION_STATE_POSCTL).flight_mode == "armed-pilot"
    assert packet(nav_state=NAVIGATION_STATE_STAB).flight_mode == "armed-pilot"
    assert packet(nav_state=NAVIGATION_STATE_ACRO).flight_mode == "armed-pilot"
    assert packet(nav_state=OFFBOARD).flight_mode == "armed-automatic"
    assert packet(arming_state=ARMING_STATE_DISARMED).armed is False
    assert packet().armed is True


def test_links_are_independent() -> None:
    lost_gcs = packet(gcs_connection_lost=True, manual_control_signal_lost=False)
    assert lost_gcs.link_quality == 0
    assert lost_gcs.rc_link_quality == 1
    wire = lost_gcs.to_wire()
    assert wire["telemetryLinkStatus"] == 0
    assert wire["rcLinkStatus"] == 1


def test_no_fix_still_returns_a_packet() -> None:
    none = packet(fix_usable=False, fix_type=FIX_TYPE_NONE)
    assert none.accuracy_m == 0.0
    assert none.lat == 47.397
    assert none.gps_valid() is False
    assert packet(fix_type=FIX_TYPE_2D, fix_usable=True).accuracy_m == 0.0
    assert packet(eph_m=0.0).accuracy_m == 0.0
    missing = packet(lat=None, lon=None, eph_m=None, fix_usable=False, fix_type=None)
    assert missing.lat == 0.0 and missing.lon == 0.0
    assert missing.accuracy_m == 0.0


def test_stale_fix() -> None:
    grown = packet(position_age_s=4.0)
    assert grown.accuracy_m == 0.15 + 5.0
    assert grown.lat == 47.397
    dead = packet(position_age_s=STALE_DEAD_AFTER_S)
    assert dead.accuracy_m == 0.0
    assert dead.lat == 47.397


def test_battery_and_home() -> None:
    assert packet(battery_pct=None).battery_pct == -1.0
    assert packet(battery_pct=None).validation_reject_reason() == "battery"
    assert packet(home_alt_m=None).alt_agl_m == 0.0
    assert packet().alt_agl_m == 12.0
    assert packet(frame_bias_m=15.0).alt_agl_m == -3.0
    assert ground_bias_m(518.0, 488.0, on_ground=True) == 30.0
    assert ground_bias_m(518.6, 518.0, on_ground=True) == 0.0
    assert ground_bias_m(533.0, 518.0, on_ground=False) == 0.0


if __name__ == "__main__":
    test_modes()
    test_links_are_independent()
    test_no_fix_still_returns_a_packet()
    test_stale_fix()
    test_battery_and_home()
    print("fc state cases ok")
