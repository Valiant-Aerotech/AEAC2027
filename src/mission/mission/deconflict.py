"""Stay out of other UAVs' exclusion cylinders, and hold a Task 2 standoff.

Does not command the aircraft. Returns a suggested hold / offset so the
mission runner can stop flying into a cylinder. Companion never terminates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from mission.boundary import (
    DEFAULT_ALTITUDE_MARGIN_M,
    DEFAULT_SOFT_INSET_M,
    MAX_ALTITUDE_AGL_M,
    signed_distance_m,
)
from telemetry.traffic import (
    TASK2_STANDOFF_M,
    TrafficAircraft,
    TrafficSnapshot,
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
FLOOR_AGL_M = 8.0
CEILING_AGL_M = MAX_ALTITUDE_AGL_M - DEFAULT_ALTITUDE_MARGIN_M
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
    up_m_s: float = 0.0


class TrafficTracks:
    """Velocity and sample age from successive traffic snapshots. No ROS."""

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._sequence: int | None = None
        self._aircraft: dict[str, TrafficAircraft] = {}
        self._latest: dict[str, tuple[float, float, float, float]] = {}
        self._previous: dict[str, tuple[float, float, float, float]] = {}

    def observe(self, snapshot: TrafficSnapshot, now_s: float) -> bool:
        if (
            snapshot.session_id == self._session_id
            and self._sequence is not None
            and snapshot.sequence <= self._sequence
        ):
            return False

        if snapshot.session_id != self._session_id:
            self._aircraft.clear()
            self._latest.clear()
            self._previous.clear()

        seen: set[str] = set()
        for aircraft in snapshot.aircraft:
            seen.add(aircraft.uav_id)
            latest = self._latest.get(aircraft.uav_id)
            if latest is not None:
                self._previous[aircraft.uav_id] = latest
            self._aircraft[aircraft.uav_id] = aircraft
            self._latest[aircraft.uav_id] = (now_s, aircraft.lat, aircraft.lon, aircraft.alt_agl_m)

        for omitted in set(self._aircraft) - seen:
            self._aircraft.pop(omitted, None)
            self._latest.pop(omitted, None)
            self._previous.pop(omitted, None)

        self._session_id = snapshot.session_id
        self._sequence = snapshot.sequence
        return True

    def motions(self, now_s: float) -> tuple[TrafficMotion, ...]:
        out: list[TrafficMotion] = []
        for uav_id, aircraft in self._aircraft.items():
            latest = self._latest[uav_id]
            previous = self._previous.get(aircraft.uav_id)
            north_m_s = 0.0
            east_m_s = 0.0
            up_m_s = 0.0
            if previous is not None and latest is not None:
                dt = latest[0] - previous[0]
                if dt > 0.05:
                    north, east = offset_m(latest[1], latest[2], previous[1], previous[2])
                    north_m_s = north / dt
                    east_m_s = east / dt
                    up_m_s = (latest[3] - previous[3]) / dt
            age = max(0.0, now_s - latest[0])
            out.append(TrafficMotion(aircraft, north_m_s, east_m_s, age, up_m_s))
        return tuple(out)


def buffer_radius_m(motion: TrafficMotion) -> float:
    """Keep-away plus 10 m, grown by how far it can travel before the next sample."""
    speed = math.hypot(motion.north_m_s, motion.east_m_s)
    return motion.aircraft.keepout_radius_m + BUFFER_M + speed * max(0.0, motion.age_s)


def _to_other(lat: float, lon: float, other: TrafficAircraft) -> tuple[float, float]:
    """North and east metres from us to the other aircraft."""
    return offset_m(other.lat, other.lon, lat, lon)


def _overlaps(alt_agl_m: float, motion: TrafficMotion) -> bool:
    """True when the next 5 s of the other altitude meets our vertical keep-away.

    A climb that stays above the band is ignored. A descent that will enter
    the band is avoided before the heights meet.
    """
    if not math.isfinite(alt_agl_m):
        return True
    height = motion.aircraft.keepout_height_m
    start = motion.aircraft.alt_agl_m
    end = start + motion.up_m_s * LEAD_S
    low = min(start, end)
    high = max(start, end)
    return low <= alt_agl_m + height and high >= alt_agl_m - height


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
        if not _overlaps(alt_agl_m, motion):
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
        if not _overlaps(alt_agl_m, motion):
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


def _two_nearest(
    capsules: list[tuple[float, float, float, float, float]],
) -> list[tuple[float, float]]:
    ranked = sorted(capsules, key=lambda item: math.hypot(item[0], item[1]))
    return [(item[0], item[1]) for item in ranked[:2]]


def _toward_both(north_m: float, east_m: float, pair: list[tuple[float, float]]) -> bool:
    """True when this step moves closer to both of the two nearest aircraft.

    That direction is the slit between them.
    """
    if len(pair) < 2 or (north_m == 0.0 and east_m == 0.0):
        return False
    return all(north_m * north + east_m * east > 0.0 for north, east in pair)


def _ray_clearance(
    north_m: float,
    east_m: float,
    capsules: list[tuple[float, float, float, float, float]],
) -> float:
    clearance = math.inf
    for start_n, start_e, end_n, end_e, radius in capsules:
        gap = _segment_distance(north_m, east_m, start_n, start_e, end_n, end_e) - radius
        if gap < clearance:
            clearance = gap
    return clearance


def _blocks_hover(lat: float, lon: float, motion: TrafficMotion) -> bool:
    """True when the hover sits inside this aircraft's horizontal buffer."""
    north, east = _to_other(lat, lon, motion.aircraft)
    if math.hypot(north, east) > SCAN_RANGE_M:
        return False
    return (
        _segment_distance(
            0.0,
            0.0,
            north,
            east,
            north + motion.north_m_s * LEAD_S,
            east + motion.east_m_s * LEAD_S,
        )
        < buffer_radius_m(motion) - 0.05
    )


