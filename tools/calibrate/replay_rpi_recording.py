#!/usr/bin/env python3
"""Replay Pi-recorded RGB+depth through CV + metric recon on GCS."""

from __future__ import annotations

import argparse
import sys

import cv2

from valiant.autonomy.cv import create_target_detector, draw_mission_overlay
from valiant.autonomy.metric_recon.depth_source import InlineDepthSource
from valiant.autonomy.metric_recon.reconstructor import MetricReconstructor
from valiant.common.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay RPi recording")
    parser.add_argument("--recording-dir", required=True)
    args = parser.parse_args()

    cfg = load_config()
    cfg.setdefault("metric_recon", {})["rangefinder"] = "depth_at_target"
    depth_source = InlineDepthSource()
    recon = MetricReconstructor(None, cfg, sim=True, depth_source=depth_source)
    detector = create_target_detector(cfg)

    import json
    from pathlib import Path

    rec_dir = Path(args.recording_dir)
    rgb_files = sorted(rec_dir.rglob("rgb_*.jpg"))
    if not rgb_files:
        print("ERROR: no rgb_*.jpg in recording dir")
        return 1

    print("Replay. Press Q to quit.")
    for rgb_path in rgb_files:
        frame = cv2.imread(str(rgb_path))
        if frame is None:
            continue
        depth_path = rgb_path.parent / rgb_path.name.replace("rgb_", "depth_").replace(".jpg", ".npy")
        if depth_path.is_file():
            import numpy as np

            depth_source.set_frame(np.load(str(depth_path)).astype(np.uint16))
        else:
            depth_source.set_frame(None)
        h, w = frame.shape[:2]
        cv_packet = detector.detect(frame)
        metric = recon.reconstruct(cv_packet, w, h)
        if metric:
            print(json.dumps({"distance_m": metric.distance_m, "source": metric.distance_source}))
        overlay = draw_mission_overlay(frame, cv_packet, "REPLAY", cfg, metric=metric)
        cv2.imshow("Replay", overlay)
        if cv2.waitKey(200) & 0xFF == ord("q"):
            break

    recon.stop()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
