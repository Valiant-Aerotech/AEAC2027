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
    mode: str | None


class EscapeGate:
    def __init__(self) -> None:
        self._holding = False

    def update(
        self,
        *,
        armed: bool,
        pitch: float | None,
        roll: float | None,
        north_m: float,
        east_m: float,
    ) -> EscapeAction:
        centered = (
            pitch is not None
            and roll is not None
            and math.isfinite(pitch)
            and math.isfinite(roll)
            and abs(pitch) <= STICK_DEADBAND
            and abs(roll) <= STICK_DEADBAND
        )
        want = armed and centered and math.hypot(north_m, east_m) >= MOVE_M
        if want:
            self._holding = True
            return EscapeAction(True, north_m, east_m, "offboard")
        if self._holding:
            self._holding = False
            return EscapeAction(False, 0.0, 0.0, "position")
        return EscapeAction(False, 0.0, 0.0, None)
