"""LOCAL NED kinematics: rotations, distances, and 3D velocity planning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from valiant_mav.kinematics import VehiclePose, alt_m_from_z


class ApproachPhase(str, Enum):
    CRUISE = "cruise"
    ALIGN = "align"
    RETREAT = "retreat"


@dataclass(frozen=True)
class ApproachGoal:
    """Desired NED position for velocity steering."""

    position_ned: np.ndarray
    phase: ApproachPhase = ApproachPhase.ALIGN


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


def compute_approach_goal(
    pose: VehiclePose,
    target_ned: tuple[float, float, float],
    *,
    cruise_alt_m: float | None,
    descend_range_m: float,
    align_to_target: bool,
    alt_offset_m: float,
    min_clearance_m: float,
    retreat_to_ned: tuple[float, float, float] | None = None,
) -> ApproachGoal:
    """Where to fly next when closing on a target.

    Stay at cruise altitude until within ``descend_range_m`` horizontally, then
    drop to the target's altitude plus ``alt_offset_m``, never below
    ``min_clearance_m``. Passing ``retreat_to_ned`` overrides everything and
    sends the aircraft to that point instead, which is how a mission backs off
    after a payload action.
    """
    if retreat_to_ned is not None:
        goal = np.array(retreat_to_ned, dtype=float)
        return ApproachGoal(goal, ApproachPhase.RETREAT)

    tx, ty, tz = (float(target_ned[0]), float(target_ned[1]), float(target_ned[2]))
    target_alt_m = alt_m_from_z(tz) + alt_offset_m
    descend = distance_horizontal(pose, (tx, ty, tz)) <= descend_range_m

    if align_to_target or descend or cruise_alt_m is None:
        desired_alt_m = max(target_alt_m, min_clearance_m)
        phase = ApproachPhase.ALIGN
    else:
        desired_alt_m = max(cruise_alt_m, min_clearance_m)
        phase = ApproachPhase.CRUISE

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


def speed_scaled_by_range(
    base_speed: float,
    range_m: float | None,
    *,
    stop_range_m: float,
    slow_zone_m: float,
) -> float:
    """Taper speed to zero as the aircraft closes on a stopping distance.

    Quadratic rather than linear so the last metre is taken slowly. Used both
    for closing on a target and for backing off a keepout boundary.
    """
    if range_m is None:
        return base_speed
    room = range_m - stop_range_m
    if room <= 0:
        return 0.0
    if room >= slow_zone_m:
        return base_speed
    ratio = room / max(slow_zone_m, 1e-6)
    return base_speed * ratio * ratio
