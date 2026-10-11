"""Plain asserts for closest-approach advice. No ROS."""

from __future__ import annotations

import math
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(_SRC / "mission"))
sys.path.insert(0, str(_SRC / "telemetry"))

from mission.deconflict import advise
from telemetry.traffic import TrafficAircraft

LAT = 50.0
LON = -110.0
METRES = 111_320.0


def shift(north_m: float, east_m: float = 0.0) -> tuple[float, float]:
    lat = LAT + north_m / METRES
    lon = LON + east_m / (METRES * math.cos(math.radians(LAT)))
    return lat, lon


def craft(north_m: float, east_m: float = 0.0, alt: float = 45.0, name: str = "a") -> TrafficAircraft:
    lat, lon = shift(north_m, east_m)
    return TrafficAircraft(name, lat, lon, alt)


def test_empty_traffic_keeps_infinity() -> None:
    advice = advise(LAT, LON, 45.0, ())
    assert advice.nearest_id is None
    assert math.isinf(advice.nearest_m)
    assert advice.hold is False
    assert advice.avoid is False
    assert advice.clear is True


def test_closing_track_avoids_before_entry() -> None:
    advice = advise(LAT, LON, 45.0, (craft(40.0),), speed_m_s=10.0, heading_deg=0.0)
    assert advice.hold is False
    assert advice.avoid is True
    assert advice.approaching == ("a",)


def test_opening_track_does_not_avoid() -> None:
    advice = advise(LAT, LON, 45.0, (craft(-40.0),), speed_m_s=10.0, heading_deg=0.0)
    assert advice.avoid is False
    assert advice.approaching == ()


def test_contact_beyond_outer_range_is_ignored() -> None:
    advice = advise(LAT, LON, 45.0, (craft(200.0),), speed_m_s=10.0, heading_deg=0.0)
    assert advice.avoid is False
    assert advice.nearest_id == "a"
    assert advice.nearest_m > 30.0


def test_already_inside_holds() -> None:
    advice = advise(LAT, LON, 45.0, (craft(0.0),), speed_m_s=10.0, heading_deg=0.0)
    assert advice.hold is True
    assert advice.inside == ("a",)
    assert advice.clear is False


def test_vertical_separation_is_not_a_conflict() -> None:
    advice = advise(LAT, LON, 45.0, (craft(20.0, alt=90.0),), speed_m_s=10.0, heading_deg=0.0)
    assert advice.hold is False
    assert advice.avoid is False


def test_hover_does_not_avoid() -> None:
    advice = advise(LAT, LON, 45.0, (craft(40.0),))
    assert advice.avoid is False
    assert advice.hold is False


def test_abeam_track_does_not_avoid() -> None:
    advice = advise(LAT, LON, 45.0, (craft(0.0, 40.0),), speed_m_s=10.0, heading_deg=0.0)
    assert advice.hold is False
    assert advice.avoid is False


if __name__ == "__main__":
    test_empty_traffic_keeps_infinity()
    test_closing_track_avoids_before_entry()
    test_opening_track_does_not_avoid()
    test_contact_beyond_outer_range_is_ignored()
    test_already_inside_holds()
    test_vertical_separation_is_not_a_conflict()
    test_hover_does_not_avoid()
    test_abeam_track_does_not_avoid()
    print("deconflict cases ok")
