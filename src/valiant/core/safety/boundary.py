"""Competition flight boundary and the flight-termination trigger it drives.

CONOPS v1.0 Appendix C gives the boundary for the Medicine Hat RC'ers club
site as six GPS coordinates. They are module constants rather than config,
because a boundary that can be overridden by a YAML file on someone's laptop
is not a safety feature.

CONOPS 4.5 requires that crossing the boundary automatically activates the
flight termination system. :class:`FlightBoundary` provides the detection; the
FTS hook is what wires it to the actual termination path.

Note on the CONOPS text: Appendix C's prose says the soft boundary is Table C1
and the hard boundary is Table C2, but the document contains exactly one table,
labelled "Table C1: Hard Flight Boundary GPS Coordinates". These six points are
coded as the *hard* boundary, and the soft boundary is derived as an inset. Ask
the judges to confirm before the FRR.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# CONOPS v1.0 Appendix C, Table C1. (latitude, longitude) in decimal degrees,
# in the order given, forming a closed non-convex polygon. Do not reorder.
HARD_BOUNDARY: tuple[tuple[float, float], ...] = (
    (50.0970884, -110.7328077),
    (50.1061216, -110.7327756),
    (50.1061482, -110.7437887),
    (50.1035232, -110.7437798),
    (50.0988785, -110.7382540),
    (50.0971194, -110.7382533),
)

# CARs limit for these operations, and the altitude referenced throughout the
# CONOPS. AGL, measured from the takeoff datum.
MAX_ALTITUDE_AGL_M = 100.0

# How far inside the hard boundary the soft boundary sits. Crossing the soft
# boundary is a warning to the crew; crossing the hard boundary terminates.
DEFAULT_SOFT_INSET_M = 15.0
DEFAULT_ALTITUDE_MARGIN_M = 5.0

_METRES_PER_DEG_LAT = 111_320.0


class BoundaryStatus(str, Enum):
    INSIDE = "inside"
    SOFT_WARNING = "soft_warning"
    OUTSIDE = "outside"
    ABOVE_CEILING = "above_ceiling"


@dataclass(frozen=True)
class BoundaryCheck:
    status: BoundaryStatus
    # Distance to the nearest boundary edge; positive inside, negative outside.
    distance_m: float
    altitude_agl_m: float
    reasons: tuple[str, ...] = ()

    @property
    def inside(self) -> bool:
        return self.status in (BoundaryStatus.INSIDE, BoundaryStatus.SOFT_WARNING)

    @property
    def terminate(self) -> bool:
        """Whether this check should trigger flight termination."""
        return self.status in (BoundaryStatus.OUTSIDE, BoundaryStatus.ABOVE_CEILING)


def _metres_per_deg_lon(lat_deg: float) -> float:
    return _METRES_PER_DEG_LAT * math.cos(math.radians(lat_deg))


def point_in_polygon(lat: float, lon: float, polygon=HARD_BOUNDARY) -> bool:
    """Ray-casting test, correct for non-convex polygons.

    The Appendix C outline is L-shaped (the club field plus the adjacent
    field), so a convex test would wrongly accept the notch.
    """
    inside = False
    n = len(polygon)
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[(i - 1) % n]
        # Does the edge straddle this latitude, and is the crossing east of us?
        if (lat_i > lat) != (lat_j > lat):
            span = lat_j - lat_i
            if abs(span) < 1e-12:
                continue
            lon_at_lat = lon_i + (lat - lat_i) / span * (lon_j - lon_i)
            if lon < lon_at_lat:
                inside = not inside
    return inside


def _point_segment_distance_m(
    lat: float,
    lon: float,
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Metres from a point to a segment, in a local flat projection."""
    m_lon = _metres_per_deg_lon(lat)
    px = (lon - a[1]) * m_lon
    py = (lat - a[0]) * _METRES_PER_DEG_LAT
    bx = (b[1] - a[1]) * m_lon
    by = (b[0] - a[0]) * _METRES_PER_DEG_LAT
    seg_len_sq = bx * bx + by * by
    if seg_len_sq < 1e-9:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * bx + py * by) / seg_len_sq))
    return math.hypot(px - t * bx, py - t * by)


def distance_to_edge_m(lat: float, lon: float, polygon=HARD_BOUNDARY) -> float:
    """Shortest distance to any boundary edge, in metres. Always positive."""
    n = len(polygon)
    return min(
        _point_segment_distance_m(lat, lon, polygon[i], polygon[(i + 1) % n])
        for i in range(n)
    )


