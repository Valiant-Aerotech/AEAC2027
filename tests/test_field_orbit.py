"""Unit tests for field orbit geometry and HUD strings."""

from __future__ import annotations

import math

import pytest

from valiant.autonomy.gcs_hud import format_orbit_status
from valiant.autonomy.orbit_math import (
    circle_center,
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
