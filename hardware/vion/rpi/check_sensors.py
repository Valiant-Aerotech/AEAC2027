#!/usr/bin/env python3
"""Quick sensor + MAVLink check on Pi (props off)."""

from __future__ import annotations

import argparse
import os
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from valiant.autonomy.flight.profile import apply_flight_profile, mavlink_connection_for_host
from valiant.common.camera_factory import create_camera, camera_depth_ok
from valiant.common.config import load_config
from valiant.common.mavlink import connect


def check_rgb(camera) -> bool:
    frame = camera.get_frame()
    if frame is None:
        print("[FAIL] RGB frame")
        return False
    print(f"[OK] RGB frame captured {frame.shape[1]}x{frame.shape[0]}")
    if camera_depth_ok(camera):
        depth = camera.depth_mm
        if depth is not None:
            import numpy as np

            valid = depth[(depth > 0) & (depth < 60000)]
            med = int(np.median(valid)) if valid.size else None
            print(f"[OK] ArduCam ToF active, median depth ~{med} mm")
        else:
            print("[WARN] ToF active but no depth frame")
    else:
        print("[INFO] ToF not active (SDK missing or disabled)")
    return True


def check_mavlink(conn: str, baud: int) -> bool:
    try:
        master = connect(conn, baud, wait_heartbeat=True)
        print("[OK] MAVLink heartbeat received")
        master.close()
        return True
    except Exception as exc:
        print(f"[FAIL] MAVLink: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Pi sensor and MAVLink check")
    parser.add_argument("--profile", default="vivi")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--skip-mavlink", action="store_true")
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config(), args.profile)
    conn, baud = mavlink_connection_for_host(cfg)

    camera = create_camera(cfg)
    ok_rgb = check_rgb(camera)
    camera.cleanup()

    ok_mav = True
    if not args.skip_mavlink and not os.environ.get("SKIP_MAVLINK"):
        ok_mav = check_mavlink(conn, baud)

    if args.once:
        sys.exit(0 if ok_rgb and ok_mav else 1)

    while True:
        time.sleep(5)


if __name__ == "__main__":
    main()
