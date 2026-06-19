#!/usr/bin/env python3
"""GCS-side field orbit runner (Pi UART or relay)."""

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
    parser = argparse.ArgumentParser(description="Run field orbit on companion MAVLink link")
    parser.add_argument("--profile", default="vivi_orbit")
    parser.add_argument("--connection", default=None)
    parser.add_argument("--gcs-ip", default=None)
    parser.add_argument("--drone", default="vion")
    parser.add_argument("--laps", type=int, default=None, help="Override orbit lap count")
    args = parser.parse_args()

    cfg = apply_flight_profile(load_config(args.drone), args.profile)
    if args.laps is not None:
        cfg.setdefault("field_orbit", {})["laps"] = args.laps
    mavlink = cfg.get("mavlink", {})
    conn = args.connection or mavlink.get("rpi_connection") or mavlink.get("connection")
    run_field_orbit(connection=conn, cfg=cfg, sitl=False, gcs_ip=args.gcs_ip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
