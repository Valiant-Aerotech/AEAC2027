"""Offline unit tests for Task 1 SurveyRunner (no SITL)."""

from __future__ import annotations

from pathlib import Path

from valiant.core.safety.boundary import (
    HARD_BOUNDARY,
    BoundaryMonitor,
    FlightBoundary,
    polygon_centroid,
)
from valiant.missions.survey import SurveyRunner, parse_report


def test_survey_runner_record_cluster_write(tmp_path: Path):
    runner = SurveyRunner()
    runner.start_course()
    runner.finish_course()
    assert runner.course.done

    runner.record_fix(50.1000, -110.7400, tag="A1")
    runner.record_fix(50.100005, -110.740005, tag="A1")
    runner.record_fix(50.1020, -110.7420)

    records = runner.build_report_records()
    assert len(records) == 2
    assert records[0].count == 2
    assert "A1" in records[0].tags
    assert records[1].count == 1

    out = runner.write_report(tmp_path / "report.txt")
    parsed = parse_report(out)
    assert len(parsed) == 2
    assert parsed[0].tags == ("A1",)


def test_soft_boundary_triggers_hold_fn():
    holds: list[str] = []

    # Soft inset large enough that centroid is still inside soft band? Use a
    # point near the edge: take hard boundary vertex and nudge inside slightly.
    lat0, lon0 = HARD_BOUNDARY[0]
    # Nudge ~5 m north/east into the polygon soft band (inset 15 m default).
    from valiant.core.geo import offset_lat_lon

    lat, lon = offset_lat_lon(lat0, lon0, 5.0, 5.0)
    # Ensure we are inside hard but within soft inset.
    boundary = BoundaryMonitor(
        FlightBoundary(soft_inset_m=50.0),  # wide soft band so 5 m inset triggers
    )

    runner = SurveyRunner(
        boundary=boundary,
        hold_fn=lambda: holds.append("held"),
    )
    status = runner.tick(lat, lon, 10.0)
    assert status.held
    assert holds == ["held"]

    # Second tick must not re-fire hold.
    status2 = runner.tick(lat, lon, 10.0)
    assert status2.held
    assert holds == ["held"]


def test_run_two_pass_sweep_callable_and_fault():
    class _Motion:
        def __init__(self):
            self.said: list[str] = []

        def say(self, msg, force=False):
            self.said.append(msg)

    motion = _Motion()
    runner = SurveyRunner(motion=motion)

    called: list[int] = []
    runner.run_two_pass_sweep(motion, legs=lambda: called.append(1))
    assert called == [1]
    assert motion.said  # announced SWEEPING via say()

    # Fault path: legs raise; soft hold, no SystemExit.
    runner2 = SurveyRunner(motion=motion)

    def _boom():
        raise RuntimeError("pattern failed")

    try:
        runner2.run_two_pass_sweep(motion, legs=_boom)
    except SystemExit:
        raise AssertionError("SurveyRunner must not raise SystemExit")
    assert runner2._held


def test_inside_centroid_does_not_hold():
    holds: list[str] = []
    lat, lon = polygon_centroid()
    runner = SurveyRunner(
        boundary=BoundaryMonitor(),
        hold_fn=lambda: holds.append("held"),
    )
    status = runner.tick(lat, lon, 10.0)
    assert not status.held
    assert holds == []
