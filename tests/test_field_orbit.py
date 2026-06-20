"""Unit tests for field orbit geometry and HUD strings."""

from __future__ import annotations

import math

import pytest

from valiant.autonomy.gcs_hud import format_orbit_status
from valiant.autonomy.orbit_math import (
    advance_arc_progress_m,
    circle_center,
    combined_laps,
    course_yaw_from_velocity,
    forward_entry_ned,
    limit_yaw_step,
    orbit_tangent_yaw,
    orbit_velocity_ned,
    simulate_orbit_path,
    update_lap_progress,
    velocity_toward_ned,
    wrap_pi,
)


def test_wrap_pi():
    assert abs(wrap_pi(math.pi + 0.1) - (-math.pi + 0.1)) < 1e-6


def test_circle_center_clockwise():
    cx, cy = circle_center(0.0, 0.0, 0.0, 5.0, clockwise=True)
    assert abs(cx - 0.0) < 1e-6
    assert abs(cy - 5.0) < 1e-6


def test_circle_center_counter_clockwise():
    cx, cy = circle_center(0.0, 0.0, 0.0, 5.0, clockwise=False)
    assert abs(cx - 0.0) < 1e-6
    assert abs(cy + 5.0) < 1e-6


def test_intent_entry_and_center_from_anchor():
    """Center is placed from actual entry pose + yaw (working geometry)."""
    ax, ay, yaw = 0.0, 0.0, 0.0
    forward_m = 2.0
    radius_m = 5.0
    ix, iy = forward_entry_ned(ax, ay, yaw, forward_m)
    assert abs(ix - 2.0) < 1e-6
    cx, cy = circle_center(ix, iy, yaw, radius_m, clockwise=True)
    assert abs(cy - 5.0) < 1e-6
    # Intent entry vs fixed center at overshoot: actual pose drives center
    cx2, cy2 = circle_center(15.0, 0.0, yaw, radius_m, clockwise=True)
    assert (cx2, cy2) != (cx, cy)


def test_progress_along_heading():
    from valiant.autonomy.orbit_math import progress_along_heading

    assert abs(progress_along_heading(2.0, 0.0, 0.0, 0.0, 0.0) - 2.0) < 1e-6
    assert abs(progress_along_heading(0.0, 2.0, 0.0, 0.0, math.pi / 2) - 2.0) < 1e-6


def test_course_yaw_from_velocity_cardinals():
    assert abs(course_yaw_from_velocity(0.4, 0.0)) < 1e-6
    assert abs(course_yaw_from_velocity(0.0, 0.4) - math.pi / 2) < 1e-6
    assert abs(course_yaw_from_velocity(-0.4, 0.0) - math.pi) < 1e-6


def test_orbit_tangent_yaw_cw_at_south_and_east():
    cx, cy = 0.0, 5.0
    yaw_south = orbit_tangent_yaw(0.0, 0.0, cx, cy, clockwise=True)
    assert abs(yaw_south) < 0.15
    yaw_east = orbit_tangent_yaw(5.0, 5.0, cx, cy, clockwise=True)
    assert abs(yaw_east - math.pi / 2) < 0.15


def test_limit_yaw_step_clamps_rate():
    last = 0.0
    target = math.radians(90.0)
    stepped = limit_yaw_step(target, last, max_rate_rad_s=math.radians(25.0), dt_s=0.05)
    assert abs(stepped - math.radians(1.25)) < 1e-6


def test_course_yaw_matches_orbit_tangent_on_circle():
    cx, cy = 0.0, 5.0
    x, y = 0.0, 0.0
    vn, ve, _ = orbit_velocity_ned(x, y, cx, cy, 5.0, 0.4, 0.0, clockwise=True)
    assert abs(course_yaw_from_velocity(vn, ve) - orbit_tangent_yaw(x, y, cx, cy, clockwise=True)) < 0.05


def test_lap_progress_skipped_when_far_from_radius():
    """Large err_r approach must not instantly complete laps (phi near center)."""
    cx, cy = 2.0, 5.0
    radius_m = 5.0
    # Drone far southwest of circle — not on radius
    x, y = -30.0, -30.0
    err_r = radius_m - math.hypot(x - cx, y - cy)
    assert abs(err_r) > 1.0
    progress = 0.0
    phi_prev = None
    for _ in range(20):
        progress, laps, phi_prev = update_lap_progress(
            x, y, cx, cy, phi_prev, progress, clockwise=True
        )
        x += 0.5
    assert laps < 0.5


