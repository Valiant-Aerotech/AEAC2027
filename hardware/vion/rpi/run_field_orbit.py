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
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config(args.drone), args.profile)
    conn, baud = mavlink_connection_for_host(cfg)
    if args.connection:
        conn = args.connection
    cfg.setdefault("mavlink", {})["baud"] = baud

    run_field_orbit(connection=conn, cfg=cfg, sitl=False, gcs_ip=args.gcs_ip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
