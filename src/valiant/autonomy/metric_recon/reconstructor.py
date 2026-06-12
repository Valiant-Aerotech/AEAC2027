"""Build MetricPacket from CVPacket + MAVLink + frame geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from valiant.autonomy.metric_recon.depth_map import rgb_to_depth_pixel, sample_depth_m
from valiant.autonomy.metric_recon.depth_source import DepthSource, NullDepthSource
from valiant.autonomy.metric_recon.pixel_geometry import (
    estimate_distance_fov,
    estimate_side_clearance,
    pixel_offset,
)
from valiant.autonomy.metric_recon.rangefinder import RangefinderReader
from valiant.autonomy.metric_recon.wall_distance import enrich_wall_distance
from valiant.autonomy.packets import CVPacket, MetricPacket

if TYPE_CHECKING:
    from pymavlink import mavutil


class MetricReconstructor:
    """CVPacket -> MetricPacket pipeline."""

    def __init__(
        self,
        master: mavutil.mavfile | None,
        cfg: dict,
        *,
        sim: bool = False,
        depth_source: DepthSource | None = None,
    ):
        self.cfg = cfg
        self.sim = sim
        metric_cfg = cfg.get("metric_recon", {})
        self.rangefinder_mode = metric_cfg.get("rangefinder", "fov_estimate")
        self.target_diameter_m = metric_cfg.get("target_diameter_m", 0.30)
        cam_cfg = cfg.get("camera", {})
        cal = cfg.get("calibration", {})
        fov_cal = cal.get("fov", {})
        self.hfov_deg = fov_cal.get("hfov_deg", cam_cfg.get("hfov_deg", 66.0))
        self.camera_down = metric_cfg.get("camera_down", True)

        self._depth_window_px = metric_cfg.get(
            "depth_sample_window_px",
            cal.get("depth_sample_window_px", 5),
        )
        self._depth_invalid_mm = metric_cfg.get(
            "depth_invalid_mm",
            cal.get("depth_invalid_mm", 0),
        )
        self._depth_max_mm = metric_cfg.get(
            "depth_max_mm",
            cal.get("depth_max_mm", 6000),
        )
        self._cal = cal

        self._depth_source: DepthSource = depth_source or NullDepthSource()

        self._rangefinder: RangefinderReader | None = None
        if not sim and master is not None and self.rangefinder_mode == "vl53l1x":
            self._rangefinder = RangefinderReader(master, cfg)
            self._rangefinder.start()
            print("[MetricRecon] VL53L1X rangefinder reader started")

    def stop(self) -> None:
        if self._rangefinder:
            self._rangefinder.stop()
        self._depth_source.stop()

    def reconstruct(
        self,
        cv_packet: CVPacket,
        frame_w: int,
        frame_h: int,
    ) -> MetricPacket | None:
        hit = cv_packet.primary_dry
        if hit is None:
            return None

        offset = pixel_offset(hit, frame_w, frame_h)
        distance_m, distance_source = self._resolve_distance(hit, frame_w, frame_h)

        packet = MetricPacket(
            target_px=(hit.cx, hit.cy),
            pixel_offset=offset,
            distance_m=distance_m,
            distance_source=distance_source,
            timestamp=cv_packet.timestamp,
        )

        packet.side_clearance_m = estimate_side_clearance(
            hit, frame_w, distance_m, hfov_deg=self.hfov_deg
        )
        return enrich_wall_distance(
            packet, self.cfg, camera_down=self.camera_down
        )

    def _resolve_distance(
        self,
        hit,
        frame_w: int,
        frame_h: int,
    ) -> tuple[float | None, str | None]:
        fov_dist = estimate_distance_fov(
            hit,
            frame_w,
            hfov_deg=self.hfov_deg,
            target_diameter_m=self.target_diameter_m,
        )

        if self.rangefinder_mode == "none":
            return None, None
        if self.rangefinder_mode == "fov_estimate":
            return fov_dist, "fov"

        if self.rangefinder_mode == "depth_at_target":
            depth_mm = self._depth_source.get_depth_mm()
            if depth_mm is not None:
                dx, dy = rgb_to_depth_pixel(
                    hit.cx, hit.cy, frame_w, frame_h, self._cal
                )
                depth_dist = sample_depth_m(
                    depth_mm,
                    dx,
                    dy,
                    window_px=self._depth_window_px,
                    cal=self._cal,
                    invalid_mm=self._depth_invalid_mm,
                    max_mm=self._depth_max_mm,
                )
                if depth_dist is not None:
                    return depth_dist, "depth_at_target"
            if fov_dist is not None:
                return fov_dist, "fov_fallback"
            return None, None

        # vl53l1x: prefer rangefinder, FOV fallback
        rf_dist = None
        if self._rangefinder is not None:
            rf_dist = self._rangefinder.read_distance_m()
        if rf_dist is not None:
            return rf_dist, "vl53l1x"
        return fov_dist, "fov_fallback" if fov_dist is not None else None
