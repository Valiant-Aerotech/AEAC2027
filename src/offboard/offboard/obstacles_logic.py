"""Centered-stick escape gate. No ROS.

Pitch and roll inside the deadband may take offboard. Yaw is not an input,
so looking around does not cancel the move. A pitch or roll deflection, or
a hover that is legal again, asks for position mode once and does not
command a return to the old point.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

STICK_DEADBAND = 0.10
MOVE_M = 0.5
TRAFFIC_FRESH_S = 2.0


@dataclass(frozen=True)
class EscapeAction:
    heartbeat: bool
    north_m: float
    east_m: float
    up_m: float = 0.0
    mode: str | None = None

@dataclass(frozen=True)
class LocalSample:
    x: float
    y: float
    z: float
    yaw: float
    xy_valid: bool
    z_valid: bool
    heading_good_for_control: bool
    xy_reset_counter: int
    z_reset_counter: int
    heading_reset_counter: int

@dataclass(frozen=True)
class EscapeTarget:
    x: float
    y: float
    z: float
    yaw: float

class TrafficFreshness:
    def __init__(self, max_age_s: float = TRAFFIC_FRESH_S) -> None:
        self._max_age_s = max_age_s
        self._accepted_at: float | None = None

    def observe(self, accepted: bool, now_s: float) -> None:
        if accepted:
            self._accepted_at = now_s

    def fresh(self, now_s: float) -> bool:
        return self._accepted_at is not None and now_s - self._accepted_at < self._max_age_s

class EscapeTargetLatch:
    def __init__(self) -> None:
        self._target: EscapeTarget | None = None
        self._sample: LocalSample | None = None

    def reset(self) -> None:
        self._target = None
        self._sample = None

    def update(self, action: EscapeAction, sample: LocalSample) -> EscapeTarget | None:
        if not action.heartbeat:
            self.reset()
            return None
        if not self._valid(sample):
            self.reset()
            return None
        if self._sample is not None and self._reset_changed(sample):
            self.reset()
            return None
        if self._target is None:
            self._target = EscapeTarget(
                x=sample.x + action.north_m,
                y=sample.y + action.east_m,
                z=sample.z - action.up_m,
                yaw=sample.yaw,
            )
        self._sample = sample
        return self._target

    @staticmethod
    def _valid(sample: LocalSample) -> bool:
        return (
            sample.xy_valid
            and sample.z_valid
            and sample.heading_good_for_control
            and math.isfinite(sample.x)
            and math.isfinite(sample.y)
            and math.isfinite(sample.z)
            and math.isfinite(sample.yaw)
        )

    def _reset_changed(self, sample: LocalSample) -> bool:
        assert self._sample is not None
        return (
            sample.xy_reset_counter != self._sample.xy_reset_counter
            or sample.z_reset_counter != self._sample.z_reset_counter
            or sample.heading_reset_counter != self._sample.heading_reset_counter
        )


class EscapeGate:
    def __init__(self) -> None:
        self._holding = False
        self._north_m = 0.0
        self._east_m = 0.0
        self._up_m = 0.0

    def reset(self) -> None:
        self._holding = False
        self._north_m = 0.0
        self._east_m = 0.0
        self._up_m = 0.0

    def remembered(self) -> tuple[float, float, float] | None:
        """Step from the last cycle, while the sticks stay centered."""
        if not self._holding:
            return None
        return (self._north_m, self._east_m, self._up_m)

    def update(
        self,
        *,
        armed: bool,
        pitch: float | None,
        roll: float | None,
        north_m: float,
        east_m: float,
        up_m: float = 0.0,
    ) -> EscapeAction:
        centered = (
            pitch is not None
            and roll is not None
            and math.isfinite(pitch)
            and math.isfinite(roll)
            and abs(pitch) <= STICK_DEADBAND
            and abs(roll) <= STICK_DEADBAND
        )
        want = armed and centered and (math.hypot(north_m, east_m) >= MOVE_M or abs(up_m) >= MOVE_M)
        if want:
            self._holding = True
            self._north_m = north_m
            self._east_m = east_m
            self._up_m = up_m
            return EscapeAction(True, north_m, east_m, up_m, "offboard")
        if self._holding:
            self._holding = False
            self._north_m = 0.0
            self._east_m = 0.0
            self._up_m = 0.0
            return EscapeAction(False, 0.0, 0.0, 0.0, "position")
        return EscapeAction(False, 0.0, 0.0, 0.0, None)
