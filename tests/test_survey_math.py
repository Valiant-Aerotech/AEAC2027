"""Offline unit tests for Task 1 survey math (course, window, cluster, report)."""

from __future__ import annotations

import math

from valiant.missions.survey import (
    CourseTimer,
    ReportWindow,
    cluster_fixes,
    parse_report,
    write_report,
)
from valiant.missions.survey.cluster import ClusterPoint, meters_apart
from valiant.missions.survey.report import ClusterRecord
from valiant.missions.survey.window import (
    FLIGHT_WINDOW_S,
    MULTIPLIER_CUTOFF_AFTER_END_S,
)


class _FakeClock:
    """Injectable monotonic clock for timer tests."""

    def __init__(self, t0: float = 0.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_course_timer_advances_with_fake_clock():
    clock = _FakeClock(100.0)
    timer = CourseTimer(time_fn=clock)
    assert timer.elapsed_s() == 0.0
    assert not timer.done

    timer.start()
    clock.advance(12.5)
    assert timer.elapsed_s() == 12.5
    assert not timer.done

    timer.finish()
    clock.advance(50.0)
    assert timer.done
    assert timer.elapsed_s() == 12.5


def test_report_window_open_then_closed():
    clock = _FakeClock(0.0)
    window = ReportWindow(
        flight_window_s=FLIGHT_WINDOW_S,
        grace_after_end_s=MULTIPLIER_CUTOFF_AFTER_END_S,
        time_fn=clock,
    )
    assert not window.in_multiplier_window

    window.start()
    assert window.in_multiplier_window
    assert window.elapsed_s() == 0.0

    clock.advance(FLIGHT_WINDOW_S + MULTIPLIER_CUTOFF_AFTER_END_S)
    assert window.in_multiplier_window

    clock.advance(0.001)
    assert not window.in_multiplier_window


def _offset_point(lat: float, lon: float, north_m: float, east_m: float) -> ClusterPoint:
    """Displace a lat/lon by local north/east metres (equirectangular)."""
    dlat = north_m / 6_371_000.0
    dlon = east_m / (6_371_000.0 * math.cos(math.radians(lat)))
    return ClusterPoint(lat=lat + math.degrees(dlat), lon=lon + math.degrees(dlon))


def test_cluster_five_metres_same_fifteen_apart():
    origin = ClusterPoint(lat=45.0, lon=-75.0, id="a")
    near = _offset_point(origin.lat, origin.lon, north_m=5.0, east_m=0.0)
    near = ClusterPoint(lat=near.lat, lon=near.lon, id="b")
    far = _offset_point(origin.lat, origin.lon, north_m=15.0, east_m=0.0)
    far = ClusterPoint(lat=far.lat, lon=far.lon, id="c")

    assert meters_apart(origin, near) < 10.0
    assert meters_apart(origin, far) > 10.0

    same = cluster_fixes([origin, near])
    assert len(same) == 1
    assert len(same[0]) == 2

    split = cluster_fixes([origin, far])
    assert len(split) == 2
    assert all(len(c) == 1 for c in split)


def test_write_then_parse_round_trip(tmp_path):
    records = [
        ClusterRecord(cluster_id=1, count=2, lat=45.12345678, lon=-75.98765432, tags=("A1", "B2")),
        ClusterRecord(cluster_id=2, count=1, lat=45.2, lon=-75.1, tags=()),
    ]
    path = write_report(tmp_path / "Task_1_team_targets.txt", records)
    assert path.exists()
    assert parse_report(path) == records
