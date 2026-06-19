"""SEARCHING motion for physics SITL - reposition when target not in FOV."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from valiant.common.ned_kinematics import (
    ApproachGoal,
    ApproachPhase,
    VehiclePose,
    apply_wall_constraint,
    compute_approach_goal,
    compute_altitude_vz,
    ned_to_body_velocity,
    scale_speed_by_range,
    velocity_toward_goal,
    wall_north_m,
)
from valiant.common.sitl_physics import nearest_active_target_ned

__all__ = [
    "SearchMotion",
    "wall_north_m",
    "ned_to_body_velocity",
    "compute_search_motion",
    "scale_approach_speed",
    "compute_altitude_vz",
    "compute_reposition_motion",
]


@dataclass(frozen=True)
class SearchMotion:
    """Body-frame velocity command for SEARCHING."""

    vx: float
    vy: float
    vz: float = 0.0
    vn: float = 0.0
    ve: float = 0.0
    reason: str = ""


def compute_search_motion(
    pose: VehiclePose,
    scene: dict[str, Any],
    *,
    search_speed: float = 0.15,
    wall_standoff_m: float = 0.6,
    creep_speed: float = 0.12,
    home_south_limit_m: float = -1.0,
    max_vz: float = 0.12,
    kp_z: float = 0.22,
    cruise_alt_m: float | None = None,
    descent_wall_range_m: float = 4.5,
    min_ground_clearance_m: float = 1.5,
    alt_offset_m: float = 0.0,
) -> SearchMotion | None:
    """3D reposition in LOCAL NED toward target."""
    if not pose.ok:
        return None
    targets = scene.get("targets", [])
    target = nearest_active_target_ned(pose, targets)
    if target is None:
        return None

    wall_x = wall_north_m(scene)
    dist_3d = math.sqrt(
        (target[0] - pose.x) ** 2 + (target[1] - pose.y) ** 2 + (target[2] - pose.z) ** 2
    )
    if dist_3d < 0.12:
        return None

    if wall_x is not None and pose.x > wall_x - wall_standoff_m:
        vn = -abs(search_speed)
        ve = 0.0
        vz_ned = compute_altitude_vz(
            pose, scene,
            min_ground_clearance_m=min_ground_clearance_m,
            kp_z=kp_z, max_vz=max_vz,
            alt_offset_m=alt_offset_m,
            cruise_alt_m=cruise_alt_m,
            descent_wall_range_m=descent_wall_range_m,
        )
        reason = "backup past wall"
    else:
        speed = creep_speed if (wall_x is None or pose.x < wall_x - 3.0) else min(creep_speed, search_speed)
        goal = compute_approach_goal(
            pose, target, scene,
            cruise_alt_m=cruise_alt_m,
            descent_wall_range_m=descent_wall_range_m,
            align_to_target=False,
            alt_offset_m=alt_offset_m,
            min_clearance_m=min_ground_clearance_m,
        )
        v_ned = velocity_toward_goal(
            pose, goal, speed_m_s=speed, max_vz=max_vz, kp_z=kp_z,
            min_clearance_m=min_ground_clearance_m,
        )
        v_ned = apply_wall_constraint(v_ned, pose, wall_x, wall_standoff_m)
        vn, ve, vz_ned = float(v_ned[0]), float(v_ned[1]), float(v_ned[2])
        if pose.x < home_south_limit_m:
            vn = max(vn, speed * 0.5)
        reason = "creep toward target"

    vx, vy, vz = ned_to_body_velocity(pose, vn, ve, vz_ned)
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
    target = nearest_active_target_ned(pose, scene.get("targets", [])) if scene else None
    return scale_speed_by_range(
        pose,
        scene,
        approach_speed,
        wall_standoff_m=wall_standoff_m,
        slow_zone_m=slow_zone_m,
        fire_distance_m=fire_distance_m,
        metric_distance_m=metric_distance_m,
        target_ned=target,
    )


def compute_reposition_motion(
    pose: VehiclePose,
    scene: dict[str, Any] | None = None,
    *,
    retreat_alt_m: float = 2.5,
    retreat_home_north_m: float = 1.0,
    lane_center_east_m: float = 0.0,
    speed: float = 0.12,
    max_vz: float = 0.12,
    lane_tolerance_m: float = 0.35,
) -> tuple[float, float, float, bool]:
    """Climb and back away from wall after a kill; returns (vx, vy, vz body), done."""
    if not pose.ok:
        return 0.0, 0.0, 0.0, False
    alt_m = -pose.z
    east_err = pose.y - lane_center_east_m
    goal_pos = np.array([retreat_home_north_m, lane_center_east_m, -retreat_alt_m], dtype=float)
    goal = ApproachGoal(goal_pos, ApproachPhase.RETREAT)
    v_ned = velocity_toward_goal(pose, goal, speed_m_s=speed, max_vz=max_vz, kp_z=0.22)
    vn, ve, vz = float(v_ned[0]), float(v_ned[1]), float(v_ned[2])
    if pose.x > retreat_home_north_m:
        vn = min(vn, -abs(speed))
    if alt_m < retreat_alt_m - 0.15:
        vz = min(vz, -min(max_vz, abs(speed)))
    if abs(east_err) > lane_tolerance_m:
        ve = -math.copysign(speed * 0.6, east_err)
    vx, vy, vz_b = ned_to_body_velocity(pose, vn, ve, vz)
    done = (
        pose.x <= retreat_home_north_m + 0.25
        and alt_m >= retreat_alt_m - 0.2
        and abs(east_err) <= lane_tolerance_m
    )
    return vx, vy, vz_b, done
