"""Projection of world-fixed targets into the simulated camera, plus gimbal PWM math."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from valiant.core.kinematics import VehiclePose, rot_body_from_ned


def body_elevation_deg(rel_body: np.ndarray) -> float:
    """Elevation angle to point (positive = target below horizon in body frame)."""
    forward = float(rel_body[0])
    if forward < 0.1:
        return 45.0
    return math.degrees(math.atan2(float(rel_body[2]), forward))


def relative_target_body(pose: VehiclePose, target_ned: tuple[float, float, float]) -> np.ndarray:
    rel_ned = np.array(
        [
            target_ned[0] - pose.x,
            target_ned[1] - pose.y,
            target_ned[2] - pose.z,
        ],
        dtype=float,
    )
    r_bn = rot_body_from_ned(pose.roll, pose.pitch, pose.yaw)
    return r_bn.T @ rel_ned


def active_targets(targets: list[dict]) -> list[dict]:
    """Targets the mission has not yet marked done."""
    return [t for t in targets if not t.get("done")]


def nearest_target_ned(
    pose: VehiclePose, targets: list[dict], *, active_only: bool = False
) -> tuple[float, float, float] | None:
    pool = active_targets(targets) if active_only else targets
    best: tuple[float, float, float] | None = None
    best_d = float("inf")
    for spec in pool:
        pos = spec.get("position_ned")
        if not pos or len(pos) < 3:
            continue
        tx, ty, tz = float(pos[0]), float(pos[1]), float(pos[2])
        d = (tx - pose.x) ** 2 + (ty - pose.y) ** 2 + (tz - pose.z) ** 2
        if d < best_d:
            best_d = d
            best = (tx, ty, tz)
    return best


def nearest_active_target_ned(
    pose: VehiclePose, targets: list[dict]
) -> tuple[float, float, float] | None:
    """Closest outstanding target (3D distance)."""
    return nearest_target_ned(pose, targets, active_only=True)


def target_display_color(spec: dict) -> tuple[int, int, int]:
    if spec.get("done"):
        return tuple(int(x) for x in spec.get("done_color", [80, 200, 100]))
    return tuple(spec.get("color", [60, 90, 170]))


def _rot_camera_from_body(gimbal_pitch_deg: float) -> np.ndarray:
    """Pitch camera about body Y (right); positive = look down."""
    a = math.radians(gimbal_pitch_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


@dataclass
class ProjectedTarget:
    cx: int
    cy: int
    bbox_w: int
    bbox_h: int
    depth_m: float
    visible: bool


def project_target_ned(
    target_ned: tuple[float, float, float],
    pose: VehiclePose,
    *,
    gimbal_pitch_deg: float,
    target_diameter_m: float,
    frame_w: int,
    frame_h: int,
    hfov_deg: float,
    vfov_deg: float,
    min_depth_m: float = 0.35,
) -> ProjectedTarget | None:
    """Project a world-fixed NED point into the forward gimballed camera."""
    rel_ned = np.array(
        [
            target_ned[0] - pose.x,
            target_ned[1] - pose.y,
            target_ned[2] - pose.z,
        ],
        dtype=float,
    )
    r_bn = rot_body_from_ned(pose.roll, pose.pitch, pose.yaw)
    rel_body = r_bn.T @ rel_ned
    rel_cam = _rot_camera_from_body(gimbal_pitch_deg) @ rel_body

    depth_m = float(rel_cam[0])
    if depth_m < min_depth_m:
        return None

    fx = frame_w / (2.0 * math.tan(math.radians(hfov_deg / 2.0)))
    fy = frame_h / (2.0 * math.tan(math.radians(vfov_deg / 2.0)))
    cx = frame_w / 2.0 + (rel_cam[1] / depth_m) * fx
    cy = frame_h / 2.0 + (rel_cam[2] / depth_m) * fy

    angular_d = target_diameter_m / max(depth_m, 0.1)
    bbox_w = int(max(angular_d * fx, 12))
    bbox_h = bbox_w

    margin = max(bbox_w, bbox_h)
    visible = (
        -margin <= cx <= frame_w + margin
        and -margin <= cy <= frame_h + margin
    )
    return ProjectedTarget(
        cx=int(round(cx)),
        cy=int(round(cy)),
        bbox_w=bbox_w,
        bbox_h=bbox_h,
        depth_m=depth_m,
        visible=visible,
    )
