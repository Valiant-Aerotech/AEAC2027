#!/usr/bin/env python3
"""Smoke-test Task 2 photo upload (local copy or Drive if configured)."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np

from valiant.autonomy.conops import task2_photo_filename
from valiant.autonomy.upload.drive import DriveUploader
from valiant.common.config import load_config, repo_root


def run_test(*, target_number: int = 1) -> int:
    cfg = load_config()
    uploader = DriveUploader(cfg)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        photo_dir = tmp_path / "task2_photos"
        photo_dir.mkdir()
        cfg = dict(cfg)
        cfg.setdefault("team", {})["photo_save_dir"] = str(photo_dir)

        filename = task2_photo_filename(cfg, target_number)
        local_path = photo_dir / filename
        # Minimal valid JPEG header + padding
        img = np.zeros((48, 64, 3), dtype=np.uint8)
        import cv2

        cv2.imwrite(str(local_path), img)
        assert local_path.is_file(), "failed to write test image"

        ok = uploader.upload_task2_photo(str(local_path), target_number)
        if not ok:
            print("FAIL: upload_task2_photo returned False")
            return 1

        uploaded = photo_dir / "uploaded" / filename
        if not uploaded.is_file():
            print(f"FAIL: expected local copy at {uploaded}")
            return 1

        print(f"PASS: upload smoke test ({uploader.method}) -> {uploaded}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Task 2 photo upload path")
    parser.add_argument("--target", type=int, default=1)
    args = parser.parse_args()
    return run_test(target_number=args.target)


if __name__ == "__main__":
    raise SystemExit(main())
