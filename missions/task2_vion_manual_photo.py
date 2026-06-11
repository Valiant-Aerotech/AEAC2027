#!/usr/bin/env python3
"""AEAC Task 2 - Vion manual photo capture fallback.

Usage:
    python missions/task2_vion_manual_photo.py
    python missions/task2_vion_manual_photo.py --source scrcpy --upload
    python missions/task2_vion_manual_photo.py --team ValiantAerotech --camera 0
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Vion Task 2 manual photo capture")
    parser.add_argument("--team", default=None, help="Team name in filename")
    parser.add_argument("--source", choices=["webcam", "scrcpy"], default="webcam")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index (webcam)")
    parser.add_argument("--output-dir", default=None, help="Photo output directory")
    parser.add_argument("--upload", action="store_true", help="Upload each photo after save")
    parser.add_argument("--scrcpy-ip", default=None, help="Wireless adb address")
    args = parser.parse_args()

    try:
        from valiant.autonomy.manual_capture import capture_task2_photos
        from valiant.common.config import load_config
    except ImportError:
        print("ERROR: valiant package not installed. Run: .\\tools\\setup.ps1")
        sys.exit(1)

    cfg = load_config("vion")
    team = args.team or cfg.get("team", {}).get("name", "ValiantAerotech")
    output_dir = args.output_dir or cfg.get("team", {}).get("photo_save_dir", "task2_photos")

    capture_task2_photos(
        team_name=team,
        source=args.source,
        camera_index=args.camera,
        output_dir=output_dir,
        cfg=cfg,
        phone_ip=args.scrcpy_ip,
        upload=args.upload,
    )


if __name__ == "__main__":
    main()
