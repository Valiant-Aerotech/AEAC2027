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
    TrafficTracks,
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
    up_m_s: float = 0.0,
) -> TrafficMotion:
    lat, lon = shift(north_m, east_m)
    aircraft = TrafficAircraft(name, lat, lon, alt, keepout_radius_m=keepout_radius_m)
    return TrafficMotion(aircraft, north_m_s, east_m_s, age_s, up_m_s)


def test_stationary_east_row_walls_the_buffer_and_steps_away() -> None:
    # 20 m east, 30 m keep-away. The wall is range minus (30 + 10) = -20 m.
    # That is 10 m closer than the keep-away surface (range - 30 = -10).
    row = motion(0.0, 20.0)
    bins = sector_scan(LAT, LON, 45.0, (row,))
    east_bin = bins[18]
    assert abs(east_bin - (20.0 - 40.0)) < 1.0
    assert abs((20.0 - 30.0) - east_bin - 10.0) < 1.0
    assert math.isinf(bins[54])
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert abs(north) < abs(east)
    assert east < -15.0
    assert up == 0.0
    assert math.hypot(north, east) <= 40.0


def test_clear_hover_stays() -> None:
    row = motion(0.0, 80.0)
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert abs(north) < 0.1 and abs(east) < 0.1
    bins = sector_scan(LAT, LON, 45.0, (row,))
    assert abs(bins[18] - (80.0 - (30.0 + BUFFER_M))) < 1.0


def test_closing_row_moves_a_hover_before_the_buffer() -> None:
    # 60 m east and flying west, so a centered hover is inside the lead track
    # while the range is still outside 40 m.
    row = motion(0.0, 60.0, east_m_s=-8.0)
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert math.hypot(north, east) > 1.0
    assert east < 0.0


def test_vertical_gap_blocks_nothing() -> None:
    row = motion(0.0, 20.0, alt=90.0)
    bins = sector_scan(LAT, LON, 45.0, (row,))
    assert all(math.isinf(value) for value in bins)
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert north == 0.0 and east == 0.0


def test_far_row_blocks_nothing() -> None:
    row = motion(0.0, 5_000.0)
    bins = sector_scan(LAT, LON, 45.0, (row,))
    assert all(math.isinf(value) for value in bins)
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert north == 0.0 and east == 0.0


def test_second_buffer_clamps_the_escape() -> None:
    nearer = motion(0.0, 20.0, name="near")
    other = motion(0.0, -50.0, name="far")
    north, east, up = hover_escape(LAT, LON, 45.0, (nearer, other))
    assert math.hypot(north, east) <= 40.0
    assert math.hypot(north, east) > 1.0
    # The naive 20 m west step would still be inside the western buffer.
    assert abs(east - (-20.0)) > 5.0 or abs(north) > 5.0
    end_east = east
    assert math.hypot(north, end_east - 20.0) >= 39.0
    assert math.hypot(north, end_east - (-50.0)) >= 39.0


def test_hover_between_two_rows_steps_out_to_the_side() -> None:
    east_row = motion(0.0, 20.0, name="east")
    west_row = motion(0.0, -20.0, name="west")
    north, east, up = hover_escape(LAT, LON, 45.0, (east_row, west_row))
    assert abs(north) > abs(east)
    assert abs(east) < 5.0
    again_n, again_e, again_up = hover_escape(LAT, LON, 45.0, (east_row, west_row), prefer=(north, east))
    assert again_n == north and again_e == east and again_up == 0.0


def test_climb_away_does_not_move_the_hover() -> None:
    row = motion(0.0, 20.0, alt=90.0, up_m_s=3.0)
    bins = sector_scan(LAT, LON, 45.0, (row,))
    assert all(math.isinf(value) for value in bins)
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert north == 0.0 and east == 0.0


def test_descent_into_the_keep_away_moves_the_hover() -> None:
    # 90 m above, descending 8 m/s, so the next 5 s reaches 50 m and meets us.
    row = motion(0.0, 20.0, alt=90.0, up_m_s=-8.0)
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert math.hypot(north, east) > 1.0
    assert east < 0.0


def test_cornered_hover_climbs_clear() -> None:
    # Buffer is 50 m, so no point inside the 40 m cap is outside it.
    row = motion(0.0, 0.0, keepout_radius_m=40.0)
    north, east, up = hover_escape(LAT, LON, 45.0, (row,))
    assert abs(north) < 0.1 and abs(east) < 0.1
    assert up > 1.0
    again_n, again_e, again_up = hover_escape(LAT, LON, 45.0, (row,), prefer=(north, east, up))
    assert again_n == 0.0 and again_e == 0.0 and again_up == up


def test_cornered_hover_under_the_ceiling_descends() -> None:
    row = motion(0.0, 0.0, alt=90.0, keepout_radius_m=40.0)
    _north, _east, up = hover_escape(LAT, LON, 90.0, (row,))
    assert up < -1.0


def test_tracks_store_vertical_speed() -> None:
    tracks = TrafficTracks()
    high = craft(0.0, 20.0, alt=90.0, name="high")
    tracks.motions((high,), 0.0)
    lower = craft(0.0, 20.0, alt=74.0, name="high")
    motions = tracks.motions((lower,), 2.0)
    assert motions[0].up_m_s < -5.0


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
    test_hover_between_two_rows_steps_out_to_the_side()
    test_climb_away_does_not_move_the_hover()
    test_descent_into_the_keep_away_moves_the_hover()
    test_cornered_hover_climbs_clear()
    test_cornered_hover_under_the_ceiling_descends()
    test_tracks_store_vertical_speed()
    print("deconflict cases ok")
