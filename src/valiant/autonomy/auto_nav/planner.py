"""Motion planning from MetricPacket - approach, aim, fire gating."""

from __future__ import annotations

from enum import Enum

from valiant.autonomy.packets import MetricPacket


class MotionIntent(Enum):
    STOP = "stop"
    APPROACH = "approach"
    HOLD_AIM = "hold_aim"
    ABORT = "abort"


class MotionPlanner:
    """Decide motion intent and fire permission from metric data."""

    def __init__(self, cfg: dict):
        nav = cfg.get("auto_nav", {})
        metric = cfg.get("metric_recon", {})

        self.min_approach_distance_m = metric.get("min_approach_distance_m", 2.0)
        self.fire_distance_m = metric.get("fire_distance_m", 0.8)
        self.side_clearance_m = nav.get("side_clearance_m", 1.0)
        self.target_lock_area_px = nav.get("target_lock_area_px", 15000)
        self.deadband_px = nav.get("deadband_px", 40)

        self._max_distance_seen_m: float | None = None
        self._approach_valid = False

    def reset_approach(self) -> None:
        self._max_distance_seen_m = None
        self._approach_valid = False

    def update_approach_tracking(self, metric: MetricPacket) -> None:
        if metric.distance_m is None:
            return
        if self._max_distance_seen_m is None or metric.distance_m > self._max_distance_seen_m:
            self._max_distance_seen_m = metric.distance_m
        if self._max_distance_seen_m >= self.min_approach_distance_m:
            self._approach_valid = True

    def is_safe_to_move(self, metric: MetricPacket) -> bool:
        if metric.side_clearance_m is None:
            return True
        return metric.side_clearance_m >= self.side_clearance_m

    def should_switch_to_aiming(self, metric: MetricPacket, bbox_area: int) -> bool:
        if bbox_area >= self.target_lock_area_px:
            return True
        if metric.distance_m is not None and metric.distance_m <= self.fire_distance_m:
            return True
        return False

    def intent_for_approaching(self, metric: MetricPacket) -> MotionIntent:
        self.update_approach_tracking(metric)
        if not self.is_safe_to_move(metric):
            return MotionIntent.ABORT
        return MotionIntent.APPROACH

    def intent_for_aiming(self, metric: MetricPacket) -> MotionIntent:
        if not self.is_safe_to_move(metric):
            return MotionIntent.ABORT
        return MotionIntent.HOLD_AIM

    def can_fire(self, metric: MetricPacket, *, lock_duration_met: bool) -> bool:
        if not lock_duration_met:
            return False
        if not self._is_centered(metric):
            return False
        # CONOPS: when distance is available, must have approached from beyond 2m
        if self._max_distance_seen_m is not None:
            return self._approach_valid
        return True

    def _is_centered(self, metric: MetricPacket) -> bool:
        dx, dy = metric.pixel_offset
        return abs(dx) < self.deadband_px and abs(dy) < self.deadband_px

    @property
    def approach_valid(self) -> bool:
        return self._approach_valid
