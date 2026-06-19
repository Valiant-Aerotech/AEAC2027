"""Camera-ray 3D geometry for metric reconstruction."""

from __future__ import annotations

import math

import numpy as np

from valiant.autonomy.packets import TargetHit
from valiant.common.ned_kinematics import rot_body_from_ned
from valiant.common.ned_kinematics import VehiclePose


def pixel_to_unit_ray(
    cx: int,
    cy: int,
    frame_w: int,
    frame_h: int,
    *,
    hfov_deg: float,
    vfov_deg: float,
) -> np.ndarray:
    """Unit ray in camera frame (+X forward, +Y right, +Z down)."""
    half_h = math.radians(hfov_deg / 2.0)
    half_v = math.radians(vfov_deg / 2.0)
    nx = (float(cx) - frame_w / 2.0) / max(frame_w / 2.0, 1.0)
    ny = (float(cy) - frame_h / 2.0) / max(frame_h / 2.0, 1.0)
    y_angle = nx * half_h
    z_angle = ny * half_v
    cy, sy = math.cos(y_angle), math.sin(y_angle)
    cz, sz = math.cos(z_angle), math.sin(z_angle)
    ray = np.array([cy * cz, sy * cz, sz], dtype=float)
    n = float(np.linalg.norm(ray))
    return ray / max(n, 1e-9)


def rot_camera_from_body(gimbal_pitch_deg: float) -> np.ndarray:
    """Pitch camera about body Y; positive = look down."""
    a = math.radians(gimbal_pitch_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def camera_ray_to_body(ray_cam: np.ndarray, gimbal_pitch_deg: float) -> np.ndarray:
    r_cb = rot_camera_from_body(gimbal_pitch_deg)
    return r_cb @ np.asarray(ray_cam, dtype=float)


def ray_angles_deg(ray: np.ndarray) -> tuple[float, float]:
    """Return (azimuth_deg, elevation_deg); elevation positive = below horizon."""
    x, y, z = (float(ray[0]), float(ray[1]), float(ray[2]))
    forward = max(x, 1e-6)
    azimuth = math.degrees(math.atan2(y, forward))
    elevation = math.degrees(math.atan2(z, forward))
    return azimuth, elevation


def decompose_slant_range(slant_m: float, ray_body: np.ndarray) -> tuple[float, float]:
    """Return (horizontal_range_m, vertical_offset_m down-positive in body)."""
    _, elevation = ray_angles_deg(ray_body)
    elev_rad = math.radians(elevation)
    horizontal = slant_m * math.cos(elev_rad)
    vertical = slant_m * math.sin(elev_rad)
    return horizontal, vertical


def altitude_error_from_ray(
    slant_m: float,
    ray_body: np.ndarray,
    *,
    pixel_offset_y: float | None = None,
    frame_h: int | None = None,
    vfov_deg: float = 52.0,
) -> float:
    """Estimate signed altitude miss from ray elevation (positive = climb needed)."""
    _, elevation = ray_angles_deg(ray_body)
    if pixel_offset_y is not None and frame_h is not None and frame_h > 0:
        norm_y = pixel_offset_y / (frame_h / 2.0)
        vertical_m = slant_m * math.tan(math.radians(vfov_deg / 2.0)) * norm_y
        return -vertical_m
    return -slant_m * math.sin(math.radians(elevation))


def altitude_error_from_pose(
    pose: VehiclePose,
    target_ned: tuple[float, float, float],
    *,
    alt_offset_m: float = 0.0,
) -> float:
    """Ground-truth altitude error from NED positions."""
    target_alt = -float(target_ned[2]) + alt_offset_m
    camera_alt = -pose.z
    return target_alt - camera_alt


def estimate_vertical_clearance(
    hit: TargetHit,
    frame_h: int,
    slant_m: float | None,
    *,
    vfov_deg: float,
) -> float | None:
    if slant_m is None or slant_m <= 0 or frame_h <= 0:
        return None
    margin_px = min(hit.cy, frame_h - hit.cy)
    fraction = margin_px / (frame_h / 2.0)
    half_vfov_rad = math.radians(vfov_deg / 2.0)
    vertical_span_m = slant_m * math.tan(half_vfov_rad)
    return vertical_span_m * fraction


def metric_vz_from_altitude_error(altitude_error_m: float | None, *, kp: float, max_vz: float) -> float:
    """NED vz from altitude error (positive error = climb = negative vz)."""
    if altitude_error_m is None:
        return 0.0
    vz = -kp * altitude_error_m
    return max(-max_vz, min(max_vz, vz))
