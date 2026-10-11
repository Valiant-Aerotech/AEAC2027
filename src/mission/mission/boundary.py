"""Competition flight boundary. Advisory only - this module never terminates.

CONOPS v1.0 Appendix C gives the boundary for the Medicine Hat RC'ers club
site as six GPS coordinates. They are module constants rather than config,
because a boundary that can be overridden by a YAML file on someone's laptop
is not a safety feature.

Who enforces what
-----------------
The flight controller is the sole enforcer. The hard polygon below is exported
by :func:`write_polygon_file`, loaded into Mission Planner by hand, and written
to the autopilot as an inclusion fence, where ``FENCE_ACTION = 2`` (Always
Land) with ``LAND_SPEED >= 200`` cm/s satisfies CONOPS 4.5. That path involves
no companion computer, no Python, and nothing that can crash mid-flight.

This module is the *advisory* half, and the rules themselves draw the line.
CONOPS 4.2: if the aircraft leaves the **soft** boundary "the operator will be
required to bring it back within the boundary", and only on leaving the
**hard** boundary "it must be terminated immediately". So a soft breach is a
human recovery, which means the useful thing software can do is warn the crew
early and stop flying further out. :class:`BoundaryMonitor` does exactly that
and nothing more. There is deliberately no termination hook: a second path to
killing the aircraft is a second thing that can kill it by mistake.

Note on the CONOPS text: Appendix C's prose says the soft boundary is Table C1
and the hard boundary is Table C2, but the document contains exactly one table,
labelled "Table C1: Hard Flight Boundary GPS Coordinates", and no Table C2 at
all. So one boundary is missing and the other is labelled both ways. These six
points are coded as the hard boundary and the soft boundary is derived as an
inset, which makes ``DEFAULT_SOFT_INSET_M`` our invention until a judge
confirms it. Outstanding question tracked in docs/conops-2027.md.
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
# boundary warns the crew and stops the mission; crossing the hard boundary is
# the flight controller's business, not ours. See the module docstring on why
# this number is currently a guess.
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
        """Inside the hard boundary, warning band included."""
        return self.status in (BoundaryStatus.INSIDE, BoundaryStatus.SOFT_WARNING)

    @property
    def should_stop(self) -> bool:
        """Whether the mission should stop flying further out.

        True from the soft warning onward. Deliberately not called
        ``terminate``: stopping is ours, terminating is the autopilot's.
        """
        return self.status is not BoundaryStatus.INSIDE


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
    """Pure geometry: where is the aircraft relative to the boundary.

    Call :meth:`check` on every position update. Holds no state beyond the
    last result, commands nothing, and has no side effects. Wrap it in
    :class:`BoundaryMonitor` to get crew messaging out of it.
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
        self._last: BoundaryCheck | None = None

    @property
    def last_check(self) -> BoundaryCheck | None:
        return self._last

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
        return check


def boundary_status_text(check: BoundaryCheck) -> str:
    """One short line for the Mission Planner HUD, within the 50-char limit."""
    if check.status is BoundaryStatus.INSIDE:
        return f"In bounds, {check.distance_m:.0f}m to edge"
    if check.status is BoundaryStatus.SOFT_WARNING:
        return f"NEAR EDGE {check.distance_m:.0f}m - stopping"
    if check.status is BoundaryStatus.ABOVE_CEILING:
        return f"CEILING {check.altitude_agl_m:.0f}m AGL - descend"
    return f"OUTSIDE by {abs(check.distance_m):.0f}m - recover now"


class BoundaryMonitor:
    """Turns boundary checks into crew warnings. Commands nothing.

    Sends one STATUSTEXT per status *change* rather than per fix, so the
    Mission Planner Messages tab stays readable at 1 Hz. The return value of
    :meth:`update` tells the caller's mission loop whether to stop flying
    outward; what to do about that is the mission's decision, not ours.
    """

    def __init__(self, boundary: FlightBoundary | None = None, *, hud=None):
        self.boundary = boundary or FlightBoundary()
        self._hud = hud
        self._last_status: BoundaryStatus | None = None
        self._breaches = 0

    @property
    def breaches(self) -> int:
        """How many times the aircraft has left the soft boundary."""
        return self._breaches

    def reset(self) -> None:
        self._last_status = None
        self._breaches = 0

    def update(self, lat: float, lon: float, alt_agl_m: float) -> BoundaryCheck:
        check = self.boundary.check(lat, lon, alt_agl_m)

        if check.status is not self._last_status:
            if check.should_stop:
                self._breaches += 1
                print(f"[Boundary] {'; '.join(check.reasons)}")
            if self._hud is not None:
                self._hud.send(boundary_status_text(check), force=check.should_stop)
            self._last_status = check.status

        return check


def write_polygon_file(path: str | Path, polygon=HARD_BOUNDARY) -> Path:
    """Write the boundary as a Mission Planner polygon file.

    Emits the ``.poly`` format Mission Planner's Plan screen reads via Load
    Polygon. From there: polygon tool, Fence Inclusion, Write. That is the
    documented path to an ArduPilot inclusion fence, and it means the
    coordinates the autopilot enforces come from the same six constants this
    module checks against, rather than from someone clicking on a map.

    The ring is left open. Mission Planner closes the polygon itself, so
    repeating the first vertex here produces a duplicate seventh point in the
    uploaded fence.

    Loading it also satisfies CONOPS 4.2: Mission Planner then draws the
    competition flight area alongside the live aircraft position, which is the
    required GCS display.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#saved by Valiant Aerotech - AEAC 2027 CONOPS v1.0 Appendix C Table C1"]
    lines += [f"{lat:.7f} {lon:.7f}" for lat, lon in polygon]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
