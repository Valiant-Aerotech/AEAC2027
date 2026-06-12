#!/usr/bin/env python3
"""Bench-test water spray SERVO15 via GCS MAVLink link (bringup Phase B4.3)."""

from __future__ import annotations

import argparse
import sys

from valiant.common.config import load_config
from valiant.common.mavlink import connect
from valiant.autonomy.spray.actuation import WaterTrigger


def main() -> int:
    parser = argparse.ArgumentParser(description="Test SERVO15 water spray via MAVLink")
    parser.add_argument("--connection", default=None)
    parser.add_argument("--baud", type=int, default=None)
    parser.add_argument("--duration", type=float, default=1.0, help="Spray open duration (seconds)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    cfg = load_config("vion")
    mavlink = cfg.get("mavlink", {})
    conn = args.connection or mavlink.get("connection", "COM5")
    baud = args.baud if args.baud is not None else mavlink.get("baud", 57600)
    channel = cfg.get("spray", {}).get("channel", 15)

    print(f"Will pulse SERVO{channel} for {args.duration}s on {conn}")
    print("Props OFF. Clear spray path. Have towel ready.")
    if not args.yes:
        reply = input("Type YES to continue: ").strip()
        if reply != "YES":
            print("Aborted.")
            return 0

    master = connect(conn, baud, wait_heartbeat=True)
    trigger = WaterTrigger(master, cfg)
    print("Firing...")
    trigger.fire(args.duration)
    trigger.cleanup()
    print("OK: SERVO command sent. Verify water valve in Mission Planner / physically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
