"""Build MetricPacket from CVPacket + MAVLink + frame geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from valiant.autonomy.metric_recon.depth_map import sample_depth_m
from valiant.autonomy.metric_recon.pixel_geometry import (
    estimate_distance_fov,
    estimate_distance_fov_band,
    estimate_side_clearance,
    pixel_offset,
)
from valiant.autonomy.metric_recon.rangefinder import RangefinderReader
from valiant.autonomy.metric_recon.wall_distance import enrich_wall_distance
from valiant.autonomy.packets import CVPacket, MetricPacket

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from pymavlink import mavutil


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
        self.camera_down = metric_cfg.get("camera_down", True)

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
    ) -> MetricPacket | None:
        hit = cv_packet.primary_dry
        if hit is None:
            return None

        offset = pixel_offset(hit, frame_w, frame_h)
        distance_m, dist_min, dist_max, source = self._resolve_distance(
            hit, frame_w, depth_mm=depth_mm
        )

        packet = MetricPacket(
            target_px=(hit.cx, hit.cy),
            pixel_offset=offset,
            distance_m=distance_m,
            distance_min_m=dist_min,
            distance_max_m=dist_max,
            distance_source=source,
            timestamp=cv_packet.timestamp,
        )

        clearance_dist = dist_max if dist_max is not None else distance_m
        packet.side_clearance_m = estimate_side_clearance(
            hit, frame_w, clearance_dist, hfov_deg=self.hfov_deg
        )
        return enrich_wall_distance(packet, self.cfg, camera_down=self.camera_down)

    def _resolve_distance(
        self,
        hit,
        frame_w: int,
        *,
        depth_mm: NDArray[np.uint16] | None,
    ) -> tuple[float | None, float | None, float | None, str]:
        if self.mode == "depth_at_target" and depth_mm is not None:
            depth_m = sample_depth_m(depth_mm, hit.cx, hit.cy)
            if depth_m is not None:
                return depth_m, depth_m, depth_m, "depth_at_target"

        if self.mode == "depth_at_target" and depth_mm is None:
            pass  # fall through to FOV band

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

        # vl53l1x: prefer rangefinder, FOV band fallback
        if rf_dist is not None:
            return rf_dist, rf_dist, rf_dist, "vl53l1x"
        if mid is not None:
            return mid, lo, hi, "fov_band"
        return None, None, None, "vl53l1x"
