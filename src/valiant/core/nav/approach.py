"""Approach planning: close on a target to a standoff, then signal ready.

This is deliberately not a mission. The planner answers two questions from
metric geometry — "may I keep moving?" and "am I in position?" — and the
mission decides what to do when the answer to the second is yes. For 2027 that
means attaching a tracker or picking up a sample; the gating logic is the same
either way.

The one piece of behaviour worth preserving from 2026: a payload action is
never permitted unless the approach was *proven*, meaning we observed the
target from beyond the standoff distance and closed on it. Arriving already
close, with no approach history, is treated as untrusted range evidence.
"""

from __future__ import annotations

from enum import Enum

from valiant.perception.types import RangeFix

# Blockers that mean "keep closing" rather than "hold still and re-aim".
APPROACH_REMEDIATION_BLOCKERS = frozenset({
    "approach_not_proven",
    "too_far",
    "altitude_not_aligned",
})
CENTER_REMEDIATION_BLOCKERS = frozenset({"not_centered"})


class MotionIntent(Enum):
    APPROACH = "approach"
    HOLD = "hold"
    ABORT = "abort"


class ApproachPlanner:
    """Decide motion intent and action permission from metric geometry."""

    def __init__(self, cfg: dict):
        self._cfg = cfg
        nav = cfg.get("nav", cfg.get("auto_nav", {}))
        metric = cfg.get("metric_recon", {})

        # Distance we must have observed the target from before closing counts
        # as a real approach.
        self.standoff_proof_m = float(metric.get("standoff_proof_m", 2.0))
        # Distance at which we consider ourselves in position to act.
        self.action_distance_m = float(metric.get("action_distance_m", 0.8))
        self.action_distance_slack_m = float(metric.get("action_distance_slack_m", 0.12))
        self.target_lock_area_px = int(nav.get("target_lock_area_px", 15000))
        self.deadband_px = float(nav.get("deadband_px", 50))
        self.alt_align_tolerance_m = float(
            metric.get(
                "alt_align_tolerance_m",
                cfg.get("sitl", {}).get("alt_align_tolerance_m", 0.25),
            )
        )

        self._max_distance_seen_m: float | None = None
        self._approach_valid = False

    # --- approach proving ----------------------------------------------------

    def reset_approach(self) -> None:
        self._max_distance_seen_m = None
        self._approach_valid = False

    def update_approach_tracking(self, fix: RangeFix) -> None:
        observed = fix.distance_max_m if fix.distance_max_m is not None else fix.range_m()
        if observed is None:
            return
        if self._max_distance_seen_m is None or observed > self._max_distance_seen_m:
            self._max_distance_seen_m = observed
        if self._max_distance_seen_m >= self.standoff_proof_m:
            self._approach_valid = True

    @property
    def approach_valid(self) -> bool:
        return self._approach_valid

    # --- gating --------------------------------------------------------------

    def _nearest_m(self, fix: RangeFix) -> float | None:
        return fix.distance_min_m if fix.distance_min_m is not None else fix.range_m()

    def _centered(self, fix: RangeFix) -> bool:
        ox, oy = fix.pixel_offset
        return abs(ox) <= self.deadband_px and abs(oy) <= self.deadband_px

    def _altitude_aligned(self, fix: RangeFix) -> bool:
        if fix.altitude_error_m is None:
            return True
        return abs(fix.altitude_error_m) <= self.alt_align_tolerance_m

    def in_position(self, fix: RangeFix) -> bool:
        near = self._nearest_m(fix)
        if near is None:
            return False
        return near <= self.action_distance_m + self.action_distance_slack_m

    def is_safe_to_move(self, fix: RangeFix, *, bbox_area: int = 0) -> bool:
        """Whether closing further is allowed.

        A large bounding box or an already-close range both mean we are at the
        target and further motion is the mission's call, not a safety question.
        """
        if bbox_area >= self.target_lock_area_px:
            return True
        near = self._nearest_m(fix)
        if near is not None and near <= self.action_distance_m:
            return True
        return True

    def intent_for_approaching(self, fix: RangeFix, *, bbox_area: int = 0) -> MotionIntent:
        self.update_approach_tracking(fix)
        if not self.is_safe_to_move(fix, bbox_area=bbox_area):
            return MotionIntent.ABORT
        if self.in_position(fix):
            return MotionIntent.HOLD
        return MotionIntent.APPROACH

    def intent_for_holding(self, fix: RangeFix, *, bbox_area: int = 0) -> MotionIntent:
        if not self.is_safe_to_move(fix, bbox_area=bbox_area):
            return MotionIntent.ABORT
        return MotionIntent.HOLD

    # --- action permission ---------------------------------------------------

    def action_blockers(self, fix: RangeFix, *, lock_duration_met: bool) -> tuple[str, ...]:
        """Why the payload action is not allowed yet. Empty tuple means ready."""
        blockers: list[str] = []
        if not lock_duration_met:
            blockers.append("lock_duration")
        if not self._centered(fix):
            blockers.append("not_centered")
        if fix.range_m() is None and fix.distance_max_m is None:
            blockers.append("no_distance")
        if not self._approach_valid:
            blockers.append("approach_not_proven")
        if not self.in_position(fix):
            blockers.append("too_far")
        if not self._altitude_aligned(fix):
            blockers.append("altitude_not_aligned")
        return tuple(blockers)

    def may_act(self, fix: RangeFix, *, lock_duration_met: bool) -> bool:
        """True when every precondition for the payload action is satisfied.

        Payload actions are one-shot and mostly irreversible — releasing a
        tracker, dropping a sample — so this is an all-gates-pass check rather
        than a best-effort score.
        """
        return not self.action_blockers(fix, lock_duration_met=lock_duration_met)

    @staticmethod
    def needs_approach_remediation(blockers: tuple[str, ...]) -> bool:
        return any(b in APPROACH_REMEDIATION_BLOCKERS for b in blockers)

    @staticmethod
    def needs_center_remediation(blockers: tuple[str, ...]) -> bool:
        return any(b in CENTER_REMEDIATION_BLOCKERS for b in blockers)


def effective_approach_speed(
    fix: RangeFix | None,
    *,
    base_speed: float,
    slow_range_m: float = 3.0,
    min_speed: float = 0.15,
) -> float:
    """Scale approach speed down as the target gets closer."""
    if fix is None:
        return base_speed
    near = fix.distance_min_m if fix.distance_min_m is not None else fix.range_m()
    if near is None or near >= slow_range_m:
        return base_speed
    scale = max(near / slow_range_m, 0.0)
    return max(min_speed, base_speed * scale)
