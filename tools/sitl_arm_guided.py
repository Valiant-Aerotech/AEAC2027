#!/usr/bin/env python3
"""Put ArduCopter SITL into GUIDED and arm (run from Windows while SITL is up)."""

from __future__ import annotations

import argparse
import time

from pymavlink import mavutil


def _wait_mode(master: mavutil.mavlink_connection, mode: str, timeout_s: float) -> None:
    want = master.mode_mapping()[mode]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if hb and hb.custom_mode == want:
            return
    raise SystemExit(f"Timed out waiting for mode {mode}")


def _wait_armed(master: mavutil.mavlink_connection, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if hb and hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            return
    raise SystemExit("Timed out waiting for armed state")


def main() -> None:
    parser = argparse.ArgumentParser(description="Arm ArduCopter SITL in GUIDED mode")
    parser.add_argument("--connection", default="tcp:127.0.0.1:5760")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    print(f"Connecting to {args.connection}...")
    master = mavutil.mavlink_connection(args.connection)
    try:
        master.wait_heartbeat(timeout=args.timeout)
        print(f"Heartbeat from system {master.target_system}")

        mode = "GUIDED"
        if mode not in master.mode_mapping():
            raise SystemExit(f"Mode {mode!r} not in mode_mapping: {master.mode_mapping()}")
        master.set_mode(master.mode_mapping()[mode])
        print(f"Set mode {mode}")
        _wait_mode(master, mode, args.timeout)

        master.arducopter_arm()
        print("Arm command sent")
        _wait_armed(master, args.timeout)
        print("Vehicle armed")
    finally:
        master.close()


if __name__ == "__main__":
    main()
