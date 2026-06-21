"""Detector parity: subframe backend wired through TargetDetector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from valiant.autonomy.cv.detector import TargetDetector
from valiant.autonomy.packets import TargetHit


def test_target_detector_subframe_sets_debug_backend():
    cfg = {
        "cv": {
            "method": "yolo",
            "inference_mode": "subframe",
            "confidence_threshold": 0.5,
            "models": {"dry": "models/dry.onnx"},
        }
    }
    det = TargetDetector(cfg)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    fake_hit = TargetHit(cx=100, cy=100, area=400, bbox=(80, 80, 120, 120), confidence=0.9)

    mock_backend = MagicMock()
    mock_backend.dry_backend_name = "subframe"
    mock_backend.detect_dry.return_value = [fake_hit]

    with patch("valiant.autonomy.cv.detector.resolve_dry_model_path", return_value=__import__("pathlib").Path("x")):
        det._yolo_dry = mock_backend
        packet = det.detect(frame)

    assert packet.method == "yolo"
    assert len(packet.dry) == 1
    assert packet.debug == {"dry_backend": "subframe"}
    assert packet.dry[0].bbox == (80, 80, 120, 120)


def test_subframe_backend_factory():
    from valiant.autonomy.cv.dry_detector import SubframeYoloDryBackend, create_yolo_dry_backend

    cfg = {"cv": {"method": "yolo", "inference_mode": "subframe", "models": {"dry": "models/dry.onnx"}}}
    with patch("valiant.autonomy.cv.dry_detector.resolve_dry_model_path", return_value=__import__("pathlib").Path("m")):
        backend = create_yolo_dry_backend(cfg)
    assert isinstance(backend, SubframeYoloDryBackend)
