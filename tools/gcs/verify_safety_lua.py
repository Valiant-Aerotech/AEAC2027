#!/usr/bin/env python3
"""Verify FC safety.lua is enabled before field flight."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valiant.autonomy.flight.fc_safety import (  # noqa: E402
    SafetyPreflightError,
    assert_safety_lua,
    verify_safety_lua,
)
from valiant.autonomy.flight.profile import (  # noqa: E402
    apply_flight_profile,
    mavlink_connection_for_gcs,
)
from valiant.common.config import load_config  # noqa: E402
from valiant.common.mavlink import MavlinkConnectError, connect, print_mavlink_connect_error  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify SCR_ENABLE and safety.lua on flight controller",
    )
    parser.add_argument("--connection", default=None, help="MAVLink URL override (e.g. COM5 on GCS)")
    parser.add_argument(
        "--profile",
        default="vivi_orbit",
        help="Flight profile for safety settings (connection uses GCS radio by default)",
    )
    parser.add_argument("--drone", default="vion")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings too")
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config(args.drone), args.profile)
    conn, baud = mavlink_connection_for_gcs(cfg)
    if args.connection:
        conn = args.connection

    print(f"[Safety] Connecting {conn} @ {baud} ...")
    try:
        master = connect(conn, baud, wait_heartbeat=True)
    except MavlinkConnectError as exc:
        print_mavlink_connect_error(exc, prefix="[Safety]")
        return 1
    try:
        if args.strict:
            report = verify_safety_lua(master, cfg, sitl=False)
            for warning in report.warnings:
                print(f"[Safety] WARN: {warning}")
            if report.ok and not report.warnings:
                print("[Safety] safety.lua preflight OK")
                return 0
            for err in report.errors:
                print(f"[Safety] FAIL: {err}")
            return 1
        assert_safety_lua(master, cfg, sitl=False)
        return 0
    except SafetyPreflightError:
        return 1
    except RuntimeError:
        return 1
    finally:
        try:
            master.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
