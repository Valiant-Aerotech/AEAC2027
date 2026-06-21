"""Public auto-nav API (orchestrator imports from here)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from valiant.autonomy.auto_nav.mavlink_driver import MavlinkDriver
from valiant.autonomy.auto_nav.planner import MotionIntent, MotionPlanner
from valiant.autonomy.auto_nav.approach_motion import effective_approach_speed

if TYPE_CHECKING:
    from pymavlink import mavutil


def create_motion_planner(cfg: dict) -> MotionPlanner:
    """Factory for approach/aim/fire gating from MetricPacket."""
    return MotionPlanner(cfg)


def create_mavlink_driver(master: mavutil.mavfile, cfg: dict) -> MavlinkDriver:
    """Factory for MetricPacket -> MAVLink velocity commands."""
    return MavlinkDriver(master, cfg)


__all__ = [
    "MavlinkDriver",
    "MotionIntent",
    "MotionPlanner",
    "create_mavlink_driver",
    "create_motion_planner",
    "effective_approach_speed",
]
