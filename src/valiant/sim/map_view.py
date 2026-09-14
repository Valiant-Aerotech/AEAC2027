"""Top-down map view for simulation and development. Not a flight-line tool.

**Mission Planner is the competition GCS display.** CONOPS 4.2 requires that
"a ground control station must always show the aircraft's real-time location
and the competition flight area", and Mission Planner does exactly that once
the boundary from :func:`~valiant.core.safety.boundary.write_polygon_file` is
loaded as an inclusion fence. Using it means the display, the geofence and the
termination action are one configuration instead of three, which is the whole
point: fewer things to babysit while the window is running.

This module exists because watching a SITL run through Mission Planner is
awkward, and because it can draw things Mission Planner cannot - competition
traffic with their exclusion cylinders, and the soft boundary inset. It reads
the same Appendix C constants, so what you watch in simulation matches what
the crew sees in the field.

Do not put this on the flight line. It is a second window to go wrong during
a scored window, for a requirement that is already met.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from valiant.comms.draw import (
    C_BOUNDARY,
    C_GREEN,
    C_MUTED,
    C_TEXT,
    draw_compass,
    draw_corner_brackets,
    draw_drone_icon,
    draw_footer,
    draw_scale_bar,
    draw_title_bar,
    vignette,
)
from valiant.core.geo import offset_lat_lon
from valiant.core.map_asset import GeoMapAsset
from valiant.core.safety.boundary import (
    HARD_BOUNDARY,
    BoundaryStatus,
    FlightBoundary,
    polygon_centroid,
    signed_distance_m,
)

DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 720
DEFAULT_VIEW_RADIUS_M = 600.0

C_TRACK = (120, 200, 255)
C_TRAFFIC = (90, 120, 255)
C_SOFT = (90, 190, 255)
C_BREACH = (70, 70, 235)

_METRES_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class MapVehicle:
    """One aircraft to draw: ours, or traffic from the competition server."""

    lat: float
    lon: float
    alt_agl_m: float = 0.0
    yaw_rad: float = 0.0
    label: str = ""
    # Exclusion cylinder, when the server publishes one for this aircraft.
    keepout_radius_m: float | None = None


class SimMapView:
    """Live map of the flight area and everything flying in it.

    Keeps the flown track between frames, so call :meth:`render` on every
    position update rather than only when you want to display.
    """

    def __init__(
        self,
        *,
        boundary: FlightBoundary | None = None,
        map_asset: GeoMapAsset | None = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        view_radius_m: float = DEFAULT_VIEW_RADIUS_M,
        follow_aircraft: bool = False,
        max_track_points: int = 4000,
    ):
        self.boundary = boundary or FlightBoundary()
        self.map_asset = map_asset
        self.width = width
        self.height = height
        self.view_radius_m = view_radius_m
        # False frames the whole flight area, which is what a judge wants to
        # see. True follows the aircraft, which is better for close work.
        self.follow_aircraft = follow_aircraft
        self.max_track_points = max_track_points
        self._track: list[tuple[float, float]] = []
        self._center = polygon_centroid(self.boundary.polygon)

    def clear_track(self) -> None:
        self._track.clear()

    # --- projection ----------------------------------------------------------

    def _scale(self) -> float:
        """Screen pixels per metre."""
        return min(self.width, self.height) / (2.0 * self.view_radius_m)

    def _to_screen(self, lat: float, lon: float) -> tuple[int, int]:
        clat, clon = self._center
        scale = self._scale()
        east_m = (lon - clon) * _METRES_PER_DEG_LAT * math.cos(math.radians(clat))
        north_m = (lat - clat) * _METRES_PER_DEG_LAT
        return (
            int(self.width / 2 + east_m * scale),
            int(self.height / 2 - north_m * scale),
        )

    def fit_to_boundary(self, *, margin_frac: float = 0.15) -> None:
        """Set the view radius so the whole polygon is comfortably visible."""
        clat, clon = polygon_centroid(self.boundary.polygon)
        worst = 0.0
        for lat, lon in self.boundary.polygon:
            east_m = (lon - clon) * _METRES_PER_DEG_LAT * math.cos(math.radians(clat))
            north_m = (lat - clat) * _METRES_PER_DEG_LAT
            worst = max(worst, abs(east_m), abs(north_m))
        self.view_radius_m = worst * (1.0 + margin_frac)
        self._center = (clat, clon)

    # --- rendering -----------------------------------------------------------

    def _backdrop(self) -> np.ndarray:
        if self.map_asset is not None:
            clat, clon = self._center
            north_m = (clat - self.map_asset.home_lat_deg) * _METRES_PER_DEG_LAT
            east_m = (
                (clon - self.map_asset.home_lon_deg)
                * _METRES_PER_DEG_LAT
                * math.cos(math.radians(clat))
            )
            return self.map_asset.crop_drone_centered(
                north_m,
                east_m,
                width=self.width,
                height=self.height,
                view_radius_m=self.view_radius_m,
            ).copy()
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[:] = (22, 24, 30)
        for i in range(0, self.width, 48):
            cv2.line(img, (i, 0), (i, self.height), (32, 34, 40), 1)
        for j in range(0, self.height, 48):
            cv2.line(img, (0, j), (self.width, j), (32, 34, 40), 1)
        return img

    def _draw_boundary(self, img: np.ndarray) -> None:
        pts = np.array(
            [self._to_screen(lat, lon) for lat, lon in self.boundary.polygon],
            dtype=np.int32,
        )
        cv2.polylines(img, [pts], True, C_BOUNDARY, 3, cv2.LINE_AA)
        # Soft boundary as a dashed inset, so the crew sees the warning band.
        inset = self._inset_polygon(self.boundary.soft_inset_m)
        if inset is not None:
            inset_pts = np.array([self._to_screen(la, lo) for la, lo in inset], dtype=np.int32)
            cv2.polylines(img, [inset_pts], True, C_SOFT, 1, cv2.LINE_AA)

    def _inset_polygon(self, inset_m: float):
        """Approximate inset by pulling each vertex toward the centroid.

        Good enough to show the crew roughly where the warning band starts;
        the authoritative soft check is the distance test in
        ``core.safety.boundary``, not this drawing.
        """
        if inset_m <= 0:
            return None
        clat, clon = polygon_centroid(self.boundary.polygon)
        out = []
        for lat, lon in self.boundary.polygon:
            east_m = (lon - clon) * _METRES_PER_DEG_LAT * math.cos(math.radians(clat))
            north_m = (lat - clat) * _METRES_PER_DEG_LAT
            dist = math.hypot(east_m, north_m)
            if dist < 1e-6:
                out.append((lat, lon))
                continue
            shrink = max(0.0, (dist - inset_m) / dist)
            out.append(offset_lat_lon(clat, clon, north_m * shrink, east_m * shrink))
        return out

    def _draw_track(self, img: np.ndarray) -> None:
        if len(self._track) < 2:
            return
        pts = np.array([self._to_screen(la, lo) for la, lo in self._track], dtype=np.int32)
        cv2.polylines(img, [pts], False, C_TRACK, 1, cv2.LINE_AA)

    def _draw_traffic(self, img: np.ndarray, traffic) -> None:
        scale = self._scale()
        for other in traffic:
            sx, sy = self._to_screen(other.lat, other.lon)
            if other.keepout_radius_m:
                cv2.circle(
                    img, (sx, sy), max(int(other.keepout_radius_m * scale), 3),
                    C_TRAFFIC, 1, cv2.LINE_AA,
                )
            cv2.circle(img, (sx, sy), 5, C_TRAFFIC, -1, cv2.LINE_AA)
            label = other.label or "traffic"
            cv2.putText(
                img, f"{label} {other.alt_agl_m:.0f}m", (sx + 8, sy - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, C_TRAFFIC, 1, cv2.LINE_AA,
            )

    def render(
        self,
        aircraft: MapVehicle | None,
        traffic: list[MapVehicle] | None = None,
        *,
        state: str = "",
    ) -> np.ndarray:
        if aircraft is not None and self.follow_aircraft:
            self._center = (aircraft.lat, aircraft.lon)

        img = self._backdrop()
        overlay = img.copy()
        self._draw_boundary(overlay)

        if aircraft is not None:
            self._track.append((aircraft.lat, aircraft.lon))
            if len(self._track) > self.max_track_points:
                del self._track[: len(self._track) - self.max_track_points]
        self._draw_track(overlay)
        self._draw_traffic(overlay, traffic or [])

        status = BoundaryStatus.INSIDE
        distance_m = 0.0
        if aircraft is not None:
            sx, sy = self._to_screen(aircraft.lat, aircraft.lon)
            draw_drone_icon(overlay, sx, sy, aircraft.yaw_rad, scale=1.2)
            check = self.boundary.check(aircraft.lat, aircraft.lon, aircraft.alt_agl_m)
            status = check.status
            distance_m = check.distance_m

        cv2.addWeighted(overlay, 0.94, img, 0.06, 0, img)
        vignette(img, 0.22)
        draw_corner_brackets(img, margin=8, length=18)

        banner = {
            BoundaryStatus.INSIDE: "",
            BoundaryStatus.SOFT_WARNING: "APPROACHING BOUNDARY",
            BoundaryStatus.OUTSIDE: "BOUNDARY BREACH - FTS",
            BoundaryStatus.ABOVE_CEILING: "ABOVE 100 m AGL - FTS",
        }[status]
        draw_title_bar(img, "FLIGHT AREA", banner or state)
        if banner:
            colour = C_SOFT if status is BoundaryStatus.SOFT_WARNING else C_BREACH
            cv2.rectangle(img, (0, 0), (self.width, 4), colour, -1)
            cv2.rectangle(img, (0, self.height - 4), (self.width, self.height), colour, -1)

        draw_compass(img, self.width - 40, 56, radius=26)
        scale_m = 100.0 if self.view_radius_m > 250 else 25.0
        draw_scale_bar(img, 16, self.height - 52, scale_m, self._scale())

        if aircraft is not None:
            draw_footer(
                img,
                f"{aircraft.lat:.6f}, {aircraft.lon:.6f}  |  "
                f"{aircraft.alt_agl_m:.0f} m AGL  |  {distance_m:+.0f} m to boundary",
                right="Esri" if self.map_asset else "",
            )
        else:
            cv2.putText(
                img, "NO POSITION", (16, self.height - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, C_MUTED, 1, cv2.LINE_AA,
            )
        return img


def render_boundary_preview(
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> np.ndarray:
    """Draw the Appendix C polygon with no aircraft. Useful for a sanity check."""
    view = SimMapView(width=width, height=height)
    view.fit_to_boundary()
    return view.render(None)


__all__ = [
    "MapVehicle",
    "SimMapView",
    "render_boundary_preview",
]
