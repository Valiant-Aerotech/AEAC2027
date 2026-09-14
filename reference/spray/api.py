"""Public spray API (orchestrator and auto-nav import from here)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from valiant.autonomy.spray.actuation import WaterTrigger
from valiant.autonomy.spray.aim import is_aimed, is_body_aligned, is_target_aligned

if TYPE_CHECKING:
    from pymavlink import mavutil


def create_water_trigger(mav_connection: mavutil.mavfile | None, cfg: dict) -> WaterTrigger:
    """Factory for MAVLink servo or GPIO water actuation."""
    return WaterTrigger(mav_connection, cfg)


__all__ = [
    "WaterTrigger",
    "create_water_trigger",
    "is_aimed",
    "is_body_aligned",
    "is_target_aligned",
]
