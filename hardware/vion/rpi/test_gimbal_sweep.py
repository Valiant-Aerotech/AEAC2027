#!/usr/bin/env python3
"""Bench sweep of pitch gimbal servo (props off, FC powered)."""

from __future__ import annotations

import argparse
import os
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from valiant.autonomy.flight.profile import apply_flight_profile, mavlink_connection_for_host
from valiant.autonomy.gimbal.servo_gimbal import GimbalController
from valiant.common.config import load_config
from valiant.common.mavlink import MavlinkConnectError, connect, print_mavlink_connect_error


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep gimbal PWM min -> max -> neutral")
    parser.add_argument("--profile", default="vivi")
    parser.add_argument("--dwell-s", type=float, default=1.5)
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config(), args.profile)
    gimbal_cfg = cfg.get("gimbal", {})
    if not gimbal_cfg.get("enabled"):
        print("[FAIL] gimbal.enabled is false in profile")
        sys.exit(1)

    conn, baud = mavlink_connection_for_host(cfg)
    print(f"Connecting {conn} @ {baud} ...")
    try:
        master = connect(conn, baud, wait_heartbeat=True)
    except MavlinkConnectError as exc:
        print_mavlink_connect_error(exc)
        sys.exit(1)
    gimbal = GimbalController(master, cfg)

    steps = [
        ("min", gimbal.pwm_min),
        ("neutral", gimbal.pwm_neutral),
        ("max", gimbal.pwm_max),
        ("neutral", gimbal.pwm_neutral),
    ]
    print(f"Sweeping SERVO{gimbal.channel} - watch gimbal pitch (props OFF)")
    for name, pwm in steps:
        print(f"  -> {name}: PWM {pwm}")
        gimbal._send_pwm(pwm, force=True)
        time.sleep(args.dwell_s)

    gimbal.cleanup()
    master.close()
    print("[OK] Gimbal sweep complete")


if __name__ == "__main__":
    main()
