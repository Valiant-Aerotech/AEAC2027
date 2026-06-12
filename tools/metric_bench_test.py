#!/usr/bin/env python3
"""Bench-test CV + MetricRecon pipeline on webcam or video."""

from __future__ import annotations

import argparse
import json
import sys

import cv2

from valiant.autonomy.cv.detector import TargetDetector
from valiant.autonomy.cv.ui import draw_overlay
from valiant.autonomy.metric_recon.reconstructor import MetricReconstructor
from valiant.common.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="CV + MetricRecon bench test")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--video", type=str, default=None)
    parser.add_argument("--rangefinder", choices=["fov_estimate", "vl53l1x", "depth_at_target", "none"], default=None)
    parser.add_argument("--recording-dir", default=None, help="Depth replay dir for depth_at_target")
    args = parser.parse_args()

    cfg = load_config("vion")
    if args.rangefinder:
        cfg.setdefault("metric_recon", {})["rangefinder"] = args.rangefinder

    detector = TargetDetector(cfg)
    depth_source = None
    if cfg.get("metric_recon", {}).get("rangefinder") == "depth_at_target":
        from valiant.autonomy.metric_recon.depth_source import RecordingDepthSource

        rec_dir = args.recording_dir or cfg.get("camera", {}).get("rpi", {}).get("recording_dir")
        if rec_dir:
            depth_source = RecordingDepthSource(rec_dir)
    metric_recon = MetricReconstructor(None, cfg, sim=True, depth_source=depth_source)

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
        metric = metric_recon.reconstruct(cv_packet, w, h)

        if metric:
            record = {
                "target_px": metric.target_px,
                "pixel_offset": metric.pixel_offset,
                "distance_m": metric.distance_m,
                "distance_source": metric.distance_source,
                "wall_distance_m": metric.wall_distance_m,
                "side_clearance_m": metric.side_clearance_m,
            }
            print(json.dumps(record))

        method = cfg.get("cv", {}).get("method", "hsv")
        crop_size = cfg.get("cv", {}).get("yolo_input_size", 320)
        overlay = draw_overlay(
            frame,
            cv_packet,
            "METRIC_BENCH",
            metric=metric,
            show_yolo_crop=method in ("yolo", "both"),
            yolo_crop_size=crop_size,
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
