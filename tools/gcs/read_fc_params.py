#!/usr/bin/env python3
"""Read back the flight controller's safety parameters and report mismatches.

Run this from the GCS laptop before the flight window opens, while there is
still time to fix something in Mission Planner. It only reads: nothing here
changes the aircraft, and a bad result is a warning, not a veto.

    python tools/valiant.py gcs params
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valiant.core.config import load_config  # noqa: E402
from valiant.core.flight.fc_safety import format_report, read_safety_params  # noqa: E402
from valiant.core.flight.profile import mavlink_connection_for_gcs  # noqa: E402
from valiant.core.mavlink import (  # noqa: E402
    MavlinkConnectError,
    connect,
    print_mavlink_connect_error,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--connection", default=None, help="MAVLink URL override, e.g. COM5")
    parser.add_argument("--config", default=None, help="Extra YAML merged on top of defaults")
    parser.add_argument("--timeout", type=float, default=3.0, help="Per-parameter read timeout")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if anything is unexpected. For CI and bench checks, not the flight line.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    conn, baud = mavlink_connection_for_gcs(cfg)
    if args.connection:
        conn = args.connection

    print(f"[Preflight] Connecting {conn} @ {baud} ...")
    try:
        master = connect(conn, baud, wait_heartbeat=True)
    except MavlinkConnectError as exc:
        print_mavlink_connect_error(exc, prefix="[Preflight]")
        return 1

    try:
        report = read_safety_params(master, timeout_s=args.timeout)
    finally:
        try:
            master.close()
        except Exception:
            pass

    print()
    print(format_report(report))
    return 1 if args.strict and not report.clean else 0


if __name__ == "__main__":
    raise SystemExit(main())
