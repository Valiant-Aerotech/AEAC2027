"""Build MetricPacket from CVPacket + MAVLink + frame geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from valiant.autonomy.metric_recon.depth_map import sample_depth_at_bbox, sample_depth_m
from valiant.autonomy.metric_recon.geometry_3d import (
    altitude_error_from_pose,
    altitude_error_from_ray,
    camera_ray_to_body,
    decompose_slant_range,
    estimate_vertical_clearance,
    pixel_to_unit_ray,
    ray_angles_deg,
)
from valiant.autonomy.metric_recon.pixel_geometry import (
    estimate_distance_fov_band,
    estimate_side_clearance,
    pixel_offset,
)
from valiant.autonomy.metric_recon.rangefinder import RangefinderReader
from valiant.autonomy.metric_recon.wall_distance import enrich_wall_distance
from valiant.autonomy.packets import CVPacket, MetricPacket
from valiant.common.ned_kinematics import rot_body_from_ned

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from pymavlink import mavutil

    from valiant.common.ned_kinematics import VehiclePose


class MetricReconstructor:
    """CVPacket -> MetricPacket pipeline."""

    def __init__(self, master: mavutil.mavfile | None, cfg: dict, *, sim: bool = False):
        self.cfg = cfg
        self.sim = sim
        metric_cfg = cfg.get("metric_recon", {})
        self.mode = metric_cfg.get("mode", "rangefinder")
        self.rangefinder_mode = metric_cfg.get("rangefinder", "fov_estimate")
        self.target_diameter_m = metric_cfg.get("target_diameter_m", 0.30)
        self.target_diameter_min_m = metric_cfg.get(
            "target_diameter_min_m",
            cfg.get("conops", {}).get("task2", {}).get("target_diameter_min_m", 0.05),
        )
        self.target_diameter_max_m = metric_cfg.get(
            "target_diameter_max_m",
            cfg.get("conops", {}).get("task2", {}).get("target_diameter_max_m", 0.30),
        )
        cam_cfg = cfg.get("camera", {})
        self.hfov_deg = cam_cfg.get("hfov_deg", 66.0)
        self.vfov_deg = cam_cfg.get("vfov_deg", cfg.get("fov", {}).get("vfov_deg", 52.0))
        self.camera_down = metric_cfg.get("camera_down", True)
        self.alt_offset_m = float(metric_cfg.get("alt_offset_m", cfg.get("sitl", {}).get("alt_offset_m", 0.0)))
        self._calibration = cfg.get(
            "calibration",
            cfg.get("rpas_calibration", cfg.get("vion_calibration", {})),
        )

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
        cv_packet: CVPacket,
        frame_w: int,
        frame_h: int,
        *,
        depth_mm: NDArray[np.uint16] | None = None,
        gimbal_pitch_deg: float = 0.0,
        vehicle_pose: VehiclePose | None = None,
        target_ned: tuple[float, float, float] | None = None,
        calibration: dict[str, Any] | None = None,
    ) -> MetricPacket | None:
        hit = cv_packet.primary_dry
        if hit is None:
            return None

        calib = calibration if calibration is not None else self._calibration
        offset = pixel_offset(hit, frame_w, frame_h)
        slant_m, dist_min, dist_max, source = self._resolve_distance(
            hit, frame_w, depth_mm=depth_mm, calib=calib
        )

        ray_cam = pixel_to_unit_ray(
            hit.cx, hit.cy, frame_w, frame_h,
            hfov_deg=self.hfov_deg, vfov_deg=self.vfov_deg,
        )
        ray_body = camera_ray_to_body(ray_cam, gimbal_pitch_deg)
        if vehicle_pose is not None and vehicle_pose.ok:
            r_bn = rot_body_from_ned(vehicle_pose.roll, vehicle_pose.pitch, vehicle_pose.yaw)
            ray_ned = r_bn @ ray_body
            azimuth, elevation = ray_angles_deg(ray_ned)
        else:
            azimuth, elevation = ray_angles_deg(ray_body)

        horizontal_m = slant_m
        if slant_m is not None:
            horizontal_m, _ = decompose_slant_range(slant_m, ray_body)

        if target_ned is not None and vehicle_pose is not None and vehicle_pose.ok:
            alt_err = altitude_error_from_pose(
                vehicle_pose, target_ned, alt_offset_m=self.alt_offset_m
            )
        else:
            alt_err = altitude_error_from_ray(
                slant_m or 0.0,
                ray_body,
                pixel_offset_y=offset[1],
                frame_h=frame_h,
                vfov_deg=self.vfov_deg,
            ) if slant_m is not None else None

        planner_dist = horizontal_m if horizontal_m is not None else slant_m

        packet = MetricPacket(
            target_px=(hit.cx, hit.cy),
            pixel_offset=offset,
            distance_m=planner_dist,
            distance_min_m=dist_min,
            distance_max_m=dist_max,
            distance_source=source,
            slant_range_m=slant_m,
            horizontal_range_m=horizontal_m,
            elevation_deg=elevation,
            azimuth_deg=azimuth,
            altitude_error_m=alt_err,
            timestamp=cv_packet.timestamp,
        )

        clearance_dist = dist_max if dist_max is not None else planner_dist
        packet.side_clearance_m = estimate_side_clearance(
            hit, frame_w, clearance_dist, hfov_deg=self.hfov_deg
        )
        packet.vertical_clearance_m = estimate_vertical_clearance(
            hit, frame_h, slant_m, vfov_deg=self.vfov_deg
        )
        return enrich_wall_distance(packet, self.cfg, camera_down=self.camera_down)

    def _resolve_distance(
        self,
        hit,
        frame_w: int,
        *,
        depth_mm: NDArray[np.uint16] | None,
        calib: dict[str, Any] | None,
    ) -> tuple[float | None, float | None, float | None, str]:
        if self.mode == "depth_at_target" and depth_mm is not None:
            depth_m = sample_depth_at_bbox(depth_mm, hit, calib=calib)
            if depth_m is None:
                depth_m = sample_depth_m(
                    depth_mm, hit.cx, hit.cy,
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
            hit,
            frame_w,
            hfov_deg=self.hfov_deg,
            target_diameter_min_m=self.target_diameter_min_m,
            target_diameter_max_m=self.target_diameter_max_m,
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
