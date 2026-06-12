#!/usr/bin/env python3
"""Capture synced RGB + depth frames at a known tape-measure distance."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import cv2
import numpy as np

from valiant.common.config import load_config, repo_root
from valiant.common.rpi_local_camera import RpiLocalCamera


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture calibration RGB+depth set")
    parser.add_argument("--distance", type=float, required=True, help="Tape distance in meters")
    parser.add_argument("--output", default="logs/calibration")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config("vion")
    out_dir = repo_root() / args.output / f"{args.distance:.1f}m"
    out_dir.mkdir(parents=True, exist_ok=True)

    camera = RpiLocalCamera.from_config(cfg, webcam_fallback_index=args.camera)
    index_path = out_dir.parent / "index.json"
    frames_meta: list[dict] = []

    print(f"Capturing {args.count} frames at {args.distance}m into {out_dir}")
    for i in range(args.count):
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.1)
            continue
        depth = camera.get_depth_mm()
        rgb_name = f"rgb_{i:04d}.jpg"
        depth_name = f"depth_{i:04d}.npy"
        cv2.imwrite(str(out_dir / rgb_name), frame)
        if depth is not None:
            np.save(str(out_dir / depth_name), depth.astype(np.uint16))
        frames_meta.append(
            {
                "distance_m": args.distance,
                "rgb_file": str(Path(args.output) / f"{args.distance:.1f}m" / rgb_name),
                "depth_file": str(Path(args.output) / f"{args.distance:.1f}m" / depth_name)
                if depth is not None
                else None,
            }
        )
        time.sleep(0.2)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({"frames": frames_meta}, f, indent=2)

    camera.cleanup()
    print(f"Saved {len(frames_meta)} frames. Index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