def _altitude_clear(alt_agl_m: float, motions: tuple[TrafficMotion, ...]) -> bool:
    for motion in motions:
        height = motion.aircraft.keepout_height_m
        start = motion.aircraft.alt_agl_m
        end = start + motion.up_m_s * LEAD_S
        low = min(start, end) - height
        high = max(start, end) + height
        if low <= alt_agl_m <= high:
            return False
    return True


def _vertical_step(alt_agl_m: float, motions: tuple[TrafficMotion, ...]) -> float:
    """Metres up (positive) that leaves every blocking band. Zero means stay."""
    if not math.isfinite(alt_agl_m) or not motions or _altitude_clear(alt_agl_m, motions):
        return 0.0
    for step in range(1, int(ESCAPE_CAP_M) + 1):
        for sign in (1.0, -1.0):
            target = alt_agl_m + sign * step
            if target < FLOOR_AGL_M or target > CEILING_AGL_M:
                continue
            if _altitude_clear(target, motions):
                return sign * step
    return 0.0


def hover_escape(
    lat: float,
    lon: float,
    alt_agl_m: float,
    motions: tuple[TrafficMotion, ...],
    prefer: tuple[float, ...] | None = None,
) -> tuple[float, float, float]:
    """North, east, and up metres that keep a hover outside every buffer.

    The other aircraft does not dodge. A zero-velocity hover that lies in its
    path is a full velocity obstacle: the step clears the track it will fly
    over the next few seconds. Rays through the slit between the two nearest
    aircraft are dropped. Among the rest, the step with the most room is kept.
    Up or down is used only when no horizontal ray is clear and inside the
    field. ``prefer`` repeats a step that is still clear. Each axis is capped
    at 40 m. Zero means stay.
    """
    capsules = _capsules(lat, lon, alt_agl_m, motions)
    if not capsules:
        return (0.0, 0.0, 0.0)
    clamp = signed_distance_m(lat, lon) > -FIELD_CLAMP_M
    if _clear_of(0.0, 0.0, capsules) and _inside_field(lat, lon, 0.0, 0.0, clamp):
        return (0.0, 0.0, 0.0)
    nearest = _two_nearest(capsules)
    if (
        prefer is not None
        and len(prefer) >= 2
        and (prefer[0] != 0.0 or prefer[1] != 0.0)
        and _clear_of(prefer[0], prefer[1], capsules)
        and _inside_field(lat, lon, prefer[0], prefer[1], clamp)
        and not _toward_both(prefer[0], prefer[1], nearest)
    ):
        return (prefer[0], prefer[1], 0.0)

    best: tuple[float, float] | None = None
    best_clearance = -math.inf
    for index in range(SECTOR_COUNT):
        bearing = math.radians(index * SECTOR_DEG)
        north_hat = math.cos(bearing)
        east_hat = math.sin(bearing)
        if _toward_both(north_hat, east_hat, nearest):
            continue
        ray_best: tuple[float, float] | None = None
        ray_clearance = -math.inf
        for step in range(1, int(ESCAPE_CAP_M) + 1):
            point_n = north_hat * step
            point_e = east_hat * step
            length = math.hypot(point_n, point_e)
            if length > ESCAPE_CAP_M:
                scale = ESCAPE_CAP_M / length
                point_n *= scale
                point_e *= scale
            if not _clear_of(point_n, point_e, capsules):
                continue
            if not _inside_field(lat, lon, point_n, point_e, clamp):
                continue
            clearance = _ray_clearance(point_n, point_e, capsules)
            if clearance > ray_clearance:
                ray_clearance = clearance
                ray_best = (point_n, point_e)
        if ray_best is not None and ray_clearance > best_clearance:
            best_clearance = ray_clearance
            best = ray_best
    blockers = tuple(motion for motion in motions if _blocks_hover(lat, lon, motion))
    if best is None:
        remembered = 0.0 if prefer is None or len(prefer) < 3 else prefer[2]
        if remembered != 0.0 and math.isfinite(alt_agl_m):
            target = alt_agl_m + remembered
            if FLOOR_AGL_M <= target <= CEILING_AGL_M and _altitude_clear(target, blockers):
                return (0.0, 0.0, remembered)
        return (0.0, 0.0, _vertical_step(alt_agl_m, blockers))
    return (best[0], best[1], 0.0)


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
    north_m, east_m, up_m = hover_escape(lat, lon, alt_agl_m, motions)
    return math.hypot(north_m, east_m) < 0.5 and abs(up_m) < 0.5


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
