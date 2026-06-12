#!/usr/bin/env python3
"""Validate depth calibration against tape-measure checkpoints (10% gate)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml

from valiant.autonomy.cv.detector import TargetDetector
from valiant.autonomy.metric_recon.depth_source import InlineDepthSource
from valiant.autonomy.metric_recon.reconstructor import MetricReconstructor
from valiant.common.config import load_config, repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate depth calibration")
    parser.add_argument("--calibration-dir", default="logs/calibration")
    parser.add_argument("--max-error-pct", type=float, default=None)
    args = parser.parse_args()

    cfg = load_config("vion")
    cal = cfg.get("calibration", {})
    max_error = args.max_error_pct
    if max_error is None:
        max_error = cal.get("validation", {}).get("max_error_pct", 10.0)

    cal_dir = repo_root() / args.calibration_dir
    if not cal_dir.is_dir():
        print(f"ERROR: calibration dir not found: {cal_dir}")
        return 1

    cfg.setdefault("metric_recon", {})["rangefinder"] = "depth_at_target"
    depth_source = InlineDepthSource()
    recon = MetricReconstructor(None, cfg, sim=True, depth_source=depth_source)
    detector = TargetDetector(cfg)

    errors: list[float] = []
    for sub in sorted(cal_dir.glob("*m")):
        if not sub.is_dir():
            continue
        try:
            truth_m = float(sub.name.replace("m", ""))
        except ValueError:
            continue

        for rgb_path in sorted(sub.glob("rgb_*.jpg")):
            import cv2

            frame = cv2.imread(str(rgb_path))
            if frame is None:
                continue
            depth_path = sub / rgb_path.name.replace("rgb_", "depth_").replace(".jpg", ".npy")
            if depth_path.is_file():
                depth_source.set_frame(np.load(str(depth_path)).astype(np.uint16))
            else:
                depth_source.set_frame(None)

            h, w = frame.shape[:2]
            cv_packet = detector.detect(frame)
            metric = recon.reconstruct(cv_packet, w, h)
            if metric is None or metric.distance_m is None:
                continue
            err_pct = abs(metric.distance_m - truth_m) / truth_m * 100.0
            errors.append(err_pct)
            print(
                json.dumps(
                    {
                        "truth_m": truth_m,
                        "measured_m": round(metric.distance_m, 3),
                        "error_pct": round(err_pct, 2),
                        "source": metric.distance_source,
                    }
                )
            )

    recon.stop()
    if not errors:
        print("ERROR: no valid samples")
        return 1

    worst = max(errors)
    mean = sum(errors) / len(errors)
    print(f"Mean error: {mean:.2f}%  Worst: {worst:.2f}%  Gate: {max_error}%")
    return 0 if worst <= max_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