def signed_distance_m(lat: float, lon: float, polygon=HARD_BOUNDARY) -> float:
    """Distance to the boundary; positive inside, negative outside."""
    d = distance_to_edge_m(lat, lon, polygon)
    return d if point_in_polygon(lat, lon, polygon) else -d


def polygon_bounds(polygon=HARD_BOUNDARY) -> tuple[float, float, float, float]:
    """(min_lat, min_lon, max_lat, max_lon) - for framing a map view."""
    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]
    return min(lats), min(lons), max(lats), max(lons)


def polygon_centroid(polygon=HARD_BOUNDARY) -> tuple[float, float]:
    return (
        sum(p[0] for p in polygon) / len(polygon),
        sum(p[1] for p in polygon) / len(polygon),
    )


class FlightBoundary:
    """Boundary monitor with a flight-termination hook.

    Call :meth:`check` on every position update. The first hard breach fires
    the registered FTS callback exactly once; repeated breaches do not re-fire,
    so the callback does not need to be idempotent.
    """

    def __init__(
        self,
        polygon=HARD_BOUNDARY,
        *,
        max_altitude_agl_m: float = MAX_ALTITUDE_AGL_M,
        soft_inset_m: float = DEFAULT_SOFT_INSET_M,
        altitude_margin_m: float = DEFAULT_ALTITUDE_MARGIN_M,
    ):
        if len(polygon) < 3:
            raise ValueError("A flight boundary needs at least 3 vertices")
        self.polygon = tuple(polygon)
        self.max_altitude_agl_m = float(max_altitude_agl_m)
        self.soft_inset_m = float(soft_inset_m)
        self.altitude_margin_m = float(altitude_margin_m)
        self._on_terminate = None
        self._terminated = False
        self._last: BoundaryCheck | None = None

    def on_terminate(self, callback) -> None:
        """Register the FTS trigger, called once on the first hard breach."""
        self._on_terminate = callback

    @property
    def terminated(self) -> bool:
        return self._terminated

    @property
    def last_check(self) -> BoundaryCheck | None:
        return self._last

    def reset(self) -> None:
        """Clear the latched termination state between flights."""
        self._terminated = False
        self._last = None

    def check(self, lat: float, lon: float, alt_agl_m: float) -> BoundaryCheck:
        distance = signed_distance_m(lat, lon, self.polygon)
        reasons: list[str] = []

        if distance < 0:
            status = BoundaryStatus.OUTSIDE
            reasons.append(f"outside lateral boundary by {abs(distance):.0f} m")
        elif alt_agl_m > self.max_altitude_agl_m:
            status = BoundaryStatus.ABOVE_CEILING
            reasons.append(
                f"above {self.max_altitude_agl_m:.0f} m AGL ceiling ({alt_agl_m:.0f} m)"
            )
        elif distance < self.soft_inset_m:
            status = BoundaryStatus.SOFT_WARNING
            reasons.append(f"within {distance:.0f} m of the boundary")
        elif alt_agl_m > self.max_altitude_agl_m - self.altitude_margin_m:
            status = BoundaryStatus.SOFT_WARNING
            reasons.append(f"approaching the altitude ceiling ({alt_agl_m:.0f} m AGL)")
        else:
            status = BoundaryStatus.INSIDE

        check = BoundaryCheck(
            status=status,
            distance_m=distance,
            altitude_agl_m=alt_agl_m,
            reasons=tuple(reasons),
        )
        self._last = check

        if check.terminate and not self._terminated:
            self._terminated = True
            print(f"[Boundary] BREACH: {'; '.join(check.reasons)} - triggering FTS")
            if self._on_terminate is not None:
                self._on_terminate(check)

        return check


def write_mission_planner_fence(path: str | Path, polygon=HARD_BOUNDARY) -> Path:
    """Write a Mission Planner-loadable polygon fence from the same constants.

    This is the backup for the CONOPS 4.2 GCS display requirement: load it in
    Mission Planner and the competition flight area is drawn alongside the live
    aircraft position, with no dependency on our own map view.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#saved by Valiant Aerotech - AEAC 2027 CONOPS Appendix C Table C1"]
    lines += [f"{lat:.7f} {lon:.7f}" for lat, lon in polygon]
    # Mission Planner expects the ring closed.
    lines.append(f"{polygon[0][0]:.7f} {polygon[0][1]:.7f}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
