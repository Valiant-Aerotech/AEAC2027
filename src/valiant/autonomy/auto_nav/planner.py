"""Motion planning from MetricPacket - approach, aim, fire gating."""

from __future__ import annotations

from enum import Enum

from valiant.autonomy.packets import MetricPacket
from valiant.autonomy.spray import is_aimed

# Blockers that mean "move closer / prove approach" rather than hold in place.
APPROACH_REMEDIATION_BLOCKERS = frozenset({
    "approach_not_proven", "too_far_wall", "too_far_metric", "altitude_not_aligned",
})
CENTER_REMEDIATION_BLOCKERS = frozenset({"not_aimed"})


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
        self.vertical_clearance_m = nav.get("vertical_clearance_m", 0.8)
        self.target_lock_area_px = nav.get("target_lock_area_px", 15000)
        self.deadband_px = nav.get("deadband_px", 50)
        self.alt_align_tolerance_m = float(
            metric.get(
                "alt_align_tolerance_m",
                cfg.get("sitl", {}).get("alt_align_tolerance_m", 0.25),
            )
        )

        self._max_distance_seen_m: float | None = None
        self._approach_valid = False

    def reset_approach(self) -> None:
        self._max_distance_seen_m = None
        self._approach_valid = False

    def update_approach_tracking(self, metric: MetricPacket) -> None:
        observed = metric.distance_max_m if metric.distance_max_m is not None else metric.planner_range_m()
        if observed is None:
            return
        if self._max_distance_seen_m is None or observed > self._max_distance_seen_m:
            self._max_distance_seen_m = observed
        if self._max_distance_seen_m >= self.min_approach_distance_m:
            self._approach_valid = True

    def is_safe_to_move(self, metric: MetricPacket, *, bbox_area: int = 0) -> bool:
        if bbox_area >= self.target_lock_area_px:
            return True
        close = metric.distance_min_m if metric.distance_min_m is not None else metric.planner_range_m()
        if close is not None and close <= self.fire_distance_m:
            return True
        ox, oy = metric.pixel_offset
        centered = abs(ox) <= self.deadband_px and abs(oy) <= self.deadband_px

        if metric.side_clearance_m is not None:
            if metric.edge_lateral and metric.lateral_clearance_ok:
                pass
            elif not centered or abs(ox) > self.deadband_px:
                pass
            elif metric.side_clearance_m < self.side_clearance_m:
                return False

        if metric.vertical_clearance_m is not None:
            if metric.edge_vertical and metric.vertical_clearance_ok:
                pass
            elif not centered or abs(oy) > self.deadband_px:
                pass
            elif metric.vertical_clearance_m < self.vertical_clearance_m:
                return False

        return True

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
        close = metric.distance_min_m if metric.distance_min_m is not None else metric.planner_range_m()
        if close is not None and close <= self.fire_distance_m:
            return True
        if (
            metric.altitude_error_m is not None
            and abs(metric.altitude_error_m) > self.alt_align_tolerance_m * 2.0
        ):
            return False
        return False

    def _altitude_aligned(self, metric: MetricPacket) -> bool:
        if metric.altitude_error_m is None:
            return True
        return abs(metric.altitude_error_m) <= self.alt_align_tolerance_m

    def _too_far_from_wall_for_fire(
        self,
        metric: MetricPacket,
        wall_range_m: float | None,
        wall_standoff_m: float,
    ) -> bool:
        """Wall-plane gate for wall-mounted targets (distinct from slant metric range)."""
        if wall_range_m is None:
            return False
        close = metric.distance_min_m if metric.distance_min_m is not None else metric.planner_range_m()
        if close is not None and close <= self.fire_distance_m + 0.12:
            if wall_range_m <= wall_standoff_m:
                return False
        return wall_range_m > self.fire_distance_m + 0.15

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
        if metric.edge_proximity.any_edge and not metric.body_clearance_ok:
            return False
        # CONOPS: must prove approach from beyond 2 m; never fire without distance evidence
        if metric.planner_range_m() is None and metric.distance_max_m is None:
            return False
        if not self._approach_valid:
            return False
        if self._too_far_from_wall_for_fire(metric, wall_range_m, wall_standoff_m):
            return False
        close = metric.distance_min_m if metric.distance_min_m is not None else metric.planner_range_m()
        if close is not None and close > self.fire_distance_m + 0.12:
            return False
        if not self._altitude_aligned(metric):
            return False
        return True

    def fire_blockers(
        self,
        metric: MetricPacket,
        *,
        lock_duration_met: bool,
        wall_range_m: float | None = None,
        wall_standoff_m: float = 1.2,
    ) -> tuple[str, ...]:
        """Why fire/capture is not allowed yet (empty = ready)."""
        blockers: list[str] = []
        if not lock_duration_met:
            blockers.append("lock_duration")
        if not is_aimed(metric, self._cfg):
            blockers.append("not_aimed")
        if metric.edge_proximity.any_edge and not metric.lateral_clearance_ok:
            blockers.append("body_clearance")
        if metric.edge_proximity.any_edge and not metric.vertical_clearance_ok:
            blockers.append("vertical_clearance")
        if metric.planner_range_m() is None and metric.distance_max_m is None:
            blockers.append("no_distance")
        if not self._approach_valid:
            blockers.append("approach_not_proven")
        if self._too_far_from_wall_for_fire(metric, wall_range_m, wall_standoff_m):
            blockers.append("too_far_wall")
        close = metric.distance_min_m if metric.distance_min_m is not None else metric.planner_range_m()
        if close is not None and close > self.fire_distance_m + 0.12:
            blockers.append("too_far_metric")
        if not self._altitude_aligned(metric):
            blockers.append("altitude_not_aligned")
        return tuple(blockers)

    @staticmethod
    def needs_approach_remediation(blockers: tuple[str, ...]) -> bool:
        return any(b in APPROACH_REMEDIATION_BLOCKERS for b in blockers)

    @staticmethod
    def needs_center_remediation(blockers: tuple[str, ...]) -> bool:
        return any(b in CENTER_REMEDIATION_BLOCKERS for b in blockers)

    @property
    def approach_valid(self) -> bool:
        return self._approach_valid
