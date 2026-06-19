"""Stanley-inspired subsumption motion stack for SITL (Backoff > Follow > Search > Hold)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from valiant.autonomy.packets import MetricPacket
from valiant.autonomy.sitl_search import (
    compute_altitude_vz,
    compute_search_motion,
    ned_to_body_velocity,
    scale_approach_speed,
    wall_north_m,
)
from valiant.common.sitl_physics import VehiclePose

RULE_BACKOFF = "backoff"
RULE_FOLLOW = "follow"
RULE_SEARCH = "search"
RULE_HOLD = "hold"
RULE_REPOSITION = "reposition"


@dataclass(frozen=True)
class MotionCommand:
    """Output of the motion stack for one control tick."""

    rule: str
    vx: float | None = None
    vy: float | None = None
    vz: float = 0.0
    yaw_rate: float | None = None
    approach_speed: float | None = None
    use_hold_center: bool = False
    reason: str = ""


@dataclass
class SitlMotionConfig:
    backoff_m: float = 1.5
    wall_standoff_m: float = 1.2
    search_speed: float = 0.10
    creep_speed: float = 0.10
    home_south_limit_m: float = -1.0
    approach_slow_zone_m: float = 3.0
    max_north_m: float = 6.0
    max_east_m: float = 2.0
    max_backup_speed: float = 0.12
    search_yaw_rate: float = 0.35
    lane_center_east_m: float = 0.0
    fire_distance_m: float = 0.8
    closing_rate_m_s: float = 0.05
    min_ground_clearance_m: float = 1.5
    altitude_kp: float = 0.22
    max_vz: float = 0.12
    alt_offset_m: float = 0.0
    retreat_alt_m: float = 5.0
    retreat_home_north_m: float = 1.0
    cruise_alt_m: float = 5.0
    descent_wall_range_m: float = 4.5


def _wall_range_m(pose: VehiclePose, scene: dict[str, Any] | None) -> float | None:
    if scene is None or not pose.ok:
        return None
    wall_x = wall_north_m(scene)
    if wall_x is None:
        return None
    return wall_x - pose.x


def _clamp_geofence(
    pose: VehiclePose,
    vn: float,
    ve: float,
    *,
    max_north_m: float,
    max_east_m: float,
    search_speed: float,
    home_south_limit_m: float = -1.0,
) -> tuple[float, float, str]:
    reason = ""
    if pose.x > max_north_m:
        vn = min(vn, -abs(search_speed))
        reason = "geofence north"
    if pose.x < home_south_limit_m:
        vn = max(vn, abs(search_speed) * 0.5)
        reason = reason or "geofence south"
    east_err = pose.y
    if abs(pose.y) > max_east_m:
        ve = -math.copysign(abs(search_speed), east_err)
        reason = reason or "geofence east"
    return vn, ve, reason


def _east_lane_correction(
    pose: VehiclePose,
    vn: float,
    ve: float,
    *,
    lane_center_east_m: float,
    creep_speed: float,
    lane_limit_m: float = 2.0,
) -> tuple[float, float]:
    """Prioritize east correction when drifted off the approach lane."""
    east_err = pose.y - lane_center_east_m
    if abs(east_err) <= lane_limit_m:
        return vn, ve
    ve = -math.copysign(min(abs(creep_speed), abs(east_err) * 0.4), east_err)
    vn *= 0.35
    return vn, ve


def search_yaw_rate(elapsed_s: float, *, rate: float, period_s: float = 8.0) -> float:
    """Stanley-style sinusoidal yaw scan while searching."""
    return rate * math.sin(2.0 * math.pi * elapsed_s / period_s)


class SitlMotionStack:
    """Priority rule stack: Backoff > Follow > Search > Hold."""

    def __init__(self, cfg: dict):
        sitl = cfg.get("sitl", {})
        metric = cfg.get("metric_recon", {})
        self._cfg = SitlMotionConfig(
            backoff_m=float(sitl.get("backoff_m", 1.5)),
            wall_standoff_m=float(sitl.get("wall_standoff_m", 1.2)),
            search_speed=float(sitl.get("search_speed", 0.10)),
            creep_speed=float(sitl.get("creep_speed", 0.10)),
            home_south_limit_m=float(sitl.get("home_south_limit_m", -1.0)),
            approach_slow_zone_m=float(sitl.get("approach_slow_zone_m", 3.0)),
            max_north_m=float(sitl.get("max_north_m", 6.0)),
            max_east_m=float(sitl.get("max_east_m", 2.0)),
            max_backup_speed=float(sitl.get("max_backup_speed", 0.12)),
            search_yaw_rate=float(sitl.get("search_yaw_rate", 0.35)),
            lane_center_east_m=float(sitl.get("approach_lane_y", 0.0)),
            fire_distance_m=float(metric.get("fire_distance_m", 0.8)),
            min_ground_clearance_m=float(sitl.get("min_ground_clearance_m", 1.5)),
            altitude_kp=float(sitl.get("altitude_kp", 0.22)),
            max_vz=float(sitl.get("max_vz", 0.12)),
            alt_offset_m=float(sitl.get("alt_offset_m", 0.0)),
            retreat_alt_m=float(sitl.get("retreat_alt_m", 5.0)),
            retreat_home_north_m=float(sitl.get("retreat_home_north_m", 1.0)),
            cruise_alt_m=float(sitl.get("cruise_alt_m", sitl.get("takeoff_alt_m", 5.0))),
            descent_wall_range_m=float(sitl.get("descent_wall_range_m", 4.5)),
        )
        self._search_start: float | None = None
        self._had_detection = False

    def _altitude_kwargs(self, *, state: str = "", has_target: bool = False) -> dict[str, float]:
        align = state in ("APPROACHING", "AIMING") and has_target
        return {
            "min_ground_clearance_m": self._cfg.min_ground_clearance_m,
            "kp_z": self._cfg.altitude_kp,
            "max_vz": self._cfg.max_vz,
            "alt_offset_m": self._cfg.alt_offset_m,
            "cruise_alt_m": self._cfg.cruise_alt_m,
            "descent_wall_range_m": self._cfg.descent_wall_range_m,
            "align_to_target": align,
        }

    def reset_search(self) -> None:
        self._search_start = None
        self._had_detection = False

    def note_detection(self) -> None:
        self._had_detection = True

    def decide(
        self,
        *,
        state: str,
        pose: VehiclePose | None,
        scene: dict[str, Any] | None,
        has_target: bool,
        metric: MetricPacket | None,
        approach_speed: float,
    ) -> MotionCommand | None:
        if pose is None or not pose.ok:
            return None

        if has_target:
            self.note_detection()

        wall_range = _wall_range_m(pose, scene)
        wall_x = wall_north_m(scene) if scene else None

        # --- Backoff (highest priority) ---
        backoff_reason = ""
        min_wall_range = max(self._cfg.fire_distance_m * 0.35, 0.25)
        if wall_range is not None and wall_range < min_wall_range:
            backoff_reason = "at wall plane"
        elif (
            state == "SEARCHING"
            and wall_range is not None
            and wall_range < self._cfg.backoff_m
        ):
            backoff_reason = "wall backoff zone"
        elif metric is not None and metric.planner_range_m() is not None:
            if metric.planner_range_m() < self._cfg.fire_distance_m:
                backoff_reason = "inside fire distance"
        elif (
            wall_range is not None
            and wall_range < self._cfg.approach_slow_zone_m
            and pose.vx > self._cfg.closing_rate_m_s
        ):
            backoff_reason = "closing-rate brake"

        if backoff_reason:
            speed = min(self._cfg.max_backup_speed, self._cfg.search_speed)
            vn = -abs(speed)
            ve = 0.0
            if abs(pose.y) > 0.5:
                ve = -math.copysign(speed * 0.5, pose.y)
            vz = 0.0
            if scene is not None:
                vz = compute_altitude_vz(
                    pose, scene, **self._altitude_kwargs(state=state, has_target=has_target)
                )
            vx, vy, _ = ned_to_body_velocity(pose, vn, ve, vz)
            return MotionCommand(
                RULE_BACKOFF, vx=vx, vy=vy, vz=vz, reason=backoff_reason
            )

        # --- Follow ---
        if has_target and metric is not None and state in ("APPROACHING", "AIMING"):
            vz = 0.0
            if scene is not None:
                vz = compute_altitude_vz(
                    pose, scene, **self._altitude_kwargs(state=state, has_target=True)
                )
            if metric is not None and metric.altitude_error_m is not None:
                from valiant.autonomy.metric_recon.geometry_3d import metric_vz_from_altitude_error

                vz_metric = metric_vz_from_altitude_error(
                    metric.altitude_error_m,
                    kp=self._cfg.altitude_kp,
                    max_vz=self._cfg.max_vz,
                )
                vz = 0.5 * vz + 0.5 * vz_metric
            if state == "AIMING":
                needs_creep = False
                if wall_range is not None and wall_range > self._cfg.fire_distance_m + 0.2:
                    needs_creep = True
                elif metric is not None and metric.planner_range_m() is not None:
                    if metric.planner_range_m() > self._cfg.fire_distance_m + 0.12:
                        needs_creep = True
                if needs_creep:
                    spd = min(approach_speed, self._cfg.creep_speed)
                    return MotionCommand(
                        RULE_FOLLOW,
                        approach_speed=spd,
                        vz=vz,
                        reason="aiming creep to target",
                    )
                return MotionCommand(
                    RULE_HOLD, use_hold_center=True, vz=vz, reason="aiming lock"
                )
            spd = approach_speed
            if scene is not None:
                dist = metric.planner_range_m()
                spd = scale_approach_speed(
                    pose,
                    scene,
                    approach_speed,
                    wall_standoff_m=self._cfg.wall_standoff_m,
                    slow_zone_m=self._cfg.approach_slow_zone_m,
                    metric_distance_m=dist,
                    fire_distance_m=self._cfg.fire_distance_m,
                )
            if wall_range is not None and wall_range < self._cfg.approach_slow_zone_m:
                if pose.vx > self._cfg.closing_rate_m_s:
                    spd = 0.0
            fire_band = self._cfg.fire_distance_m + 0.15
            if wall_range is not None and wall_range < fire_band:
                spd = min(spd, self._cfg.creep_speed)
            return MotionCommand(
                RULE_FOLLOW,
                approach_speed=spd,
                vz=vz,
                reason="visual follow",
            )

        # --- Search ---
        if state == "SEARCHING" and not has_target:
            if self._search_start is None:
                self._search_start = time.time()
            elapsed = time.time() - self._search_start
            yaw_rate = search_yaw_rate(elapsed, rate=self._cfg.search_yaw_rate)

            if scene is not None and not self._had_detection:
                motion = compute_search_motion(
                    pose,
                    scene,
                    search_speed=self._cfg.search_speed,
                    wall_standoff_m=self._cfg.wall_standoff_m,
                    creep_speed=self._cfg.creep_speed,
                    home_south_limit_m=self._cfg.home_south_limit_m,
                    max_vz=self._cfg.max_vz,
                    kp_z=self._cfg.altitude_kp,
                    cruise_alt_m=self._cfg.cruise_alt_m,
                    descent_wall_range_m=self._cfg.descent_wall_range_m,
                    min_ground_clearance_m=self._cfg.min_ground_clearance_m,
                    alt_offset_m=self._cfg.alt_offset_m,
                )
                if motion is not None:
                    vn, ve = motion.vn, motion.ve
                    vn, ve, _ = _clamp_geofence(
                        pose,
                        vn,
                        ve,
                        max_north_m=self._cfg.max_north_m,
                        max_east_m=self._cfg.max_east_m,
                        search_speed=self._cfg.search_speed,
                        home_south_limit_m=self._cfg.home_south_limit_m,
                    )
                    vn, ve = _east_lane_correction(
                        pose,
                        vn,
                        ve,
                        lane_center_east_m=self._cfg.lane_center_east_m,
                        creep_speed=self._cfg.creep_speed,
                    )
                    vz = compute_altitude_vz(pose, scene, **self._altitude_kwargs())
                    vx, vy, _ = ned_to_body_velocity(pose, vn, ve, vz)
                    return MotionCommand(
                        RULE_SEARCH,
                        vx=vx,
                        vy=vy,
                        vz=vz,
                        yaw_rate=yaw_rate,
                        reason=motion.reason,
                    )

            return MotionCommand(
                RULE_SEARCH,
                vx=0.0,
                vy=0.0,
                vz=0.0,
                yaw_rate=yaw_rate,
                reason="yaw scan",
            )

        # --- Hold (lost target during approach — coast down, no slam-stop) ---
        if state in ("APPROACHING", "AIMING") and not has_target:
            vz = 0.0
            if scene is not None:
                vz = compute_altitude_vz(
                    pose,
                    scene,
                    **{**self._altitude_kwargs(state=state, has_target=True), "kp_z": self._cfg.altitude_kp * 0.5},
                )
            if metric is not None:
                return MotionCommand(
                    RULE_HOLD, use_hold_center=True, vz=vz, reason="lost target hold"
                )
            vn = min(pose.vx, 0.0)
            if abs(vn) < 0.02:
                vn = 0.0
            vx, vy, vz = ned_to_body_velocity(pose, vn, 0.0)
            return MotionCommand(RULE_HOLD, vx=vx, vy=vy, vz=vz, reason="decelerate")

        return None

    def decide_reposition(self, pose: VehiclePose | None) -> tuple[MotionCommand | None, bool]:
        """Back up and climb after a kill before searching for the next target."""
        if pose is None or not pose.ok:
            return None, False
        from valiant.autonomy.sitl_search import compute_reposition_motion

        vx, vy, vz, done = compute_reposition_motion(
            pose,
            retreat_alt_m=self._cfg.retreat_alt_m,
            retreat_home_north_m=self._cfg.retreat_home_north_m,
            lane_center_east_m=self._cfg.lane_center_east_m,
            speed=self._cfg.search_speed,
            max_vz=self._cfg.max_vz,
        )
        return (
            MotionCommand(RULE_REPOSITION, vx=vx, vy=vy, vz=vz, reason="retreat after kill"),
            done,
        )
