"""CONOPS 5.2.3.7 — cluster deer fixes within a 10 m radius."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, Union

CLUSTER_RADIUS_M = 10.0
_EARTH_RADIUS_M = 6_371_000.0

LatLon = tuple[float, float]


@dataclass(frozen=True)
class ClusterPoint:
    """One ground fix to cluster (lat/lon degrees WGS84)."""

    lat: float
    lon: float
    id: str | None = None
    tag: str | None = None


PointLike = Union[ClusterPoint, LatLon, Sequence[float]]


def _as_lat_lon(point: PointLike) -> tuple[float, float]:
    if isinstance(point, ClusterPoint):
        return point.lat, point.lon
    if len(point) < 2:
        raise ValueError("point must provide lat and lon")
    return float(point[0]), float(point[1])


def meters_apart(a: PointLike, b: PointLike) -> float:
    """Equirectangular metre distance — accurate enough for field-scale clustering."""
    lat1, lon1 = _as_lat_lon(a)
    lat2, lon2 = _as_lat_lon(b)
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = lat2_r - lat1_r
    dlon = math.radians(lon2 - lon1)
    x = dlon * math.cos(0.5 * (lat1_r + lat2_r))
    y = dlat
    return _EARTH_RADIUS_M * math.hypot(x, y)


def cluster_fixes(
    points: Sequence[PointLike],
    radius_m: float = CLUSTER_RADIUS_M,
) -> list[list[PointLike]]:
    """Group points into clusters where members are connected within ``radius_m``.

    Connectivity is transitive: A–B and B–C within radius put A and C in the
    same cluster even if A–C exceeds the radius. Solo points are clusters of one.
    Order of clusters follows first appearance; order within a cluster preserves
    input order.
    """
    n = len(points)
    if n == 0:
        return []

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            if meters_apart(points[i], points[j]) <= radius_m:
                union(i, j)

    buckets: dict[int, list[PointLike]] = {}
    order: list[int] = []
    for i, point in enumerate(points):
        root = find(i)
        if root not in buckets:
            buckets[root] = []
            order.append(root)
        buckets[root].append(point)
    return [buckets[r] for r in order]
