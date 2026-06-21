"""Unit tests for subframe YOLO detector (mocked inference)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from valiant.autonomy.cv.subframe_yolo import SubframeYoloDetector


def _cfg() -> dict:
    return {
        "cv": {
            "subframe_size": 294,
            "max_subframes": 1,
            "confidence_threshold": 0.5,
            "nms_threshold": 0.4,
            "models": {"dry": "models/dry.onnx"},
        }
    }


def test_detect_dry_maps_tile_box_to_full_frame():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    det = SubframeYoloDetector(_cfg())

    fake_hit = ([20.0, 30.0, 80.0, 90.0], 0.9, 0)

    with patch.object(det, "_ensure_loaded", return_value=True):
        det._onnx = MagicMock()
        det._onnx.infer_tile.return_value = [fake_hit]
        det.model_path = __import__("pathlib").Path("models/dry.onnx")

        hits = det.detect_dry(frame)

    assert len(hits) == 1
    hit = hits[0]
    assert hit.confidence == 0.9
    assert hit.bbox[0] >= 52
    assert hit.bbox[1] >= 66
    assert hit.cx == (hit.bbox[0] + hit.bbox[2]) // 2


def test_detect_dry_empty_without_model():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    det = SubframeYoloDetector({"cv": {"models": {"dry": "models/missing.onnx"}}})
    with patch("valiant.autonomy.cv.subframe_yolo._resolve_dry_model_path", return_value=None):
        assert det.detect_dry(frame) == []
