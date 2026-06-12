#!/usr/bin/env python3
"""Primary onboard mission entry for Vion (RPi companion)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from valiant.autonomy.flight.profile import apply_vion_profile, gcs_monitor_connection
from valiant.autonomy.flight.preflight import check_assets
from valiant.autonomy.orchestrator import run_auto_extinguish  # noqa: E402
from valiant.common.config import load_config, repo_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Vion onboard autonomous mission (RPi)")
    parser.add_argument("--connection", default=None, help="MAVLink serial to Pixhawk")
    parser.add_argument("--baud", type=int, default=None)
    parser.add_argument("--sim", action="store_true")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--profile", choices=["indoor", "outdoor"], default="indoor")
    parser.add_argument("--max-targets", type=int, default=None)
    parser.add_argument("--recording-dir", default=None, help="Replay depth from recordings")
    parser.add_argument(
        "--gcs-connection",
        default=None,
        help="Override gcs_monitor.connection UDP target",
    )
    parser.add_argument(
        "--gcs-ip",
        default=None,
        help="GCS laptop IP for telemetry mirror (shorthand for udpout:IP:14550)",
    )
    parser.add_argument(
        "--no-gcs-monitor",
        action="store_true",
        help="Disable UDP telemetry mirror to GCS",
    )
    args = parser.parse_args()

    cfg = load_config("vion")
    apply_vion_profile(
        cfg,
        args.profile,
        source="rpi_local",
        gcs_ip=args.gcs_ip,
        enable_gcs_monitor=not args.no_gcs_monitor,
    )

    gcs_conn = args.gcs_connection or gcs_monitor_connection(cfg, args.gcs_ip)
    if gcs_conn:
        cfg.setdefault("gcs_monitor", {})["connection"] = gcs_conn

    for warning in check_assets(cfg):
        print(f"[PREFLIGHT] Warning: {warning}")

    mavlink_cfg = cfg.get("mavlink", {})
    conn = args.connection or mavlink_cfg.get("connection", "/dev/ttyAMA0")
    baud = args.baud if args.baud is not None else mavlink_cfg.get("baud", 57600)

    cal_file = cfg.get("calibration", {}).get("file")
    if cal_file and not (repo_root() / cal_file).is_file() and not args.sim:
        print(
            "ERROR: calibration file missing. Copy config/vion_calibration.yaml.example "
            "to config/vion_calibration.yaml and calibrate before flight."
        )
        return 1

    if cfg.get("gcs_monitor", {}).get("enabled") and "127.0.0.1" in cfg["gcs_monitor"].get(
        "connection", ""
    ):
        print(
            "[PREFLIGHT] Warning: gcs_monitor points to localhost. "
            "Use --gcs-ip <laptop-ip> for GCS visibility."
        )

    run_auto_extinguish(
        connection=conn,
        baud=baud,
        sim=args.sim,
        headless=args.headless,
        max_targets=args.max_targets,
        source="rpi_local",
        profile=args.profile,
        recording_dir=args.recording_dir,
        cfg=cfg,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
