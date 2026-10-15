"""Plain asserts for closest-approach advice. No ROS."""

from __future__ import annotations

import math
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(_SRC / "mission"))
sys.path.insert(0, str(_SRC / "telemetry"))

from mission.deconflict import (
    BUFFER_M,
    TrafficMotion,
    advise,
    hover_escape,
    sector_scan,
)
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


def motion(
    north_m: float,
    east_m: float = 0.0,
    alt: float = 45.0,
    name: str = "a",
    north_m_s: float = 0.0,
    east_m_s: float = 0.0,
    age_s: float = 0.0,
    keepout_radius_m: float = 30.0,
) -> TrafficMotion:
    lat, lon = shift(north_m, east_m)
    aircraft = TrafficAircraft(name, lat, lon, alt, keepout_radius_m=keepout_radius_m)
    return TrafficMotion(aircraft, north_m_s, east_m_s, age_s)


def test_stationary_east_row_walls_the_buffer_and_steps_away() -> None:
    # 20 m east, 30 m keep-away. The wall is range minus (30 + 10) = -20 m.
    # That is 10 m closer than the keep-away surface (range - 30 = -10).
    row = motion(0.0, 20.0)
    bins = sector_scan(LAT, LON, 45.0, (row,))
    east_bin = bins[18]
    assert abs(east_bin - (20.0 - 40.0)) < 1.0
    assert abs((20.0 - 30.0) - east_bin - 10.0) < 1.0
    assert math.isinf(bins[54])
    north, east = hover_escape(LAT, LON, 45.0, (row,))
    assert abs(north) < 2.5
    assert abs(east - (-20.0)) < 1.5


def test_clear_hover_stays() -> None:
    row = motion(0.0, 80.0)
    north, east = hover_escape(LAT, LON, 45.0, (row,))
    assert abs(north) < 0.1 and abs(east) < 0.1
    bins = sector_scan(LAT, LON, 45.0, (row,))
    assert abs(bins[18] - (80.0 - (30.0 + BUFFER_M))) < 1.0


def test_closing_row_moves_a_hover_before_the_buffer() -> None:
    # 60 m east and flying west, so a centered hover is inside the lead track
    # while the range is still outside 40 m.
    row = motion(0.0, 60.0, east_m_s=-8.0)
    north, east = hover_escape(LAT, LON, 45.0, (row,))
    assert math.hypot(north, east) > 1.0
    assert east < 0.0


def test_vertical_gap_blocks_nothing() -> None:
    row = motion(0.0, 20.0, alt=90.0)
    bins = sector_scan(LAT, LON, 45.0, (row,))
    assert all(math.isinf(value) for value in bins)
    north, east = hover_escape(LAT, LON, 45.0, (row,))
    assert north == 0.0 and east == 0.0


def test_far_row_blocks_nothing() -> None:
    row = motion(0.0, 5_000.0)
    bins = sector_scan(LAT, LON, 45.0, (row,))
    assert all(math.isinf(value) for value in bins)
    north, east = hover_escape(LAT, LON, 45.0, (row,))
    assert north == 0.0 and east == 0.0


def test_second_buffer_clamps_the_escape() -> None:
    nearer = motion(0.0, 20.0, name="near")
    other = motion(0.0, -50.0, name="far")
    north, east = hover_escape(LAT, LON, 45.0, (nearer, other))
    assert math.hypot(north, east) <= 40.0
    assert math.hypot(north, east) > 1.0
    # The naive 20 m west step would still be inside the western buffer.
    assert abs(east - (-20.0)) > 5.0 or abs(north) > 5.0
    end_east = east
    assert math.hypot(north, end_east - 20.0) >= 39.0
    assert math.hypot(north, end_east - (-50.0)) >= 39.0


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
    test_stationary_east_row_walls_the_buffer_and_steps_away()
    test_clear_hover_stays()
    test_closing_row_moves_a_hover_before_the_buffer()
    test_vertical_gap_blocks_nothing()
    test_far_row_blocks_nothing()
    test_second_buffer_clamps_the_escape()
    print("deconflict cases ok")
