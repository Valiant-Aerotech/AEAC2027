#!/usr/bin/env python3
"""Replay recorded footage and summarize CV detection stats (regression baseline)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from valiant.autonomy.cv.detector import TargetDetector
from valiant.common.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="CV regression test on video file")
    parser.add_argument("--video", required=True, help="Path to recorded scrcpy/webcam footage")
    parser.add_argument("--output", default=None, help="JSONL log path (default: logs/cv_regression.jsonl)")
    parser.add_argument("--max-frames", type=int, default=0, help="0 = entire video")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.is_file():
        print(f"ERROR: video not found: {video_path}")
        return 1

    cfg = load_config("vion")
    detector = TargetDetector(cfg)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: could not open {video_path}")
        return 1

    log_path = Path(args.output) if args.output else Path("logs") / "cv_regression.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    frames = 0
    dry_frames = 0
    shot_frames = 0
    both_frames = 0
    neither_frames = 0

    with open(log_path, "w", encoding="utf-8") as log_file:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames += 1
            if args.max_frames and frames > args.max_frames:
                break

            packet = detector.detect(frame)
            has_dry = packet.has_dry_target
            has_shot = len(packet.shot) > 0
            if has_dry:
                dry_frames += 1
            if has_shot:
                shot_frames += 1
            if has_dry and has_shot:
                both_frames += 1
            if not has_dry and not has_shot:
                neither_frames += 1

            if frames % 30 == 0:
                record = {
                    "frame": frames,
                    "dry": len(packet.dry),
                    "shot": len(packet.shot),
                    "method": packet.method,
                }
                log_file.write(json.dumps(record) + "\n")

    cap.release()

    summary = {
        "video": str(video_path),
        "frames": frames,
        "dry_frames": dry_frames,
        "shot_frames": shot_frames,
        "both_frames": both_frames,
        "neither_frames": neither_frames,
        "dry_pct": round(100 * dry_frames / max(frames, 1), 1),
        "shot_pct": round(100 * shot_frames / max(frames, 1), 1),
        "log": str(log_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
