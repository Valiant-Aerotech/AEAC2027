"""Centered-stick escape gate. No ROS.

Pitch and roll inside the deadband may take offboard. Yaw is not an input,
so looking around does not cancel the move. A pitch or roll deflection, or
a hover that is legal again, asks for position mode once and does not
command a return to the old point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

STICK_DEADBAND = 0.10
MOVE_M = 0.5


@dataclass(frozen=True)
class EscapeAction:
    heartbeat: bool
    north_m: float
    east_m: float
    up_m: float = 0.0
    mode: str | None = None


class EscapeGate:
    def __init__(self) -> None:
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
