"""Stay out of other UAVs' exclusion cylinders, and hold a Task 2 standoff.

Does not command the aircraft. Returns a suggested hold / offset so the
mission runner can stop flying into a cylinder. Companion never terminates.
"""

from __future__ import annotations

from dataclasses import dataclass

from valiant.comms.competition.traffic import (
    TASK2_STANDOFF_M,
    TrafficAircraft,
    horizontal_distance_m,
    inside_keepout,
)


@dataclass(frozen=True)
class DeconflictAdvice:
    clear: bool
    nearest_id: str | None
    nearest_m: float
    inside: tuple[str, ...]
    hold: bool


def advise(
    lat: float,
    lon: float,
    alt_agl_m: float,
    traffic: tuple[TrafficAircraft, ...],
) -> DeconflictAdvice:
    inside: list[str] = []
    nearest_id = None
    nearest_m = float("inf")
    for other in traffic:
        dist = horizontal_distance_m(lat, lon, other.lat, other.lon)
        if dist < nearest_m:
            nearest_m = dist
            nearest_id = other.uav_id
        if inside_keepout(lat, lon, alt_agl_m, other):
            inside.append(other.uav_id)
    if nearest_m is float("inf"):
        nearest_m = 0.0
        nearest_id = None
    return DeconflictAdvice(
        clear=not inside,
        nearest_id=nearest_id,
        nearest_m=nearest_m,
        inside=tuple(inside),
        hold=bool(inside),
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
