#!/usr/bin/env python3
"""Live webcam test for the trained dry-target YOLO ONNX model.

Replaces the legacy models/test.py script. Uses the same pipeline as missions
and bench tools (TargetDetector + center 224x224 crop).

Usage:
    python tools/yolo_webcam_test.py
    python tools/yolo_webcam_test.py --camera 0
    python tools/yolo_webcam_test.py --method both
"""

from __future__ import annotations

import argparse
import sys

import cv2

from valiant.autonomy.cv.detector import TargetDetector
from valiant.autonomy.cv.ui import draw_overlay
from valiant.common.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="YOLO dry-target webcam test")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index")
    parser.add_argument(
        "--method",
        choices=["yolo", "both", "hsv"],
        default=None,
        help="Override cv.method from config",
    )
    args = parser.parse_args()

    cfg = load_config("vion")
    if args.method:
        cfg.setdefault("cv", {})["method"] = args.method

    method = cfg.get("cv", {}).get("method", "yolo")
    detector = TargetDetector(cfg)

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("ERROR: Could not open webcam")
        return 1

    print(f"YOLO webcam test (method={method}). Press Q to quit.")
    show_crop = method in ("yolo", "both")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            packet = detector.detect(frame)
            overlay = draw_overlay(
                frame,
                packet,
                "YOLO_TEST",
                show_yolo_crop=show_crop,
                yolo_crop_size=detector.yolo_input_size,
            )
            cv2.imshow("YOLO Webcam Test", overlay)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
