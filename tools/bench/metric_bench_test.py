#!/usr/bin/env python3
"""Bench-test CV + MetricRecon pipeline on webcam or video."""

from __future__ import annotations

import argparse
import json
import sys

import cv2

from valiant.autonomy.cv import create_target_detector, draw_mission_overlay
from valiant.autonomy.metric_recon.reconstructor import MetricReconstructor
from valiant.common.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="CV + MetricRecon bench test")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--video", type=str, default=None)
    parser.add_argument("--rangefinder", choices=["fov_estimate", "vl53l1x", "depth_at_target", "none"], default=None)
    parser.add_argument("--recording-dir", default=None, help="Depth replay dir for depth_at_target")
    args = parser.parse_args()

    cfg = load_config()
    metric_cfg = cfg.setdefault("metric_recon", {})
    if args.rangefinder:
        metric_cfg["rangefinder"] = args.rangefinder
        if args.rangefinder == "depth_at_target":
            metric_cfg["mode"] = "depth_at_target"

    depth_reader = None
    if metric_cfg.get("mode") == "depth_at_target":
        from valiant.autonomy.metric_recon.depth_source import RecordingDepthSource

        rec_dir = args.recording_dir or cfg.get("camera", {}).get("rpi", {}).get("recording_dir")
        if rec_dir:
            depth_reader = RecordingDepthSource(rec_dir)

    metric_recon = MetricReconstructor(None, cfg, sim=True)
    detector = create_target_detector(cfg)

    cap = cv2.VideoCapture(args.video) if args.video else cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("ERROR: could not open video source")
        return 1

    print("Metric bench test. Press Q to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        cv_packet = detector.detect(frame)
        depth_mm = depth_reader.get_depth_mm() if depth_reader else None
        metric = metric_recon.reconstruct(cv_packet, w, h, depth_mm=depth_mm)

        if metric:
            record = {
                "target_px": metric.target_px,
                "pixel_offset": metric.pixel_offset,
                "distance_m": metric.distance_m,
                "slant_range_m": metric.slant_range_m,
                "horizontal_range_m": metric.horizontal_range_m,
                "altitude_error_m": metric.altitude_error_m,
                "distance_source": metric.distance_source,
                "wall_distance_m": metric.wall_distance_m,
                "side_clearance_m": metric.side_clearance_m,
            }
            print(json.dumps(record))

        overlay = draw_mission_overlay(
            frame,
            cv_packet,
            "METRIC_BENCH",
            cfg,
            metric=metric,
        )
        cv2.imshow("Metric Bench", overlay)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    metric_recon.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
