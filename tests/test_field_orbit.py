"""Unit tests for field orbit geometry and HUD strings."""

from __future__ import annotations

import math

import pytest

from valiant.autonomy.gcs_hud import format_orbit_status
from valiant.autonomy.orbit_math import (
    circle_center,
    orbit_velocity_ned,
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


def test_orbit_velocity_on_circle():
    cx, cy = 0.0, 5.0
    x, y = 0.0, 0.0
    vn, ve, err = orbit_velocity_ned(
        x, y, cx, cy, 5.0, 0.4, 0.25, clockwise=True
    )
    assert abs(err) < 0.01
    assert vn < 0.0
    assert abs(ve) < 0.05


def test_lap_progress_accumulates_clockwise():
    cx, cy = 0.0, 0.0
    progress = 0.0
    phi_prev = None
    points = [
        (5.0, 0.0),
        (0.0, -5.0),
        (-5.0, 0.0),
        (0.0, 5.0),
        (5.0, 0.0),
    ]
    for x, y in points:
        progress, laps, phi_prev = update_lap_progress(
            x, y, cx, cy, phi_prev, progress, clockwise=True
        )
    assert laps >= 0.9


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
