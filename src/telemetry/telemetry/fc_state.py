"""Map PX4 samples to a competition packet. No ROS import.

``packet_from_fc`` stamps ``timestamp`` from ``packet_time()`` so loopback
age checks have a clock. The live worker replaces that stamp when the
websocket write happens. Loopback has no worker.

Accuracy 0 is the invalid-GPS sentinel, not a measured accuracy. Do not
smooth a 0 into a small positive number.
"""

from __future__ import annotations

import math

from telemetry.clock import packet_time
from telemetry.packet import TelemetryPacket

ARMING_STATE_DISARMED = 1
ARMING_STATE_ARMED = 2

NAVIGATION_STATE_MANUAL = 0
NAVIGATION_STATE_ALTCTL = 1
NAVIGATION_STATE_POSCTL = 2
NAVIGATION_STATE_POSITION_SLOW = 6
NAVIGATION_STATE_ALTITUDE_CRUISE = 8
NAVIGATION_STATE_MANUAL_PARKING = 9
NAVIGATION_STATE_ACRO = 10
NAVIGATION_STATE_STAB = 15

FIX_TYPE_NONE = 1
FIX_TYPE_2D = 2
FIX_TYPE_3D = 3

PILOT_NAV_STATES = frozenset(
    {
        NAVIGATION_STATE_MANUAL,
        NAVIGATION_STATE_ALTCTL,
        NAVIGATION_STATE_POSCTL,
        NAVIGATION_STATE_POSITION_SLOW,
        NAVIGATION_STATE_ALTITUDE_CRUISE,
        NAVIGATION_STATE_MANUAL_PARKING,
        NAVIGATION_STATE_ACRO,
        NAVIGATION_STATE_STAB,
    }
)

STALE_GROW_AFTER_S = 3.0
STALE_DEAD_AFTER_S = 5.0
STALE_GROW_M_PER_S = 5.0
GROUND_FRAME_M = 2.0
AGL_WARN_M = -5.0
BATTERY_HELD_AFTER_S = 3.0


def flight_mode(
    arming_state: int,
    nav_state: int,
    *,
    failsafe: bool,
    gcs_connection_lost: bool,
    manual_control_signal_lost: bool,
) -> str:
    """Competition mode. Failsafe wins, then either lost link, then the nav state."""
    if arming_state != ARMING_STATE_ARMED:
        return "idle"
    if failsafe:
        return "failsafe"
    if gcs_connection_lost or manual_control_signal_lost:
        return "link-lost"
    if nav_state in PILOT_NAV_STATES:
        return "armed-pilot"
    return "armed-automatic"


def ground_bias_m(global_alt_m: float, home_alt_m: float, *, on_ground: bool) -> float:
    """Steady AMSL gap to remove, captured once while disarmed on the ground."""
    if not on_ground:
        return 0.0
    gap = global_alt_m - home_alt_m
    if abs(gap) < GROUND_FRAME_M:
        return 0.0
    return gap


def _fix_ok(fix_usable: bool, fix_type: int | None) -> bool:
    return bool(fix_usable) and fix_type is not None and fix_type >= FIX_TYPE_3D


def _accuracy_m(eph_m: float | None, fix_ok: bool, position_age_s: float | None) -> float:
    if not fix_ok or eph_m is None or not math.isfinite(eph_m) or eph_m <= 0.0:
        return 0.0
    if position_age_s is not None and position_age_s >= STALE_DEAD_AFTER_S:
        return 0.0
    if position_age_s is not None and position_age_s > STALE_GROW_AFTER_S:
        return eph_m + STALE_GROW_M_PER_S * (position_age_s - STALE_GROW_AFTER_S)
    return eph_m


def packet_from_fc(
    *,
    uav_id: str,
    arming_state: int,
    nav_state: int,
    failsafe: bool,
    gcs_connection_lost: bool,
    manual_control_signal_lost: bool,
    lat: float | None,
    lon: float | None,
    alt_amsl_m: float | None,
    eph_m: float | None,
    position_age_s: float | None,
    fix_usable: bool,
    fix_type: int | None,
    home_alt_m: float | None,
    frame_bias_m: float = 0.0,
    battery_pct: float | None,
    clock=None,
) -> TelemetryPacket:
    """Build a packet from the latest samples, including a bad GPS fix.

    A missing fix still returns a packet. The client scores it. Accuracy 0
    is the invalid-GPS sentinel.
    """
    mode = flight_mode(
        arming_state,
        nav_state,
        failsafe=failsafe,
        gcs_connection_lost=gcs_connection_lost,
        manual_control_signal_lost=manual_control_signal_lost,
    )
    have_horizontal = lat is not None and lon is not None
    accuracy = _accuracy_m(eph_m, _fix_ok(fix_usable, fix_type), position_age_s)
    if home_alt_m is None or alt_amsl_m is None:
        alt_agl = 0.0
    else:
        alt_agl = alt_amsl_m - home_alt_m - frame_bias_m
    return TelemetryPacket(
        uav_id=uav_id,
        timestamp=packet_time(clock),
        lat=0.0 if lat is None else lat,
        lon=0.0 if lon is None else lon,
        alt_agl_m=alt_agl,
        accuracy_m=0.0 if not have_horizontal else accuracy,
        battery_pct=-1.0 if battery_pct is None else battery_pct,
        flight_mode=mode,
        link_quality=0.0 if gcs_connection_lost else 1.0,
        rc_link_quality=0.0 if manual_control_signal_lost else 1.0,
    )
