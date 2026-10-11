"""Stay out of other UAVs' exclusion cylinders, and hold a Task 2 standoff.

Does not command the aircraft. Returns a suggested hold / offset so the
mission runner can stop flying into a cylinder. Companion never terminates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from telemetry.traffic import (
    TASK2_STANDOFF_M,
    TrafficAircraft,
    horizontal_distance_m,
    inside_keepout,
    offset_m,
)


@dataclass(frozen=True)
class DeconflictAdvice:
    clear: bool
    nearest_id: str | None
    nearest_m: float
    inside: tuple[str, ...]
    hold: bool
    approaching: tuple[str, ...] = ()
    avoid: bool = False


def _future_closest_m(
    north_m: float,
    east_m: float,
    speed_m_s: float,
    heading_deg: float,
    horizon_s: float,
) -> float | None:
    """Closest range on (0, horizon], or None when the track is not closing.

    Heading is degrees clockwise from north. The other aircraft is stationary.
    A closest point at or before now means the contact is opening or abeam.
    """
    if speed_m_s <= 0.0 or horizon_s <= 0.0:
        return None
    heading = math.radians(heading_deg)
    north_rate = speed_m_s * math.cos(heading)
    east_rate = speed_m_s * math.sin(heading)
    speed_sq = north_rate * north_rate + east_rate * east_rate
    if speed_sq <= 0.0:
        return None
    time_s = -(north_m * north_rate + east_m * east_rate) / speed_sq
    if time_s <= 0.0:
        return None
    time_s = min(time_s, horizon_s)
    return math.hypot(north_m + north_rate * time_s, east_m + east_rate * time_s)


def advise(
    lat: float,
    lon: float,
    alt_agl_m: float,
    traffic: tuple[TrafficAircraft, ...],
    *,
    speed_m_s: float = 0.0,
    heading_deg: float = 0.0,
    feed_delay_s: float = 1.0,
    reaction_s: float = 1.0,
) -> DeconflictAdvice:
    horizon_s = feed_delay_s + reaction_s
    inside: list[str] = []
    approaching: list[str] = []
    nearest_id = None
    nearest_m = float("inf")
    for other in traffic:
        dist = horizontal_distance_m(lat, lon, other.lat, other.lon)
        if dist < nearest_m:
            nearest_m = dist
            nearest_id = other.uav_id
        if inside_keepout(lat, lon, alt_agl_m, other):
            inside.append(other.uav_id)
        outer_m = other.keepout_radius_m + speed_m_s * horizon_s
        if dist > outer_m:
            continue
        if abs(alt_agl_m - other.alt_agl_m) > other.keepout_height_m:
            continue
        north_m, east_m = offset_m(lat, lon, other.lat, other.lon)
        closest_m = _future_closest_m(north_m, east_m, speed_m_s, heading_deg, horizon_s)
        if closest_m is not None and closest_m < other.keepout_radius_m:
            approaching.append(other.uav_id)
    return DeconflictAdvice(
        clear=not inside,
        nearest_id=nearest_id,
        nearest_m=nearest_m,
        inside=tuple(inside),
        hold=bool(inside),
        approaching=tuple(approaching),
        avoid=bool(approaching),
    )


def standoff_reached(
    lat: float,
    lon: float,
    animal_lat: float,
    animal_lon: float,
    *,
    min_m: float = TASK2_STANDOFF_M,
) -> bool:
    """True once the aircraft is at least ``min_m`` from the animal (Task 2)."""
    return horizontal_distance_m(lat, lon, animal_lat, animal_lon) >= min_m
