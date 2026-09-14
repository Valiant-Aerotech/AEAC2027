"""Single-window SITL dashboard: camera view beside the live GCS map.

Development convenience, not a competition deliverable. The map half is the
same :class:`~valiant.comms.gcs_map.GcsMapView` the flight line uses, so what
you watch in simulation is what the crew watches in the field.
"""

from __future__ import annotations

import cv2
import numpy as np

from valiant.comms.draw import C_BORDER, C_MUTED, state_color
from valiant.comms.gcs_map import GcsMapView, MapVehicle
from valiant.core.geo import offset_lat_lon
from valiant.core.kinematics import VehiclePose

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720


def pose_to_map_vehicle(
    pose: VehiclePose,
    *,
    home_lat: float,
    home_lon: float,
    label: str = "",
) -> MapVehicle | None:
    """Convert a LOCAL NED pose into a lat/lon the map view can draw."""
    if not pose.ok:
        return None
    lat, lon = offset_lat_lon(home_lat, home_lon, pose.x, pose.y)
    return MapVehicle(
        lat=lat,
        lon=lon,
        alt_agl_m=-pose.z,
        yaw_rad=pose.yaw,
        label=label,
    )


def _fit_panel(src: np.ndarray, width: int, height: int) -> np.ndarray:
    """Letterbox-scale *src* into a panel of size (width, height)."""
    sh, sw = src.shape[:2]
    out = np.zeros((height, width, 3), dtype=np.uint8)
    out[:] = (18, 20, 26)
    if sw <= 0 or sh <= 0:
        return out
    scale = min(width / sw, height / sh)
    nw, nh = max(int(sw * scale), 1), max(int(sh * scale), 1)
    resized = cv2.resize(src, (nw, nh), interpolation=cv2.INTER_AREA)
    x0 = (width - nw) // 2
    y0 = (height - nh) // 2
    out[y0 : y0 + nh, x0 : x0 + nw] = resized
    return out


class SitlDashboard:
    """Composes the camera frame and the GCS map into one window."""

    def __init__(
        self,
        *,
        home_lat: float,
        home_lon: float,
        map_view: GcsMapView | None = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ):
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.width = width
        self.height = height
        self.map_view = map_view or GcsMapView(height=height, width=height)
        self.map_view.fit_to_boundary()

    def render(
        self,
        camera_frame: np.ndarray,
        pose: VehiclePose,
        *,
        state: str = "",
        mode_label: str = "",
        traffic: list[MapVehicle] | None = None,
    ) -> np.ndarray:
        cam_w = self.width // 2
        map_w = self.width - cam_w

        aircraft = pose_to_map_vehicle(
            pose, home_lat=self.home_lat, home_lon=self.home_lon, label="ours"
        )
        self.map_view.width = map_w
        self.map_view.height = self.height
        map_panel = self.map_view.render(aircraft, traffic, state=state)

        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        canvas[:] = (14, 16, 22)
        canvas[:, :cam_w] = _fit_panel(camera_frame, cam_w, self.height)
        canvas[:, cam_w:] = _fit_panel(map_panel, map_w, self.height)
        cv2.line(canvas, (cam_w, 0), (cam_w, self.height), C_BORDER, 2, cv2.LINE_AA)

        if state:
            pill = f" {state} "
            pill_w = min(len(pill) * 9 + 16, cam_w - 16)
            cv2.rectangle(canvas, (8, 8), (8 + pill_w, 30), state_color(state), -1, cv2.LINE_AA)
            cv2.putText(
                canvas, pill, (12, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 22, 28), 1, cv2.LINE_AA,
            )
        if mode_label:
            tw = cv2.getTextSize(mode_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0][0]
            cv2.putText(
                canvas, mode_label, (cam_w - tw - 12, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, C_MUTED, 1, cv2.LINE_AA,
            )
        return canvas
