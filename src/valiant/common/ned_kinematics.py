"""LOCAL NED kinematics: rotations, distances, and 3D velocity planning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

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


class ApproachPhase(str, Enum):
    CRUISE = "cruise"
    ALIGN = "align"
    RETREAT = "retreat"


@dataclass(frozen=True)
class ApproachGoal:
    """Desired NED position for velocity steering."""

    position_ned: np.ndarray
    phase: ApproachPhase = ApproachPhase.ALIGN


def alt_m_from_z(z: float) -> float:
    """Altitude above NED origin (metres); ArduPilot z is positive down."""
    return -float(z)


def z_from_alt_m(alt_m: float) -> float:
    return -float(alt_m)


def ned_position(pose: VehiclePose) -> np.ndarray:
    return np.array([pose.x, pose.y, pose.z], dtype=float)


def relative_ned(pose: VehiclePose, point_ned: tuple[float, float, float] | np.ndarray) -> np.ndarray:
    p = np.asarray(point_ned, dtype=float)
    return p - ned_position(pose)


def distance_3d(pose: VehiclePose, point_ned: tuple[float, float, float] | np.ndarray) -> float:
    return float(np.linalg.norm(relative_ned(pose, point_ned)))


def distance_horizontal(pose: VehiclePose, point_ned: tuple[float, float, float] | np.ndarray) -> float:
    rel = relative_ned(pose, point_ned)
    return float(math.hypot(rel[0], rel[1]))


def rot_body_from_ned(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Rotation matrix mapping NED vector to body frame (R_bn)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx


def ned_to_body_vector(pose: VehiclePose, v_ned: np.ndarray) -> np.ndarray:
    r_bn = rot_body_from_ned(pose.roll, pose.pitch, pose.yaw)
    return r_bn.T @ np.asarray(v_ned, dtype=float)


def body_to_ned_vector(pose: VehiclePose, v_body: np.ndarray) -> np.ndarray:
    r_bn = rot_body_from_ned(pose.roll, pose.pitch, pose.yaw)
    return r_bn @ np.asarray(v_body, dtype=float)


def ned_to_body_velocity(
    pose: VehiclePose, vn: float, ve: float, vz: float = 0.0
) -> tuple[float, float, float]:
    """Transform NED velocity to body frame (full attitude rotation)."""
    v_body = ned_to_body_vector(pose, np.array([vn, ve, vz], dtype=float))
    return float(v_body[0]), float(v_body[1]), float(v_body[2])


def wall_north_m(scene: dict[str, Any]) -> float | None:
    wall = scene.get("wall")
    if not wall:
        return None
    return float(wall.get("x_m", 5.0))


def compute_fire_standoff_north_m(
    scene: dict[str, Any],
    fire_distance_m: float,
    *,
    wall_margin_m: float = 0.0,
) -> float | None:
    """North (x) coordinate to hold for spray: wall plane minus fire standoff."""
    wall_x = wall_north_m(scene)
    if wall_x is None:
        return None
    return wall_x - fire_distance_m - wall_margin_m


def compute_approach_goal(
    pose: VehiclePose,
    target_ned: tuple[float, float, float],
    scene: dict[str, Any] | None,
    *,
    cruise_alt_m: float | None,
    descent_wall_range_m: float,
    align_to_target: bool,
    alt_offset_m: float,
    min_clearance_m: float,
    retreat: bool = False,
    retreat_alt_m: float = 5.0,
    retreat_home_north_m: float = 1.0,
    lane_center_east_m: float = 0.0,
) -> ApproachGoal:
    tx, ty, tz = (float(target_ned[0]), float(target_ned[1]), float(target_ned[2]))
    target_alt_m = alt_m_from_z(tz) + alt_offset_m

    if retreat:
        goal = np.array(
            [retreat_home_north_m, lane_center_east_m, z_from_alt_m(retreat_alt_m)],
            dtype=float,
        )
        return ApproachGoal(goal, ApproachPhase.RETREAT)

    wall_x = wall_north_m(scene) if scene else None
    wall_range = (wall_x - pose.x) if wall_x is not None else None
    descend = wall_range is not None and wall_range <= descent_wall_range_m

    if align_to_target or descend:
        desired_alt_m = max(target_alt_m, min_clearance_m)
        phase = ApproachPhase.ALIGN
    elif cruise_alt_m is not None:
        desired_alt_m = max(cruise_alt_m, min_clearance_m)
        phase = ApproachPhase.CRUISE
    else:
        desired_alt_m = max(target_alt_m, min_clearance_m)
        phase = ApproachPhase.ALIGN

    goal = np.array([tx, ty, z_from_alt_m(desired_alt_m)], dtype=float)
    return ApproachGoal(goal, phase)


def velocity_toward_goal(
    pose: VehiclePose,
    goal: ApproachGoal,
    *,
    speed_m_s: float,
    max_vz: float,
    kp_z: float | None = None,
    min_clearance_m: float = 1.0,
    settle_m: float = 0.12,
) -> np.ndarray:
    """Unit-vector NED velocity toward goal with vz clamp and optional P settle."""
    if not pose.ok:
        return np.zeros(3, dtype=float)

    rel = goal.position_ned - ned_position(pose)
    dist = float(np.linalg.norm(rel))
    if dist < 0.05:
        return np.zeros(3, dtype=float)

    if kp_z is not None and abs(rel[2]) < settle_m * 3.0:
        current_alt_m = alt_m_from_z(pose.z)
        if current_alt_m < min_clearance_m - 0.05:
            err = z_from_alt_m(min_clearance_m) - pose.z
            vz = max(-max_vz, min(0.0, kp_z * err))
            return np.array([0.0, 0.0, vz], dtype=float)
        err_z = rel[2]
        if abs(err_z) < settle_m:
            vn = ve = 0.0
            vz = 0.0
        else:
            unit = rel / dist
            scale = speed_m_s
            vn = unit[0] * scale
            ve = unit[1] * scale
            vz = kp_z * err_z
        return _clamp_vz(np.array([vn, ve, vz], dtype=float), max_vz)

    unit = rel / dist
    v = unit * speed_m_s
    return _clamp_vz(v, max_vz)


def _clamp_vz(v_ned: np.ndarray, max_vz: float) -> np.ndarray:
    out = v_ned.copy()
    out[2] = float(max(-max_vz, min(max_vz, out[2])))
    horiz = math.hypot(out[0], out[1])
    if horiz > 1e-6 and abs(out[2]) >= max_vz * 0.99:
        scale = math.sqrt(max(1.0 - (max_vz / max(float(np.linalg.norm(v_ned)), max_vz)) ** 2, 0.0))
        out[0] *= scale
        out[1] *= scale
    return out


def apply_wall_constraint(
    v_ned: np.ndarray,
    pose: VehiclePose,
    wall_x: float | None,
    standoff_m: float,
) -> np.ndarray:
    """Zero or reverse north velocity when inside wall standoff."""
    if wall_x is None or not pose.ok:
        return v_ned
    wall_range = wall_x - pose.x
    out = v_ned.copy()
    if wall_range < standoff_m and out[0] > 0:
        out[0] = min(out[0], -0.02) if wall_range < standoff_m * 0.5 else 0.0
    return out


def ceiling_z_ned(scene: dict[str, Any] | None) -> float | None:
    """NED z of ceiling plane (down-positive); lower z = higher altitude."""
    if not scene:
        return None
    if "ceiling_z_ned" in scene:
        return float(scene["ceiling_z_ned"])
    wall = scene.get("wall")
    if isinstance(wall, dict) and "z_top" in wall:
        return float(wall["z_top"])
    return None


def apply_ceiling_constraint(
    v_ned: np.ndarray,
    pose: VehiclePose,
    ceiling_z: float | None,
    standoff_m: float,
) -> np.ndarray:
    """Limit climb (negative vz) when within standoff of ceiling."""
    if ceiling_z is None or not pose.ok:
        return v_ned
    out = v_ned.copy()
    margin_z = ceiling_z + standoff_m
    if pose.z < margin_z and out[2] < 0:
        out[2] = 0.0
    return out


def scale_speed_by_range(
    pose: VehiclePose,
    scene: dict[str, Any] | None,
    base_speed: float,
    *,
    wall_standoff_m: float,
    slow_zone_m: float,
    fire_distance_m: float | None = None,
    metric_distance_m: float | None = None,
    target_ned: tuple[float, float, float] | None = None,
) -> float:
    """Taper speed using wall range, metric range, and optional 3D slant range."""
    spd = base_speed
    wall_x = wall_north_m(scene) if scene else None
    if wall_x is not None and pose.ok:
        wall_range = wall_x - pose.x
        if wall_range <= 0:
            return 0.0
        if fire_distance_m is not None:
            room = wall_range - fire_distance_m
            stop_range = fire_distance_m + 0.1
        else:
            room = wall_range - wall_standoff_m
            stop_range = wall_standoff_m
        if room <= 0:
            return 0.0
        if pose.vx > 0.03 and wall_range - pose.vx * 1.2 < stop_range:
            return 0.0
        if room < slow_zone_m:
            ratio = max(room / slow_zone_m, 0.0)
            spd = base_speed * ratio * ratio

    range_m = metric_distance_m
    if range_m is None and target_ned is not None and pose.ok:
        range_m = distance_3d(pose, target_ned)

    if range_m is not None and fire_distance_m is not None:
        if range_m <= fire_distance_m:
            return 0.0
        standoff_band = fire_distance_m * 1.8
        if range_m < standoff_band:
            ratio = (range_m - fire_distance_m) / max(standoff_band - fire_distance_m, 0.1)
            spd = min(spd, base_speed * ratio * ratio)
    return spd


def compute_altitude_vz(
    pose: VehiclePose,
    scene: dict[str, Any],
    *,
    min_ground_clearance_m: float = 1.5,
    kp_z: float = 0.22,
    max_vz: float = 0.12,
    alt_offset_m: float = 0.0,
    cruise_alt_m: float | None = None,
    descent_wall_range_m: float = 4.5,
    align_to_target: bool = False,
) -> float:
    """NED vz from altitude goal (wrapper over velocity_toward_goal)."""
    from valiant.common.sitl_physics import nearest_active_target_ned

    target = nearest_active_target_ned(pose, scene.get("targets", []))
    if target is None:
        return 0.0
    goal = compute_approach_goal(
        pose,
        target,
        scene,
        cruise_alt_m=cruise_alt_m,
        descent_wall_range_m=descent_wall_range_m,
        align_to_target=align_to_target,
        alt_offset_m=alt_offset_m,
        min_clearance_m=min_ground_clearance_m,
    )
    v = velocity_toward_goal(
        pose,
        goal,
        speed_m_s=max_vz,
        max_vz=max_vz,
        kp_z=kp_z,
        min_clearance_m=min_ground_clearance_m,
    )
    return float(v[2])
