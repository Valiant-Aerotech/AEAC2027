"""Flight profile overlays for indoor/outdoor field tuning."""

from __future__ import annotations

from valiant.autonomy.flight.profile import apply_flight_profile
from valiant.common.config import load_config


def test_indoor_profile_sets_guided_nogps():
    cfg = apply_flight_profile(load_config(), "indoor")
    flight = cfg.get("flight", {})
    assert flight.get("profile") == "indoor"
    assert flight.get("require_gps") is False
    assert flight.get("mode") == "GUIDED_NOGPS"
    assert cfg.get("camera", {}).get("source") == "rpi_local"
    assert cfg.get("safety", {}).get("geofence_abort") is False


def test_outdoor_profile_tunes_cv_and_nav():
    cfg = apply_flight_profile(load_config(), "outdoor")
    flight = cfg.get("flight", {})
    assert flight.get("profile") == "outdoor"
    assert flight.get("mode") == "GUIDED"
    cv = cfg.get("cv", {})
    assert cv.get("hsv_min_area_px") == 400
    nav = cfg.get("auto_nav", {})
    assert nav.get("side_clearance_m") == 1.2
    assert nav.get("kd_x") == 0.0018


def test_vivi_outdoor_mission_profile_enables_spray_and_standby():
    cfg = apply_flight_profile(load_config("vivi"), "vivi_outdoor_mission")
    flight = cfg.get("flight", {})
    assert flight.get("mode") == "GUIDED"
    assert flight.get("require_gps") is True
    assert cfg.get("camera", {}).get("source") == "rpi_local"
    assert cfg.get("spray", {}).get("method") == "MAVLINK_SERVO"
    mission = cfg.get("mission", {})
    assert mission.get("pilot_standby") is True
    assert mission.get("loiter_on_complete") is True
