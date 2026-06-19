"""Unit tests for Task 2 photo upload."""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

from valiant.autonomy.conops import task2_photo_filename
from valiant.autonomy.upload.drive import DriveUploader
from valiant.common.config import load_config


def test_local_copy_upload():
    cfg = load_config("vion")
    cfg = dict(cfg)
    cfg.setdefault("upload", {})["method"] = "local_copy"

    with tempfile.TemporaryDirectory() as tmp:
        photo_dir = Path(tmp) / "task2_photos"
        photo_dir.mkdir()
        cfg.setdefault("team", {})["photo_save_dir"] = str(photo_dir)

        filename = task2_photo_filename(cfg, 1)
        local_path = photo_dir / filename
        cv2.imwrite(str(local_path), np.zeros((32, 32, 3), dtype=np.uint8))

        uploader = DriveUploader(cfg)
        assert uploader.upload_task2_photo(str(local_path), 1)

        copied = photo_dir / "uploaded" / filename
        assert copied.is_file()
