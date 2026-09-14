"""Turn a pixel detection into metric geometry relative to the aircraft.

Input is a ``DetectionFrame`` plus whatever range evidence is available (depth
map, rangefinder, or an apparent-size estimate from the camera FOV). Output is
a ``RangeFix``: how far away the thing is, in which direction, and how far off
our altitude is. Navigation and mission code work from that, never from pixels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from valiant.core.kinematics import rot_body_from_ned
from valiant.perception.depth.map import sample_depth_at_bbox, sample_depth_m
from valiant.perception.depth.rangefinder import RangefinderReader
from valiant.perception.geometry import (
    altitude_error_from_pose,
    altitude_error_from_ray,
    camera_ray_to_body,
    decompose_slant_range,
    pixel_to_unit_ray,
    ray_angles_deg,
    vertical_margin_m,
)
from valiant.perception.types import Detection, DetectionFrame, RangeFix

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from pymavlink import mavutil

    from valiant.core.kinematics import VehiclePose


def pixel_offset_from(cx: int, cy: int, frame_w: int, frame_h: int) -> tuple[float, float]:
    """Signed offset of a pixel from frame centre; +x right, +y down."""
    return (float(cx) - frame_w / 2.0, float(cy) - frame_h / 2.0)


def estimate_distance_fov_band(
    detection: Detection,
    frame_w: int,
    *,
    hfov_deg: float,
    object_width_min_m: float,
    object_width_max_m: float,
) -> tuple[float | None, float | None, float | None]:
    """Distance band from apparent width, given a known real-width range.

    Returns (min_m, max_m, mid_m). Useful when there is no depth sensor: an
    object of known size subtending a known pixel width pins the range to a
    band whose width is the size uncertainty.
    """
    import math

    x0, _, x1, _ = detection.bbox
    width_px = abs(x1 - x0)
    if width_px <= 0 or frame_w <= 0:
        return None, None, None
    fraction = width_px / float(frame_w)
    if fraction <= 0:
        return None, None, None
    half_angle = math.radians(hfov_deg / 2.0) * fraction
    tan_half = math.tan(half_angle)
    if tan_half <= 1e-9:
        return None, None, None
    near = (object_width_min_m / 2.0) / tan_half
    far = (object_width_max_m / 2.0) / tan_half
    return near, far, (near + far) / 2.0


class MetricReconstructor:
    """``DetectionFrame`` -> ``RangeFix`` pipeline."""

    def __init__(self, master: mavutil.mavfile | None, cfg: dict, *, sim: bool = False):
        self.cfg = cfg
        self.sim = sim
        metric_cfg = cfg.get("metric_recon", {})
        self.mode = metric_cfg.get("mode", "rangefinder")
        self.rangefinder_mode = metric_cfg.get("rangefinder", "fov_estimate")
        # Real-world width band of whatever we are ranging against. Set per
        # mission: a deer decoy, a sample container, a landing pad.
        self.object_width_min_m = float(metric_cfg.get("object_width_min_m", 0.05))
        self.object_width_max_m = float(metric_cfg.get("object_width_max_m", 1.50))

        cam_cfg = cfg.get("camera", {})
        self.hfov_deg = cam_cfg.get("hfov_deg", 66.0)
        self.vfov_deg = cam_cfg.get("vfov_deg", cfg.get("fov", {}).get("vfov_deg", 52.0))
        self.camera_down = metric_cfg.get("camera_down", True)
        self.alt_offset_m = float(
            metric_cfg.get("alt_offset_m", cfg.get("sitl", {}).get("alt_offset_m", 0.0))
        )
        self._calibration = cfg.get("calibration", {})

        self._rangefinder: RangefinderReader | None = None
        if (
            not sim
            and master is not None
            and self.mode == "rangefinder"
            and self.rangefinder_mode == "vl53l1x"
        ):
            self._rangefinder = RangefinderReader(master, cfg)
            self._rangefinder.start()
            print("[MetricRecon] VL53L1X rangefinder reader started")

    def stop(self) -> None:
        if self._rangefinder:
            self._rangefinder.stop()

    def reconstruct(
        self,
        frame: DetectionFrame,
        frame_w: int,
        frame_h: int,
        *,
        label: str | None = None,
        depth_mm: NDArray[np.uint16] | None = None,
        gimbal_pitch_deg: float = 0.0,
        vehicle_pose: VehiclePose | None = None,
        target_ned: tuple[float, float, float] | None = None,
        calibration: dict[str, Any] | None = None,
    ) -> RangeFix | None:
        detection = frame.largest(label)
        if detection is None:
            return None

        calib = calibration if calibration is not None else self._calibration
        target_px = (detection.cx, detection.cy)
        target_offset = pixel_offset_from(detection.cx, detection.cy, frame_w, frame_h)
        slant_m, dist_min, dist_max, source = self._resolve_distance(
            detection, frame_w, depth_mm=depth_mm, calib=calib
        )

        ray_cam = pixel_to_unit_ray(
            detection.cx, detection.cy, frame_w, frame_h,
            hfov_deg=self.hfov_deg, vfov_deg=self.vfov_deg,
        )
        ray_body = camera_ray_to_body(ray_cam, gimbal_pitch_deg)
        if vehicle_pose is not None and vehicle_pose.ok:
            r_bn = rot_body_from_ned(vehicle_pose.roll, vehicle_pose.pitch, vehicle_pose.yaw)
            azimuth, elevation = ray_angles_deg(r_bn @ ray_body)
        else:
            azimuth, elevation = ray_angles_deg(ray_body)

        horizontal_m = slant_m
        if slant_m is not None:
            horizontal_m, _ = decompose_slant_range(slant_m, ray_body)

        if target_ned is not None and vehicle_pose is not None and vehicle_pose.ok:
            alt_err = altitude_error_from_pose(
                vehicle_pose, target_ned, alt_offset_m=self.alt_offset_m
            )
        elif slant_m is not None:
            alt_err = altitude_error_from_ray(
                slant_m,
                ray_body,
                pixel_offset_y=target_offset[1],
                frame_h=frame_h,
                vfov_deg=self.vfov_deg,
            )
        else:
            alt_err = None

        return RangeFix(
            target_px=target_px,
            pixel_offset=target_offset,
            target_offset=target_offset,
            distance_m=horizontal_m if horizontal_m is not None else slant_m,
            distance_min_m=dist_min,
            distance_max_m=dist_max,
            distance_source=source,
            slant_range_m=slant_m,
            horizontal_range_m=horizontal_m,
            elevation_deg=elevation,
            azimuth_deg=azimuth,
            altitude_error_m=alt_err,
            vertical_margin_m=vertical_margin_m(
                detection, frame_h, slant_m, vfov_deg=self.vfov_deg
            ),
            timestamp=frame.timestamp,
        )

    def _resolve_distance(
        self,
        detection: Detection,
        frame_w: int,
        *,
        depth_mm: NDArray[np.uint16] | None,
        calib: dict[str, Any] | None,
    ) -> tuple[float | None, float | None, float | None, str]:
        if self.mode == "depth_at_target" and depth_mm is not None:
            depth_m = sample_depth_at_bbox(depth_mm, detection, calib=calib)
            if depth_m is None:
                depth_m = sample_depth_m(
                    depth_mm, detection.cx, detection.cy,
                    calib=calib,
                    patch_radius=int(calib.get("depth_sample_window_px", 5)) if calib else 5,
                )
            if depth_m is not None:
                return depth_m, depth_m, depth_m, "depth_at_target"

        if self.rangefinder_mode == "none":
            return None, None, None, "none"

        rf_dist = None
        if self._rangefinder is not None:
            rf_dist = self._rangefinder.read_distance_m()

        lo, hi, mid = estimate_distance_fov_band(
            detection,
            frame_w,
            hfov_deg=self.hfov_deg,
            object_width_min_m=self.object_width_min_m,
            object_width_max_m=self.object_width_max_m,
        )

        if self.rangefinder_mode == "fov_estimate" or self.mode == "depth_at_target":
            if mid is not None:
                return mid, lo, hi, "fov_band"
            return None, None, None, "fov_band"

        if rf_dist is not None:
            return rf_dist, rf_dist, rf_dist, "vl53l1x"
        if mid is not None:
            return mid, lo, hi, "fov_band"
        return None, None, None, "vl53l1x"
