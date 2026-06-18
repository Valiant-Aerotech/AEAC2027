"""Tests for YOLO ONNX runtime backend."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from valiant.autonomy.cv.yolo_onnx import YoloOnnxDetector

MODEL = Path("models/best.onnx")


@pytest.mark.skipif(not MODEL.is_file(), reason="models/best.onnx not present")
def test_yolo_onnx_loads_and_runs():
    det = YoloOnnxDetector(MODEL, conf_thresh=0.99)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    hit = det.detect_dry(frame)
  # blank frame — no detection expected at high threshold
    assert hit is None
