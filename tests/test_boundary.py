"""Competition flight boundary: geometry, advisory behaviour, fence export.

The boundary is deliberately advisory. The flight controller enforces the hard
polygon via FENCE_ACTION; these tests pin the geometry we hand it and the
warnings we give the crew, and assert the module cannot command termination.
"""

from __future__ import annotations

import math

import pytest

from valiant.core.safety import boundary as B
from valiant.core.safety.boundary import (
    HARD_BOUNDARY,
    MAX_ALTITUDE_AGL_M,
    BoundaryMonitor,
    BoundaryStatus,
    FlightBoundary,
    boundary_status_text,
    distance_to_edge_m,
    point_in_polygon,
    polygon_bounds,
    polygon_centroid,
    signed_distance_m,
    write_polygon_file,
)

# A point in the notch cut out of the south-west of the polygon. Inside the
# bounding box, outside the polygon. This is the case a convex hull test fails.
NOTCH = (50.0975, -110.7420)
CENTRE = polygon_centroid()


class _FakeHud:
    def __init__(self):
        self.sent: list[tuple[str, bool]] = []

    def send(self, message, *, force=False):
        self.sent.append((message, force))


# --- The polygon itself ---------------------------------------------------


def test_boundary_has_the_six_appendix_c_vertices():
    assert len(HARD_BOUNDARY) == 6
    # Appendix C Table C1, first and last rows, as printed.
    assert HARD_BOUNDARY[0] == (50.0970884, -110.7328077)
    assert HARD_BOUNDARY[-1] == (50.0971194, -110.7382533)


def test_ceiling_is_the_conops_limit():
    assert MAX_ALTITUDE_AGL_M == 100.0


def test_polygon_is_non_convex():
    """If this ever becomes convex, someone reordered or edited the vertices."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    n = len(HARD_BOUNDARY)
    signs = {
        cross(HARD_BOUNDARY[i], HARD_BOUNDARY[(i + 1) % n], HARD_BOUNDARY[(i + 2) % n]) > 0
        for i in range(n)
    }
    assert len(signs) == 2, "expected a reflex vertex - the polygon has a notch"


def test_centroid_is_inside():
    assert point_in_polygon(*CENTRE)


def test_notch_is_outside_despite_being_in_the_bounding_box():
    lat_min, lon_min, lat_max, lon_max = polygon_bounds()
    assert lat_min <= NOTCH[0] <= lat_max
    assert lon_min <= NOTCH[1] <= lon_max
    assert not point_in_polygon(*NOTCH)


def test_vertices_and_far_points():
    assert not point_in_polygon(51.0, -110.74)
    assert not point_in_polygon(50.10, -111.0)


def test_signed_distance_flips_sign_across_the_edge():
    assert signed_distance_m(*CENTRE) > 0
    assert signed_distance_m(*NOTCH) < 0


def test_distance_to_edge_is_never_negative():
    assert distance_to_edge_m(*CENTRE) > 0
    assert distance_to_edge_m(*NOTCH) > 0


def test_site_is_roughly_a_kilometre_across():
    """Sanity check on the metre conversion, not on the site."""
    lat_min, lon_min, lat_max, lon_max = polygon_bounds()
    height_m = (lat_max - lat_min) * 111_320.0
    width_m = (lon_max - lon_min) * 111_320.0 * math.cos(math.radians(lat_min))
    assert 900 < height_m < 1100
    assert 700 < width_m < 900


# --- Status classification -----------------------------------------------


def test_deep_inside_is_inside():
    check = FlightBoundary().check(*CENTRE, 50.0)
    assert check.status is BoundaryStatus.INSIDE
    assert check.inside
    assert not check.should_stop


def test_near_the_edge_is_a_soft_warning():
    b = FlightBoundary(soft_inset_m=30.0)
    # Walk in from the notch until we are inside but within the inset.
    check = b.check(50.0985, -110.7382, 50.0)
    assert check.status is BoundaryStatus.SOFT_WARNING
    assert check.inside
    assert check.should_stop


def test_outside_is_outside():
    check = FlightBoundary().check(*NOTCH, 50.0)
    assert check.status is BoundaryStatus.OUTSIDE
    assert not check.inside
    assert check.should_stop


def test_above_the_ceiling_is_flagged_even_when_laterally_inside():
    check = FlightBoundary().check(*CENTRE, 120.0)
    assert check.status is BoundaryStatus.ABOVE_CEILING
    assert check.should_stop


def test_approaching_the_ceiling_warns_before_breaching():
    check = FlightBoundary(altitude_margin_m=10.0).check(*CENTRE, 95.0)
    assert check.status is BoundaryStatus.SOFT_WARNING


def test_lateral_breach_outranks_altitude():
    """Outside the polygon is the more urgent fact; report that one."""
    check = FlightBoundary().check(*NOTCH, 150.0)
    assert check.status is BoundaryStatus.OUTSIDE


def test_a_boundary_needs_three_vertices():
    with pytest.raises(ValueError):
        FlightBoundary(polygon=((50.0, -110.0), (50.1, -110.0)))


# --- Advisory only --------------------------------------------------------


def test_module_exposes_no_termination_path():
    """Termination is the flight controller's job, via FENCE_ACTION.

    A second software path to killing the aircraft is a second way to kill it
    by accident. If someone adds one, this test should stop them and send them
    to the module docstring.
    """
    for name in ("on_terminate", "terminate", "trigger_fts", "terminated"):
        assert not hasattr(FlightBoundary, name), f"FlightBoundary.{name} must not exist"
    assert not hasattr(B, "trigger_termination")


def test_check_result_has_no_terminate_flag():
    check = FlightBoundary().check(*NOTCH, 50.0)
    assert not hasattr(check, "terminate")
    assert check.should_stop is True


def test_status_text_fits_the_statustext_limit():
    b = FlightBoundary()
    for lat, lon, alt in [(*CENTRE, 50.0), (50.0985, -110.7382, 50.0), (*CENTRE, 120.0), (*NOTCH, 50.0)]:
        text = boundary_status_text(b.check(lat, lon, alt))
        # 50-char MAVLink payload, minus the "VA: " prefix the reporter adds.
        assert len(text) <= 46, text


# --- The monitor ----------------------------------------------------------


def test_monitor_sends_one_message_per_state_change_not_per_fix():
    hud = _FakeHud()
    m = BoundaryMonitor(hud=hud)
    for _ in range(5):
        m.update(*CENTRE, 50.0)
    assert len(hud.sent) == 1, "repeated identical status must not re-send"


def test_monitor_resends_when_the_status_changes():
    hud = _FakeHud()
    m = BoundaryMonitor(hud=hud)
    m.update(*CENTRE, 50.0)
    m.update(*NOTCH, 50.0)
    m.update(*CENTRE, 50.0)
    assert len(hud.sent) == 3


def test_monitor_forces_the_message_on_a_breach():
    """A warning must not be dropped by the reporter's rate limiter."""
    hud = _FakeHud()
    m = BoundaryMonitor(hud=hud)
    m.update(*CENTRE, 50.0)
    m.update(*NOTCH, 50.0)
    assert hud.sent[0][1] is False
    assert hud.sent[1][1] is True


