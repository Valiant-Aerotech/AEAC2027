#!/usr/bin/env python3
"""Check RPi RGB preview, depth stats, and MAVLink heartbeat."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import cv2
import numpy as np

from valiant.common.config import load_config
from valiant.common.mavlink import connect
from valiant.common.rpi_local_camera import RpiLocalCamera


def main() -> int:
    parser = argparse.ArgumentParser(description="Vion RPi sensor check")
    parser.add_argument("--connection", default="/dev/ttyAMA0")
    parser.add_argument("--baud", type=int, default=57600)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--skip-mavlink", action="store_true")
    args = parser.parse_args()

    cfg = load_config("vion")
    camera = RpiLocalCamera.from_config(cfg, webcam_fallback_index=args.camera)

    master = None
    if not args.skip_mavlink:
        try:
            master = connect(args.connection, args.baud, wait_heartbeat=True)
            print("[OK] MAVLink heartbeat received")
        except Exception as exc:
            print(f"[WARN] MAVLink not available: {exc}")

    print("Sensor check. Press Q to quit.")
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.1)
            continue

        depth = camera.get_depth_mm()
        label = "depth: n/a"
        if depth is not None:
            valid = depth[(depth > 0) & (depth < 6000)]
            if valid.size:
                label = f"depth median: {int(np.median(valid))} mm ({valid.size} px)"

        cv2.putText(
            frame,
            label,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Vion Sensor Check", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.cleanup()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
