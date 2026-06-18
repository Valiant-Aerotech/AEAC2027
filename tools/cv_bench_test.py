#!/usr/bin/env python3
"""Bench-test CV detection on webcam or video file. Prints CVPacket stream."""

from __future__ import annotations

import argparse
import json
import sys
import time

import cv2

from valiant.autonomy.cv.detector import TargetDetector
from valiant.autonomy.cv.ui import draw_overlay
from valiant.common.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="CV bench test - dry/shot detection")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index")
    parser.add_argument("--video", type=str, default=None, help="Video file path")
    parser.add_argument("--log", type=str, default=None, help="Write JSON lines log file")
    parser.add_argument("--method", type=str, default=None, help="Override cv.method")
    parser.add_argument("--max-frames", type=int, default=0, help="0 = unlimited")
    args = parser.parse_args()

    cfg = load_config("vion")
    if args.method:
        cfg.setdefault("cv", {})["method"] = args.method

    detector = TargetDetector(cfg)
    log_file = open(args.log, "w", encoding="utf-8") if args.log else None

    if args.video:
        cap = cv2.VideoCapture(args.video)
    else:
        cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("ERROR: Could not open video source")
        return 1

    print("CV bench test running. Press Q to quit.")
    print(f"Detection method: {cfg.get('cv', {}).get('method', 'hsv')}")
    model_path = None
    from valiant.autonomy.cv.detector import _resolve_model_path

    model_path = _resolve_model_path(cfg)
    if model_path:
        print(f"YOLO weights: {model_path}")
    elif cfg.get("cv", {}).get("method", "hsv") in ("yolo", "both"):
        print("WARNING: no model in models/ (dry.pt, dry.onnx, best.pt) — will fall back to HSV")
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if args.max_frames and frame_count > args.max_frames:
                break

            t0 = time.time()
            packet = detector.detect(frame)
            elapsed_ms = (time.time() - t0) * 1000

            record = {
                "frame_id": packet.frame_id,
                "method": packet.method,
                "dry": [{"cx": h.cx, "cy": h.cy, "area": h.area} for h in packet.dry],
                "shot": [{"cx": h.cx, "cy": h.cy, "area": h.area} for h in packet.shot],
                "elapsed_ms": round(elapsed_ms, 1),
            }
            print(json.dumps(record))

            if log_file:
                log_file.write(json.dumps(record) + "\n")

            method = cfg.get("cv", {}).get("method", "hsv")
            crop_size = cfg.get("cv", {}).get("yolo_input_size", 320)
            overlay = draw_overlay(
                frame,
                packet,
                "BENCH",
                show_yolo_crop=method in ("yolo", "both"),
                yolo_crop_size=crop_size,
            )
            cv2.putText(
                overlay,
                f"{elapsed_ms:.1f}ms",
                (10, 95),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                1,
            )
            cv2.imshow("CV Bench Test", overlay)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if log_file:
            log_file.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
