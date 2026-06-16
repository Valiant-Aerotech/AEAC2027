"""SEARCHING motion for physics SITL — reposition when target not in FOV."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from valiant.common.sitl_physics import VehiclePose, nearest_active_target_ned


@dataclass(frozen=True)
class SearchMotion:
    """Body-frame velocity command for SEARCHING."""

    vx: float
    vy: float
    vz: float = 0.0
    vn: float = 0.0
    ve: float = 0.0
    reason: str = ""


def wall_north_m(scene: dict[str, Any]) -> float | None:
    wall = scene.get("wall")
    if not wall:
        return None
    return float(wall.get("x_m", 5.0))


def ned_to_body_velocity(pose: VehiclePose, vn: float, ve: float, vz: float = 0.0) -> tuple[float, float, float]:
    cy, sy = math.cos(pose.yaw), math.sin(pose.yaw)
    vx = vn * cy + ve * sy
    vy = -vn * sy + ve * cy
    return vx, vy, vz


def compute_search_motion(
    pose: VehiclePose,
    scene: dict[str, Any],
    *,
    search_speed: float = 0.15,
    wall_standoff_m: float = 0.6,
    creep_speed: float = 0.12,
    home_south_limit_m: float = -1.0,
) -> SearchMotion | None:
    """Reposition in LOCAL NED toward target; back up only when north of wall standoff."""
    if not pose.ok:
        return None
    targets = scene.get("targets", [])
    target = nearest_active_target_ned(pose, targets)
    if target is None:
        return None

    wall_x = wall_north_m(scene)
    dn = target[0] - pose.x
    de = target[1] - pose.y
    dist_h = math.hypot(dn, de)
    if dist_h < 0.12:
        return None

    if wall_x is not None and pose.x > wall_x - wall_standoff_m:
        vn = -abs(search_speed)
        ve = 0.0
        reason = "backup past wall"
    else:
        speed = creep_speed if (wall_x is None or pose.x < wall_x - 3.0) else min(creep_speed, search_speed)
        vn = speed * dn / dist_h
        ve = speed * de / dist_h
        if pose.x < home_south_limit_m:
            vn = max(vn, speed * 0.5)
        reason = "creep toward target"

    vx, vy, vz = ned_to_body_velocity(pose, vn, ve)
    return SearchMotion(vx, vy, vz, vn=vn, ve=ve, reason=reason)


def scale_approach_speed(
    pose: VehiclePose,
    scene: dict[str, Any],
    approach_speed: float,
    *,
    wall_standoff_m: float = 0.6,
    slow_zone_m: float = 2.0,
    metric_distance_m: float | None = None,
    fire_distance_m: float | None = None,
) -> float:
    """Reduce forward speed near the wall to prevent overshoot."""
    wall_x = wall_north_m(scene)
    if wall_x is None or not pose.ok:
        spd = approach_speed
    else:
        room = wall_x - wall_standoff_m - pose.x
        if room <= 0:
            return 0.0
        if pose.vx > 0.03 and pose.x + pose.vx * 1.2 > wall_x - wall_standoff_m:
            return 0.0
        if room >= slow_zone_m:
            spd = approach_speed
        else:
            ratio = max(room / slow_zone_m, 0.0)
            spd = approach_speed * ratio * ratio

    if metric_distance_m is not None and fire_distance_m is not None:
        if metric_distance_m <= fire_distance_m:
            return 0.0
        standoff_band = fire_distance_m * 1.8
        if metric_distance_m < standoff_band:
            ratio = (metric_distance_m - fire_distance_m) / max(standoff_band - fire_distance_m, 0.1)
            spd = min(spd, approach_speed * ratio * ratio)
    return spd


def compute_altitude_vz(
    pose: VehiclePose,
    scene: dict[str, Any],
    *,
    min_ground_clearance_m: float = 1.5,
    kp_z: float = 0.22,
    max_vz: float = 0.12,
    alt_offset_m: float = 0.0,
) -> float:
    """NED vz (down positive): align altitude with target via gimbal-friendly standoff height."""
    if not pose.ok:
        return 0.0
    target = nearest_active_target_ned(pose, scene.get("targets", []))
    if target is None:
        return 0.0

    target_alt_m = -float(target[2])
    desired_alt_m = max(target_alt_m + alt_offset_m, min_ground_clearance_m)
    desired_z = -desired_alt_m
    clearance_z = -min_ground_clearance_m
    current_alt_m = -pose.z

    if current_alt_m < min_ground_clearance_m - 0.05:
        err = clearance_z - pose.z
        vz = kp_z * err
        return max(-max_vz, min(0.0, vz))

    err = desired_z - pose.z
    if abs(err) < 0.12:
        return 0.0
    vz = kp_z * err
    if vz > 0 and pose.z >= desired_z - 0.05:
        vz = 0.0
    return max(-max_vz, min(max_vz, vz))


def compute_reposition_motion(
    pose: VehiclePose,
    *,
    retreat_alt_m: float = 2.5,
    retreat_home_north_m: float = 1.0,
    speed: float = 0.12,
    max_vz: float = 0.12,
) -> tuple[float, float, float, bool]:
    """Climb and back away from wall after a kill; returns (vx, vy, vz body), done."""
    if not pose.ok:
        return 0.0, 0.0, 0.0, False
    alt_m = -pose.z
    vn = ve = 0.0
    vz = 0.0
    if pose.x > retreat_home_north_m:
        vn = -abs(speed)
    if alt_m < retreat_alt_m - 0.15:
        vz = -min(max_vz, abs(speed))
    if abs(pose.y) > 0.4:
        ve = -math.copysign(speed * 0.6, pose.y)
    vx, vy, vz_b = ned_to_body_velocity(pose, vn, ve, vz)
    done = pose.x <= retreat_home_north_m + 0.25 and alt_m >= retreat_alt_m - 0.2
    return vx, vy, vz_b, done
