"""Tests for 3D metric geometry."""

from __future__ import annotations

import math

import numpy as np

from valiant.autonomy.metric_recon.geometry_3d import (
    altitude_error_from_pose,
    camera_ray_to_body,
    decompose_slant_range,
    pixel_to_unit_ray,
    ray_angles_deg,
)
from valiant.common.ned_kinematics import VehiclePose


def test_pixel_ray_forward():
    ray = pixel_to_unit_ray(320, 240, 640, 480, hfov_deg=66.0, vfov_deg=52.0)
    assert ray[0] > 0.9


def test_decompose_slant_horizontal_shorter():
    ray = np.array([1.0, 0.0, 0.5])
    ray /= np.linalg.norm(ray)
    horiz, vert = decompose_slant_range(2.0, ray)
    assert horiz < 2.0
    assert vert > 0.0


def test_altitude_error_from_pose():
    pose = VehiclePose(x=0.0, y=0.0, z=-5.0, ok=True)
    target = (1.0, 0.0, -1.1)
    err = altitude_error_from_pose(pose, target, alt_offset_m=-0.15)
    assert err < 0.0


def test_gimbal_pitch_rotates_ray():
    ray_cam = pixel_to_unit_ray(320, 240, 640, 480, hfov_deg=66.0, vfov_deg=52.0)
    body_level = camera_ray_to_body(ray_cam, 0.0)
    body_down = camera_ray_to_body(ray_cam, 30.0)
    assert not np.allclose(body_level, body_down)
