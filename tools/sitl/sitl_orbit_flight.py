#!/usr/bin/env python3
"""SITL field orbit validation: takeoff, orbit, LOITER."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valiant.autonomy.field_orbit import run_field_orbit  # noqa: E402
from valiant.autonomy.flight.profile import apply_flight_profile  # noqa: E402
from valiant.common.config import load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="SITL orbit flight then LOITER")
    parser.add_argument("--connection", default=None)
    parser.add_argument("--takeoff-alt", type=float, default=None)
    parser.add_argument("--laps", type=int, default=None, help="Override orbit lap count")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Assume armed, GUIDED, airborne",
    )
    parser.add_argument("--gcs-ip", default=None)
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config("vion"), "sitl_orbit")
    if args.laps is not None:
        cfg.setdefault("field_orbit", {})["laps"] = args.laps
    mavlink = cfg.get("mavlink", {})
    conn = args.connection or mavlink.get("sitl_connection") or mavlink.get("connection")
    takeoff = args.takeoff_alt
    if takeoff is None:
        takeoff = float(cfg.get("field_orbit", {}).get("trigger_alt_m", 10.0))

    run_field_orbit(
        connection=conn,
        cfg=cfg,
        sitl=True,
        skip_preflight=args.skip_preflight,
        skip_standby=args.skip_preflight,
        takeoff_alt_m=takeoff,
        gcs_ip=args.gcs_ip,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
