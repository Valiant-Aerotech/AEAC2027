#!/usr/bin/env python3
"""Onboard Pi field orbit entry - GUIDED-triggered circle then LOITER."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from valiant.autonomy.field_orbit import run_field_orbit  # noqa: E402
from valiant.autonomy.flight.profile import apply_flight_profile, mavlink_connection_for_host  # noqa: E402
from valiant.common.config import load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vivi field orbit: wait for GUIDED, fly circle, LOITER",
    )
    parser.add_argument("--profile", default="vivi_orbit", help="Flight profile (default: vivi_orbit)")
    parser.add_argument("--connection", default=None, help="MAVLink URL override")
    parser.add_argument("--gcs-ip", default=None, help="GCS laptop IP for UDP telemetry")
    parser.add_argument("--drone", default="vion", help="Config id (default: vion)")
    parser.add_argument("--laps", type=int, default=None, help="Override orbit lap count")
    parser.add_argument(
        "--skip-safety-check",
        action="store_true",
        help="Skip safety.lua preflight (dev only)",
    )
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config(args.drone), args.profile)
    if args.laps is not None:
        cfg.setdefault("field_orbit", {})["laps"] = args.laps
    conn, baud = mavlink_connection_for_host(cfg)
    if args.connection:
        conn = args.connection
    cfg.setdefault("mavlink", {})["baud"] = baud

    try:
        run_field_orbit(
            connection=conn,
            cfg=cfg,
            sitl=False,
            gcs_ip=args.gcs_ip,
            skip_safety_check=args.skip_safety_check,
        )
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
