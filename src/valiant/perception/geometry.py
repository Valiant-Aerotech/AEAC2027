"""Camera-ray geometry: pixels to bearings, ranges, and ground coordinates."""

from __future__ import annotations

import math

import numpy as np

from valiant.core.geo import offset_lat_lon
from valiant.core.kinematics import VehiclePose, rot_body_from_ned
from valiant.perception.types import Detection, GroundFix


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
    cos_y, sin_y = math.cos(y_angle), math.sin(y_angle)
    cos_z, sin_z = math.cos(z_angle), math.sin(z_angle)
    ray = np.array([cos_y * cos_z, sin_y * cos_z, sin_z], dtype=float)
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
    return slant_m * math.cos(elev_rad), slant_m * math.sin(elev_rad)


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


def vertical_margin_m(
    detection: Detection,
    frame_h: int,
    slant_m: float | None,
    *,
    vfov_deg: float,
) -> float | None:
    """Metric room between the detection and the nearest horizontal frame edge."""
    if slant_m is None or slant_m <= 0 or frame_h <= 0:
        return None
    margin_px = min(detection.cy, frame_h - detection.cy)
    fraction = margin_px / (frame_h / 2.0)
    vertical_span_m = slant_m * math.tan(math.radians(vfov_deg / 2.0))
    return vertical_span_m * fraction


def vz_from_altitude_error(altitude_error_m: float | None, *, kp: float, max_vz: float) -> float:
    """NED vz from altitude error (positive error = climb = negative vz)."""
    if altitude_error_m is None:
        return 0.0
    return max(-max_vz, min(max_vz, -kp * altitude_error_m))


# --- Ground projection -------------------------------------------------------
#
# This is the core of the Task 1 herd survey: turn a deer sitting at some pixel
# in a downward-looking frame into a latitude and longitude we can cluster and
# report. It is the same ray-plane intersection the 2026 building survey used
# against vertical wall planes (see reference/task1_building_survey/), but the
# ground plane is the easier case because it is always horizontal.


def ray_to_ground_ned(
    ray_body: np.ndarray,
    pose: VehiclePose,
    *,
    ground_z_ned: float = 0.0,
) -> np.ndarray | None:
    """Intersect a body-frame ray with a horizontal plane, in NED.

    Returns the NED point, or None when the ray points level or upward and so
    never reaches the ground.
    """
    if not pose.ok:
        return None
    r_bn = rot_body_from_ned(pose.roll, pose.pitch, pose.yaw)
    ray_ned = r_bn @ np.asarray(ray_body, dtype=float)
    down = float(ray_ned[2])
    # NED z is positive down, so a descending ray needs a positive z component.
    if down <= 1e-6:
        return None
    # Height of the aircraft above the plane.
    height = ground_z_ned - pose.z
    if height <= 0:
        return None
    scale = height / down
    return np.array([pose.x, pose.y, pose.z], dtype=float) + ray_ned * scale


def project_to_ground(
    detection: Detection,
    pose: VehiclePose,
    *,
    frame_w: int,
    frame_h: int,
    hfov_deg: float,
    vfov_deg: float,
    gimbal_pitch_deg: float = 0.0,
    home_lat: float,
    home_lon: float,
    ground_z_ned: float = 0.0,
) -> GroundFix | None:
    """Project a pixel detection onto the ground and convert to lat/lon.

    ``home_lat``/``home_lon`` are the origin of the vehicle's LOCAL NED frame,
    which for ArduPilot is the EKF origin (normally the arming position).
    """
    ray_cam = pixel_to_unit_ray(
        detection.cx, detection.cy, frame_w, frame_h,
        hfov_deg=hfov_deg, vfov_deg=vfov_deg,
    )
    ray_body = camera_ray_to_body(ray_cam, gimbal_pitch_deg)
    point = ray_to_ground_ned(ray_body, pose, ground_z_ned=ground_z_ned)
    if point is None:
        return None
    lat, lon = offset_lat_lon(home_lat, home_lon, float(point[0]), float(point[1]))
    return GroundFix(
        lat=lat,
        lon=lon,
        alt_agl_m=-float(point[2]),
        accuracy_m=ground_fix_accuracy_m(pose, frame_h, vfov_deg=vfov_deg),
        label=detection.label,
        text=detection.text,
        confidence=detection.confidence,
    )


def ground_fix_accuracy_m(
    pose: VehiclePose,
    frame_h: int,
    *,
    vfov_deg: float,
    pixel_error: float = 4.0,
) -> float | None:
    """Rough horizontal error of a ground projection, from one pixel of slop.

    Error grows linearly with altitude, which is why the 10 m clustering rule
    gets harder the higher we fly.
    """
    if frame_h <= 0 or not pose.ok:
        return None
    altitude = -pose.z
    if altitude <= 0:
        return None
    m_per_px = 2.0 * altitude * math.tan(math.radians(vfov_deg / 2.0)) / frame_h
    return m_per_px * pixel_error
