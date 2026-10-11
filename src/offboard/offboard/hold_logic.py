"""PX4 position-hold rules. No ROS imports.

The node heartbeats in every mode. This machine decides when a setpoint
exists. Offboard on with nothing latched keeps trying. A latch is kept
through a bad position or a bad heading. It is replaced only when an
estimator reset counter changes and the new sample is good. Offboard off
drops the latch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

NAN = float("nan")
UNUSED = (NAN, NAN, NAN)


@dataclass(frozen=True)
class LocalSample:
    x: float
    y: float
    z: float
    heading: float
    xy_valid: bool
    z_valid: bool
    heading_good_for_control: bool
    xy_reset_counter: int
    z_reset_counter: int
    heading_reset_counter: int


@dataclass(frozen=True)
class HoldSetpoint:
    x: float
    y: float
    z: float
    yaw: float


def _finite(value: float) -> bool:
    return math.isfinite(value)


def _position_ok(sample: LocalSample) -> bool:
    return (
        sample.xy_valid
        and sample.z_valid
        and _finite(sample.x)
        and _finite(sample.y)
        and _finite(sample.z)
    )


def _good(sample: LocalSample) -> bool:
    return (
        _position_ok(sample)
        and sample.heading_good_for_control
        and _finite(sample.heading)
    )


def _counters(sample: LocalSample) -> tuple[int, int, int]:
    return (
        sample.xy_reset_counter,
        sample.z_reset_counter,
        sample.heading_reset_counter,
    )


class HoldLogic:
    def __init__(self) -> None:
        self.offboard = False
        self.latch: tuple[float, float, float, float] | None = None
        self._sample: LocalSample | None = None
        self._counters: tuple[int, int, int] | None = None

    def set_offboard(self, enabled: bool) -> str | None:
        enabled = bool(enabled)
        if enabled == self.offboard:
            return None
        self.offboard = enabled
        if not enabled:
            self.latch = None
            self._counters = None
            return None
        return self._try_latch()

    def set_sample(self, sample: LocalSample) -> str | None:
        self._sample = sample
        if not self.offboard:
            return None
        if self.latch is None:
            return self._try_latch()
        counters = _counters(sample)
        if self._counters is not None and counters != self._counters:
            if _good(sample):
                self._store(sample)
            else:
                self.latch = None
                self._counters = None
            return "estimator reset"
        if not _position_ok(sample):
            return "position lost"
        if not sample.heading_good_for_control or not _finite(sample.heading):
            return "heading lost"
        return None

    def setpoint(self) -> HoldSetpoint | None:
        if not self.offboard or self.latch is None:
            return None
        x, y, z, yaw = self.latch
        return HoldSetpoint(x, y, z, yaw)

    def idle_line(self) -> str | None:
        if not self.offboard:
            return "waiting for offboard"
        if self.latch is None:
            return "waiting for local position"
        return None

    def _try_latch(self) -> str | None:
        sample = self._sample
        if sample is None or not _good(sample):
            return None
        self._store(sample)
        return "hold latched"

    def _store(self, sample: LocalSample) -> None:
        self.latch = (sample.x, sample.y, sample.z, sample.heading)
        self._counters = _counters(sample)
