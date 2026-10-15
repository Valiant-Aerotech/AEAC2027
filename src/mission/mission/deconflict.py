"""Stay out of other UAVs' exclusion cylinders, and hold a Task 2 standoff.

Does not command the aircraft. Returns a suggested hold / offset so the
mission runner can stop flying into a cylinder. Companion never terminates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from mission.boundary import DEFAULT_SOFT_INSET_M, signed_distance_m
from telemetry.traffic import (
    TASK2_STANDOFF_M,
    TrafficAircraft,
    horizontal_distance_m,
    inside_keepout,
    offset_m,
)

# Server keep-away plus this margin is the circle the aircraft holds.
BUFFER_M = 10.0
# ObstacleDistance bins past this range stay empty.
SCAN_RANGE_M = 100.0
SECTOR_COUNT = 72
SECTOR_DEG = 360.0 / SECTOR_COUNT
# How far ahead a published path is treated as a moving circle.
LEAD_S = 5.0
ESCAPE_CAP_M = 40.0
# Medicine Hat clamp applies only when the aircraft is actually near that polygon.
FIELD_CLAMP_M = 2_000.0
_METRES_PER_DEG_LAT = 111_320.0


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


@dataclass(frozen=True)
class TrafficMotion:
    """One server aircraft plus the velocity implied by the last two samples."""

    aircraft: TrafficAircraft
    north_m_s: float = 0.0
    east_m_s: float = 0.0
    age_s: float = 0.0


class TrafficTracks:
    """Velocity and sample age from successive traffic snapshots. No ROS."""

    def __init__(self) -> None:
        self._latest: dict[str, tuple[float, float, float]] = {}
        self._previous: dict[str, tuple[float, float, float]] = {}

    def motions(self, traffic: tuple[TrafficAircraft, ...], now_s: float) -> tuple[TrafficMotion, ...]:
        seen: set[str] = set()
        out: list[TrafficMotion] = []
        for aircraft in traffic:
            seen.add(aircraft.uav_id)
            latest = self._latest.get(aircraft.uav_id)
            moved = latest is None or horizontal_distance_m(latest[1], latest[2], aircraft.lat, aircraft.lon) > 0.5
            if moved:
                if latest is not None:
                    self._previous[aircraft.uav_id] = latest
                latest = (now_s, aircraft.lat, aircraft.lon)
                self._latest[aircraft.uav_id] = latest
            previous = self._previous.get(aircraft.uav_id)
            north_m_s = 0.0
            east_m_s = 0.0
            if previous is not None and latest is not None:
                dt = latest[0] - previous[0]
                if dt > 0.05:
                    north, east = offset_m(latest[1], latest[2], previous[1], previous[2])
                    north_m_s = north / dt
                    east_m_s = east / dt
            age = 0.0 if latest is None else max(0.0, now_s - latest[0])
            out.append(TrafficMotion(aircraft, north_m_s, east_m_s, age))
        for stale in [key for key in self._latest if key not in seen]:
            self._latest.pop(stale, None)
            self._previous.pop(stale, None)
        return tuple(out)


def buffer_radius_m(motion: TrafficMotion) -> float:
    """Keep-away plus 10 m, grown by how far it can travel before the next sample."""
    speed = math.hypot(motion.north_m_s, motion.east_m_s)
    return motion.aircraft.keepout_radius_m + BUFFER_M + speed * max(0.0, motion.age_s)


def _to_other(lat: float, lon: float, other: TrafficAircraft) -> tuple[float, float]:
    """North and east metres from us to the other aircraft."""
    return offset_m(other.lat, other.lon, lat, lon)


def _overlaps(alt_agl_m: float, other: TrafficAircraft) -> bool:
    if not math.isfinite(alt_agl_m):
        return True
    return abs(alt_agl_m - other.alt_agl_m) <= other.keepout_height_m


def _bearing_deg(north_m: float, east_m: float) -> float:
    return math.degrees(math.atan2(east_m, north_m)) % 360.0


def _angle_between(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def sector_scan(
    lat: float,
    lon: float,
    alt_agl_m: float,
    motions: tuple[TrafficMotion, ...],
) -> tuple[float, ...]:
    """72 north-referenced distances in metres.

    Index 0 is north and index 18 is east. A finite value is the range minus
    the blocked radius, so the reported wall sits on the buffer circle. Empty
    sectors are positive infinity (no data).
    """
    bins = [math.inf] * SECTOR_COUNT
    for motion in motions:
        if not _overlaps(alt_agl_m, motion.aircraft):
            continue
        north, east = _to_other(lat, lon, motion.aircraft)
        distance = math.hypot(north, east)
        if distance > SCAN_RANGE_M:
            continue
        if distance < 1e-3:
            for index in range(SECTOR_COUNT):
                if bins[index] > 0.0:
                    bins[index] = 0.0
            continue
        radius = buffer_radius_m(motion)
        half_deg = 90.0 if distance < radius else math.degrees(math.asin(min(1.0, radius / distance)))
        bearing = _bearing_deg(north, east)
        reported = distance - radius
        for index in range(SECTOR_COUNT):
            if _angle_between(index * SECTOR_DEG, bearing) > half_deg:
                continue
            if reported < bins[index]:
                bins[index] = reported
    return tuple(bins)


def _segment_distance(
    north_m: float,
    east_m: float,
    start_n: float,
    start_e: float,
    end_n: float,
    end_e: float,
) -> float:
    span_n = end_n - start_n
    span_e = end_e - start_e
    length_sq = span_n * span_n + span_e * span_e
    if length_sq < 1e-9:
        return math.hypot(north_m - start_n, east_m - start_e)
    scale = ((north_m - start_n) * span_n + (east_m - start_e) * span_e) / length_sq
    scale = max(0.0, min(1.0, scale))
    return math.hypot(north_m - (start_n + scale * span_n), east_m - (start_e + scale * span_e))


def _capsules(
    lat: float,
    lon: float,
    alt_agl_m: float,
    motions: tuple[TrafficMotion, ...],
) -> list[tuple[float, float, float, float, float]]:
    capsules = []
    for motion in motions:
        if not _overlaps(alt_agl_m, motion.aircraft):
            continue
        north, east = _to_other(lat, lon, motion.aircraft)
        if math.hypot(north, east) > SCAN_RANGE_M:
            continue
        radius = buffer_radius_m(motion)
        capsules.append(
            (
                north,
                east,
                north + motion.north_m_s * LEAD_S,
                east + motion.east_m_s * LEAD_S,
                radius,
            )
        )
    return capsules


def _clear_of(
    north_m: float,
    east_m: float,
    capsules: list[tuple[float, float, float, float, float]],
) -> bool:
    for start_n, start_e, end_n, end_e, radius in capsules:
        if _segment_distance(north_m, east_m, start_n, start_e, end_n, end_e) < radius - 0.05:
            return False
    return True


def _inside_field(lat: float, lon: float, north_m: float, east_m: float, clamp: bool) -> bool:
    if not clamp:
        return True
    lat2 = lat + north_m / _METRES_PER_DEG_LAT
    lon2 = lon + east_m / (_METRES_PER_DEG_LAT * math.cos(math.radians(lat)))
    return signed_distance_m(lat2, lon2) >= DEFAULT_SOFT_INSET_M


def hover_escape(
    lat: float,
    lon: float,
    alt_agl_m: float,
    motions: tuple[TrafficMotion, ...],
) -> tuple[float, float]:
    """Shortest north/east step, in metres, that keeps a hover outside every buffer.

    The other aircraft does not dodge. A zero-velocity hover that lies in its
    path is a full velocity obstacle: the step clears the track it will fly
    over the next few seconds. The step is capped at 40 m. Zero means stay.
    """
    capsules = _capsules(lat, lon, alt_agl_m, motions)
    if not capsules:
        return (0.0, 0.0)
    clamp = signed_distance_m(lat, lon) > -FIELD_CLAMP_M
    if _clear_of(0.0, 0.0, capsules) and _inside_field(lat, lon, 0.0, 0.0, clamp):
        return (0.0, 0.0)

    best: tuple[float, float] | None = None
    best_d = ESCAPE_CAP_M + 1.0
    for index in range(SECTOR_COUNT):
        bearing = math.radians(index * SECTOR_DEG)
        north_hat = math.cos(bearing)
        east_hat = math.sin(bearing)
        for step in range(1, int(ESCAPE_CAP_M) + 1):
            point_n = north_hat * step
            point_e = east_hat * step
            if not _clear_of(point_n, point_e, capsules):
                continue
            if not _inside_field(lat, lon, point_n, point_e, clamp):
                continue
            if step < best_d:
                best_d = step
                best = (point_n, point_e)
            break
    if best is None:
        return (0.0, 0.0)
    return best


def hover_is_blocked(
    lat: float,
    lon: float,
    alt_agl_m: float,
    motions: tuple[TrafficMotion, ...],
) -> bool:
    """True when a hover is inside a buffer and no step inside the cap gets out."""
    capsules = _capsules(lat, lon, alt_agl_m, motions)
    if not capsules or _clear_of(0.0, 0.0, capsules):
        return False
    north_m, east_m = hover_escape(lat, lon, alt_agl_m, motions)
    return math.hypot(north_m, east_m) < 0.5


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