def test_orbit_velocity_cw_at_west_of_center():
    """Drone west of center: CW tangent is north (positive vn)."""
    cx, cy = 0.0, 5.0
    x, y = 0.0, 0.0
    vn, ve, err = orbit_velocity_ned(
        x, y, cx, cy, 5.0, 0.4, 0.25, clockwise=True
    )
    assert abs(err) < 0.01
    assert vn > 0.1
    assert abs(ve) < 0.05


def test_orbit_velocity_cw_at_east_of_center():
    """Drone east of center: CW tangent is south (negative vn)."""
    cx, cy = 0.0, 0.0
    x, y = 0.0, 5.0
    vn, ve, err = orbit_velocity_ned(
        x, y, cx, cy, 5.0, 0.4, 0.25, clockwise=True
    )
    assert abs(err) < 0.01
    assert vn < -0.1
    assert abs(ve) < 0.05


def test_orbit_velocity_ccw_at_east_of_center():
    cx, cy = 0.0, 0.0
    x, y = 0.0, 5.0
    vn, ve, err = orbit_velocity_ned(
        x, y, cx, cy, 5.0, 0.4, 0.25, clockwise=False
    )
    assert abs(err) < 0.01
    assert vn > 0.1


def test_orbit_velocity_near_center_keeps_tangential_speed():
    cx, cy = 0.0, 0.0
    vn, ve, _ = orbit_velocity_ned(
        cx, cy, cx, cy, 5.0, 0.4, 0.25, clockwise=True
    )
    assert math.hypot(vn, ve) > 0.2


def test_lap_progress_accumulates_clockwise():
    cx, cy = 0.0, 0.0
    progress = 0.0
    phi_prev = None
    points = [
        (5.0, 0.0),
        (0.0, 5.0),
        (-5.0, 0.0),
        (0.0, -5.0),
        (5.0, 0.0),
    ]
    for x, y in points:
        progress, laps, phi_prev = update_lap_progress(
            x, y, cx, cy, phi_prev, progress, clockwise=True
        )
    assert laps >= 0.9


def test_lap_progress_does_not_complete_instantly():
    cx, cy = 0.0, 0.0
    progress = 0.0
    phi_prev = None
    for x, y in ((5.0, 0.0), (4.9, -0.5)):
        progress, laps, phi_prev = update_lap_progress(
            x, y, cx, cy, phi_prev, progress, clockwise=True
        )
    assert laps < 0.5


def test_simulate_orbit_path_one_lap():
    laps, path, min_r = simulate_orbit_path(
        0.0,
        0.0,
        5.0,
        clockwise=True,
        duration_s=120.0,
    )
    assert laps >= 0.95
    assert min_r > 3.5
    assert len(path) > 100


def test_combined_laps_arc_backup_reaches_one():
    """Moving integration with arc backup completes one lap."""
    cx, cy, radius = 0.0, 5.0, 5.0
    x, y = 0.0, 0.0
    lap_progress = 0.0
    arc_progress_m = 0.0
    phi_prev = None
    dt_s = 0.05
    orbit_speed = 0.4
    radial_kp = 0.25
    for _ in range(int(120.0 / dt_s)):
        vn, ve, _ = orbit_velocity_ned(
            x, y, cx, cy, radius, orbit_speed, radial_kp, clockwise=True
        )
        x += vn * dt_s
        y += ve * dt_s
        lap_progress, _, phi_prev = update_lap_progress(
            x, y, cx, cy, phi_prev, lap_progress, clockwise=True
        )
        arc_progress_m = advance_arc_progress_m(arc_progress_m, vn, ve, dt_s)
        laps = combined_laps(lap_progress, arc_progress_m, radius)
        if laps >= 0.95:
            break
    assert laps >= 0.95


def test_combined_laps_uses_higher_of_angle_and_arc():
    laps_angle = 0.2
    circumference = 2 * math.pi * 5.0
    laps_arc = 0.6
    combined = combined_laps(laps_angle * 2 * math.pi, laps_arc * circumference, 5.0)
    assert combined >= 0.6
    assert combined <= 0.61


def test_velocity_toward_center():
    vn, ve = velocity_toward_ned(0.0, 0.0, 3.0, 4.0, 0.5)
    dist = math.hypot(vn, ve)
    assert dist <= 0.5 + 1e-6
    assert vn > 0 and ve > 0


@pytest.mark.parametrize(
    "phase,lap,target,expected_prefix",
    [
        ("ORBIT", 2.2, 5, "Lap 3/5"),
        ("RETURN_CENTER", 5.0, 5, "Returning"),
        ("STANDBY", 0.0, 5, "Waiting"),
    ],
)
def test_format_orbit_status(phase, lap, target, expected_prefix):
    line = format_orbit_status(phase, lap, target)
    assert line.startswith(expected_prefix.split()[0])
