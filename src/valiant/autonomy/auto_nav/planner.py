"""Motion planning from MetricPacket - approach, aim, fire gating."""

from __future__ import annotations

from enum import Enum

from valiant.autonomy.packets import MetricPacket
from valiant.autonomy.spray.aim import is_aimed


class MotionIntent(Enum):
    APPROACH = "approach"
    HOLD_AIM = "hold_aim"
    ABORT = "abort"


class MotionPlanner:
    """Decide motion intent and fire permission from metric data."""

    def __init__(self, cfg: dict):
        self._cfg = cfg
        nav = cfg.get("auto_nav", {})
        metric = cfg.get("metric_recon", {})

        self.min_approach_distance_m = metric.get("min_approach_distance_m", 2.0)
        self.fire_distance_m = metric.get("fire_distance_m", 0.8)
        self.side_clearance_m = nav.get("side_clearance_m", 1.0)
        self.target_lock_area_px = nav.get("target_lock_area_px", 15000)
        self.deadband_px = nav.get("deadband_px", 50)

        self._max_distance_seen_m: float | None = None
        self._approach_valid = False

    def reset_approach(self) -> None:
        self._max_distance_seen_m = None
        self._approach_valid = False

    def update_approach_tracking(self, metric: MetricPacket) -> None:
        # Conservative: farthest bound must reach 2 m for CONOPS approach proof
        observed = metric.distance_max_m if metric.distance_max_m is not None else metric.distance_m
        if observed is None:
            return
        if self._max_distance_seen_m is None or observed > self._max_distance_seen_m:
            self._max_distance_seen_m = observed
        if self._max_distance_seen_m >= self.min_approach_distance_m:
            self._approach_valid = True

    def is_safe_to_move(self, metric: MetricPacket, *, bbox_area: int = 0) -> bool:
        if bbox_area >= self.target_lock_area_px:
            return True
        close = metric.distance_min_m if metric.distance_min_m is not None else metric.distance_m
        if close is not None and close <= self.fire_distance_m:
            return True
        if metric.side_clearance_m is None:
            return True
        ox, oy = metric.pixel_offset
        if abs(ox) > self.deadband_px or abs(oy) > self.deadband_px:
            return True
        return metric.side_clearance_m >= self.side_clearance_m

    def should_switch_to_aiming(
        self,
        metric: MetricPacket,
        bbox_area: int,
        *,
        wall_range_m: float | None = None,
        aim_wall_range_m: float | None = None,
    ) -> bool:
        if wall_range_m is not None and aim_wall_range_m is not None:
            if wall_range_m > aim_wall_range_m:
                return False
        if bbox_area >= self.target_lock_area_px:
            return True
        close = metric.distance_min_m if metric.distance_min_m is not None else metric.distance_m
        if close is not None and close <= self.fire_distance_m:
            return True
        return False

    def intent_for_approaching(self, metric: MetricPacket, *, bbox_area: int = 0) -> MotionIntent:
        self.update_approach_tracking(metric)
        if not self.is_safe_to_move(metric, bbox_area=bbox_area):
            return MotionIntent.ABORT
        return MotionIntent.APPROACH

    def intent_for_aiming(self, metric: MetricPacket, *, bbox_area: int = 0) -> MotionIntent:
        if not self.is_safe_to_move(metric, bbox_area=bbox_area):
            return MotionIntent.ABORT
        return MotionIntent.HOLD_AIM

    def can_fire(
        self,
        metric: MetricPacket,
        *,
        lock_duration_met: bool,
        wall_range_m: float | None = None,
        wall_standoff_m: float = 1.2,
    ) -> bool:
        if not lock_duration_met:
            return False
        if not is_aimed(metric, self._cfg):
            return False
        # CONOPS: must prove approach from beyond 2 m; never fire without distance evidence
        if metric.distance_m is None and metric.distance_max_m is None:
            return False
        if not self._approach_valid:
            return False
        if wall_range_m is not None and wall_range_m > wall_standoff_m + 0.35:
            return False
        return True

    @property
    def approach_valid(self) -> bool:
        return self._approach_valid
