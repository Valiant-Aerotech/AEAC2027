"""SITL pose reading and 3D target projection for physics-linked synthetic camera."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class VehiclePose:
    """Latest vehicle state in LOCAL NED (metres, radians)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    ok: bool = False


def pwm_to_gimbal_pitch_deg(
    pwm: int,
    *,
    pwm_min: int = 1000,
    pwm_max: int = 2000,
    pwm_neutral: int = 1500,
    pitch_up_deg: float = 25.0,
    pitch_down_deg: float = 60.0,
) -> float:
    """Positive pitch_deg = camera pitched down from body forward axis."""
    if pwm >= pwm_neutral:
        span = max(pwm_max - pwm_neutral, 1)
        return pitch_down_deg * (pwm - pwm_neutral) / span
    span = max(pwm_neutral - pwm_min, 1)
    return -pitch_up_deg * (pwm_neutral - pwm) / span


def gimbal_pitch_deg_to_pwm(
    pitch_deg: float,
    *,
    pwm_min: int = 1000,
    pwm_max: int = 2000,
    pwm_neutral: int = 1500,
    pitch_up_deg: float = 25.0,
    pitch_down_deg: float = 60.0,
) -> int:
    if pitch_deg >= 0:
        span = max(pwm_max - pwm_neutral, 1)
        pwm = pwm_neutral + (pitch_deg / max(pitch_down_deg, 1e-3)) * span
    else:
        span = max(pwm_neutral - pwm_min, 1)
        pwm = pwm_neutral + (pitch_deg / max(pitch_up_deg, 1e-3)) * span
    return int(max(pwm_min, min(pwm_max, round(pwm))))


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
    r_bn = _rot_body_from_ned(pose.roll, pose.pitch, pose.yaw)
    return r_bn.T @ rel_ned


def active_targets(targets: list[dict]) -> list[dict]:
    """Targets not yet marked extinguished in the physics scenario."""
    return [t for t in targets if not t.get("extinguished")]


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
    """Closest non-extinguished target (3D distance)."""
    return nearest_target_ned(pose, targets, active_only=True)


def target_display_color(spec: dict) -> tuple[int, int, int]:
    if spec.get("extinguished"):
        c = spec.get("extinguished_color", [80, 200, 100])
        return tuple(int(x) for x in c)
    return tuple(spec.get("color", [180, 50, 180]))


def _rot_body_from_ned(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx


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
    r_bn = _rot_body_from_ned(pose.roll, pose.pitch, pose.yaw)
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


def drain_vehicle_pose(master, previous: VehiclePose | None = None) -> VehiclePose:
    """Non-blocking read of LOCAL_POSITION_NED + ATTITUDE; merges with previous sample."""
    from valiant.common.mavlink_io import mavlink_io

    pose = VehiclePose()
    if previous is not None:
        pose.x = previous.x
        pose.y = previous.y
        pose.z = previous.z
        pose.roll = previous.roll
        pose.pitch = previous.pitch
        pose.yaw = previous.yaw
        pose.vx = previous.vx
        pose.vy = previous.vy
        pose.vz = previous.vz
        pose.ok = previous.ok

    target_sys = getattr(master, "target_system", 0)
    with mavlink_io(master):
        while True:
            msg = master.recv_match(type=["LOCAL_POSITION_NED", "ATTITUDE"], blocking=False)
            if msg is None:
                break
            if msg.get_srcSystem() != target_sys:
                continue
            mtype = msg.get_type()
            if mtype == "LOCAL_POSITION_NED":
                pose.x = float(msg.x)
                pose.y = float(msg.y)
                pose.z = float(msg.z)
                pose.vx = float(msg.vx)
                pose.vy = float(msg.vy)
                pose.vz = float(msg.vz)
                pose.ok = True
            elif mtype == "ATTITUDE":
                pose.roll = float(msg.roll)
                pose.pitch = float(msg.pitch)
                pose.yaw = float(msg.yaw)
                pose.ok = True
    return pose
