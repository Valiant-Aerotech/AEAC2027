"""Spray water: aim checks and actuation."""

from valiant.autonomy.spray.api import (
    WaterTrigger,
    create_water_trigger,
    is_aimed,
    is_body_aligned,
    is_target_aligned,
)

__all__ = [
    "WaterTrigger",
    "create_water_trigger",
    "is_aimed",
    "is_body_aligned",
    "is_target_aligned",
]
