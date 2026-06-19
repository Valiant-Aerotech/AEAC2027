#!/usr/bin/env python3
"""Verify GCS MAVLink heartbeat via telemetry radio (bringup Phase B)."""

from __future__ import annotations

import argparse
import sys
import time

from valiant.common.config import load_config
from valiant.common.mavlink import MavlinkConnectError, connect, print_mavlink_connect_error


def main() -> int:
    parser = argparse.ArgumentParser(description="Check GCS MAVLink link to Pixhawk")
    parser.add_argument("--connection", default=None, help="Override config/rpas.yaml")
    parser.add_argument("--baud", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    cfg = load_config()
    mavlink = cfg.get("mavlink", {})
    conn = args.connection or mavlink.get("connection", "COM5")
    baud = args.baud if args.baud is not None else mavlink.get("baud", 57600)

    print(f"Connecting {conn} @ {baud} (timeout {args.timeout}s)...")
    try:
        master = connect(conn, baud, wait_heartbeat=True)
    except MavlinkConnectError as exc:
        print_mavlink_connect_error(exc)
        return 1

    hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=args.timeout)
    if hb is None:
        print("FAIL: heartbeat timeout")
        return 1

    sys_status = master.recv_match(type="SYS_STATUS", blocking=True, timeout=2.0)
    battery = ""
    if sys_status is not None and sys_status.battery_remaining >= 0:
        battery = f" battery={sys_status.battery_remaining}%"

    print(f"OK: heartbeat from system {master.target_system}{battery}")
    print("Next: python tools\\valiant.py gcs spray  (SERVO15 bench test, props off)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
