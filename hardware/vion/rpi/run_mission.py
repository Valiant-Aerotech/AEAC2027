#!/usr/bin/env python3
"""Primary onboard mission entry for Vion (RPi companion)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from valiant.autonomy.orchestrator import run_auto_extinguish  # noqa: E402
from valiant.common.config import load_config, repo_root  # noqa: E402


def _apply_profile_defaults(cfg: dict, profile: str) -> None:
    flight = cfg.setdefault("flight", {})
    flight["profile"] = profile
    cam = cfg.setdefault("camera", {})
    cam["source"] = "rpi_local"
    metric = cfg.setdefault("metric_recon", {})
    metric["rangefinder"] = "depth_at_target"
    gcs = cfg.setdefault("gcs_monitor", {})
    gcs["enabled"] = True
    if profile == "indoor":
        flight["require_gps"] = False
        flight["mode"] = "GUIDED_NOGPS"
        flight["arm_check_gps"] = False
        cfg.setdefault("safety", {})["geofence_abort"] = False


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
    args = parser.parse_args()

    cfg = load_config("vion")
    _apply_profile_defaults(cfg, args.profile)

    if args.gcs_connection:
        cfg.setdefault("gcs_monitor", {})["connection"] = args.gcs_connection

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
