"""NED ceiling constraint tests."""

from __future__ import annotations

import numpy as np

from valiant.common.ned_kinematics import VehiclePose, apply_ceiling_constraint, ceiling_z_ned


def test_ceiling_z_from_wall_z_top():
    scene = {"wall": {"z_top": -3.0}}
    assert ceiling_z_ned(scene) == -3.0


def test_apply_ceiling_constraint_stops_climb():
    pose = VehiclePose(z=-2.7, ok=True)
    v = np.array([0.1, 0.0, -0.1])
    out = apply_ceiling_constraint(v, pose, ceiling_z=-3.0, standoff_m=0.5)
    assert out[2] == 0.0


def test_apply_ceiling_constraint_allows_descent():
    pose = VehiclePose(z=-2.7, ok=True)
    v = np.array([0.0, 0.0, 0.1])
    out = apply_ceiling_constraint(v, pose, ceiling_z=-3.0, standoff_m=0.5)
    assert out[2] == 0.1
