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
    parser.add_argument(
        "--once",
        action="store_true",
        help="Single-frame pass/fail check (no GUI loop)",
    )
    args = parser.parse_args()

    cfg = load_config("vion")
    camera = RpiLocalCamera.from_config(cfg, webcam_fallback_index=args.camera)

    mavlink_ok = args.skip_mavlink
    if not args.skip_mavlink:
        try:
            connect(args.connection, args.baud, wait_heartbeat=True)
            print("[OK] MAVLink heartbeat received")
            mavlink_ok = True
        except Exception as exc:
            print(f"[FAIL] MAVLink not available: {exc}")

    frame_ok = False
    depth_note = "depth: n/a"
    tof_note = (
        "ArduCam ToF: active"
        if camera.depth_available
        else "ArduCam ToF: not started"
    )
    deadline = time.time() + 5.0
    while time.time() < deadline:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.1)
            continue
        frame_ok = True
        depth = camera.get_depth_mm()
        if depth is not None:
            valid = depth[(depth > 0) & (depth < 6000)]
            if valid.size:
                depth_note = f"depth median: {int(np.median(valid))} mm"
        break

    if args.once:
        camera.cleanup()
        if frame_ok:
            print(f"[OK] RGB frame captured; {tof_note}; {depth_note}")
        else:
            print("[FAIL] no RGB frame in 5s")
        if not mavlink_ok:
            print("[FAIL] MAVLink heartbeat")
            return 1
        return 0 if frame_ok else 1

    if not mavlink_ok:
        print("[WARN] continuing without MAVLink for preview")

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
        tof_note = (
            "ArduCam ToF: active"
            if camera.depth_available
            else "ArduCam ToF: off"
        )
        cv2.putText(frame, tof_note, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, label, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Vion Sensor Check", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.cleanup()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
