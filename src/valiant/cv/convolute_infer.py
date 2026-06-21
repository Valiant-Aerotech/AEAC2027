"""
Standalone CV demo using the production detector API.

For mission use: tools/valiant.py bench cv
"""

from __future__ import annotations

import argparse

import cv2

from valiant.autonomy.cv import create_target_detector, draw_mission_overlay
from valiant.common.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="CV subframe demo (production API)")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index")
    args = parser.parse_args()

    cfg = load_config()
    detector = create_target_detector(cfg)
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"ERROR: could not open camera {args.camera}")
        return 1

    print("Convolute infer demo. Press Q to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        packet = detector.detect(frame)
        display = draw_mission_overlay(frame, packet, "DEMO", cfg)
        cv2.imshow("CV Demo", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
