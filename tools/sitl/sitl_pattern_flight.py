#!/usr/bin/env python3
"""SITL guided box pattern: forward/turn legs, then LOITER for manual control."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valiant.autonomy.flight.profile import apply_flight_profile  # noqa: E402
from valiant.autonomy.sitl_pattern import run_pattern_flight  # noqa: E402
from valiant.common.config import load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fly a guided SITL box pattern, then LOITER",
    )
    parser.add_argument(
        "--connection",
        default=None,
        help="MAVLink URL (default: config mavlink.sitl_connection)",
    )
    parser.add_argument("--takeoff-alt", type=float, default=None, help="Takeoff altitude (m)")
    parser.add_argument("--speed", type=float, default=0.45, help="Forward speed (m/s)")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Assume already armed, GUIDED, and airborne",
    )
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config("vion"), "sitl")
    mavlink = cfg.get("mavlink", {})
    conn = args.connection or mavlink.get("sitl_connection") or mavlink.get("connection")
    takeoff = args.takeoff_alt
    if takeoff is None:
        takeoff = float(cfg.get("sitl", {}).get("takeoff_alt_m", 5.0))

    run_pattern_flight(
        connection=conn,
        cfg=cfg,
        takeoff_alt_m=takeoff,
        skip_preflight=args.skip_preflight,
        speed_m_s=args.speed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
