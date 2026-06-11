#!/usr/bin/env python3
"""AEAC Task 2 - Vion manual photo capture fallback.

Usage:
    python missions/task2_vion_manual_photo.py
    python missions/task2_vion_manual_photo.py --team ValiantAerotech --camera 0
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Vion Task 2 manual photo capture")
    parser.add_argument("--team", default="ValiantAerotech", help="Team name in filename")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index")
    parser.add_argument("--output-dir", default="task2_photos", help="Photo output directory")
    args = parser.parse_args()

    try:
        from valiant.autonomy.manual_capture import capture_task2_photos
    except ImportError:
        print("ERROR: valiant package not installed. Run: .\\tools\\setup.ps1")
        sys.exit(1)

    capture_task2_photos(
        team_name=args.team,
        camera_index=args.camera,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
