"""Build MetricPacket from CVPacket + MAVLink + frame geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING

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

    def __init__(self, master: mavutil.mavfile | None, cfg: dict, *, sim: bool = False):
        self.cfg = cfg
        self.sim = sim
        metric_cfg = cfg.get("metric_recon", {})
        self.rangefinder_mode = metric_cfg.get("rangefinder", "fov_estimate")
        self.target_diameter_m = metric_cfg.get("target_diameter_m", 0.30)
        cam_cfg = cfg.get("camera", {})
        self.hfov_deg = cam_cfg.get("hfov_deg", 66.0)
        self.camera_down = metric_cfg.get("camera_down", True)

        self._rangefinder: RangefinderReader | None = None
        if not sim and master is not None and self.rangefinder_mode == "vl53l1x":
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
    ) -> MetricPacket | None:
        hit = cv_packet.primary_dry
        if hit is None:
            return None

        offset = pixel_offset(hit, frame_w, frame_h)
        distance_m = self._resolve_distance(hit, frame_w)

        packet = MetricPacket(
            target_px=(hit.cx, hit.cy),
            pixel_offset=offset,
            distance_m=distance_m,
            timestamp=cv_packet.timestamp,
        )

        packet.side_clearance_m = estimate_side_clearance(
            hit, frame_w, distance_m, hfov_deg=self.hfov_deg
        )
        return enrich_wall_distance(
            packet, self.cfg, camera_down=self.camera_down
        )

    def _resolve_distance(self, hit, frame_w: int) -> float | None:
        rf_dist = None
        if self._rangefinder is not None:
            rf_dist = self._rangefinder.read_distance_m()

        fov_dist = estimate_distance_fov(
            hit,
            frame_w,
            hfov_deg=self.hfov_deg,
            target_diameter_m=self.target_diameter_m,
        )

        if self.rangefinder_mode == "none":
            return None
        if self.rangefinder_mode == "fov_estimate":
            return fov_dist
        # vl53l1x: prefer rangefinder, FOV fallback
        return rf_dist if rf_dist is not None else fov_dist