def test_monitor_counts_breaches():
    m = BoundaryMonitor()
    m.update(*CENTRE, 50.0)
    m.update(*NOTCH, 50.0)
    m.update(*CENTRE, 50.0)
    m.update(*CENTRE, 120.0)
    assert m.breaches == 2
    m.reset()
    assert m.breaches == 0


def test_monitor_works_without_a_hud():
    assert BoundaryMonitor().update(*CENTRE, 50.0).status is BoundaryStatus.INSIDE


# --- Mission Planner export ----------------------------------------------


def test_polygon_file_has_a_header_and_one_line_per_vertex(tmp_path):
    out = write_polygon_file(tmp_path / "b.poly")
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("#")
    assert len(lines) == 1 + len(HARD_BOUNDARY)


def test_polygon_file_does_not_repeat_the_first_vertex(tmp_path):
    """Mission Planner closes the ring itself; a duplicate makes a 7th point."""
    out = write_polygon_file(tmp_path / "b.poly")
    coords = out.read_text(encoding="utf-8").strip().splitlines()[1:]
    assert coords[0] != coords[-1]
    assert len(set(coords)) == len(coords)


def test_polygon_file_round_trips_to_the_same_coordinates(tmp_path):
    out = write_polygon_file(tmp_path / "b.poly")
    parsed = [
        tuple(float(v) for v in line.split())
        for line in out.read_text(encoding="utf-8").strip().splitlines()[1:]
    ]
    for (plat, plon), (lat, lon) in zip(parsed, HARD_BOUNDARY, strict=True):
        assert plat == pytest.approx(lat, abs=1e-7)
        assert plon == pytest.approx(lon, abs=1e-7)


def test_committed_polygon_file_matches_the_coded_boundary(tmp_path):
    """The file we load into Mission Planner must not drift from the code."""
    from pathlib import Path

    committed = Path("config/aeac2027_boundary.poly")
    assert committed.exists(), "run: python tools/valiant.py boundary export"
    fresh = write_polygon_file(tmp_path / "fresh.poly")
    assert committed.read_text(encoding="utf-8") == fresh.read_text(encoding="utf-8")
