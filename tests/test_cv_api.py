"""Tests for CV public API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from valiant.autonomy.cv import (
    create_target_detector,
    draw_mission_overlay,
    hits_to_bench_dict,
)
from valiant.autonomy.packets import TargetHit


def test_hits_to_bench_dict_schema():
    hits = [
        TargetHit(cx=100, cy=200, area=500, bbox=(80, 180, 120, 220), confidence=0.9),
    ]
    out = hits_to_bench_dict(hits)
    assert len(out) == 1
    d = out[0]
    assert set(d.keys()) == {"bbox", "confidence", "class_id", "cx", "cy", "area"}
    assert d["bbox"] == [80, 180, 120, 220]
    assert d["confidence"] == 0.9
    assert d["class_id"] == 0


def test_draw_mission_overlay_reads_cfg(monkeypatch):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cfg = {
        "cv": {
            "method": "yolo",
            "inference_mode": "subframe",
            "subframe_size": 294,
        }
    }
    captured: dict = {}

    def fake_draw(frame_in, packet, state, **kwargs):
        captured.update(kwargs)
        return frame_in

    monkeypatch.setattr("valiant.autonomy.cv.api.draw_overlay", fake_draw)
    draw_mission_overlay(frame, None, "TEST", cfg)
    assert captured["show_yolo_crop"] is True
    assert captured["inference_mode"] == "subframe"
    assert captured["subframe_size"] == 294


def test_create_target_detector_returns_detector():
    cfg = {"cv": {"method": "hsv"}}
    det = create_target_detector(cfg)
    assert det.method == "hsv"


def test_bench_dict_matches_packet_dry():
    cfg = {"cv": {"method": "hsv"}}
    det = create_target_detector(cfg)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with patch.object(det, "detect") as mock_detect:
        from valiant.autonomy.packets import CVPacket

        hit = TargetHit(cx=10, cy=20, area=100, bbox=(0, 0, 20, 40), confidence=0.8)
        mock_detect.return_value = CVPacket(dry=[hit], method="yolo")
        packet = det.detect(frame)
        assert hits_to_bench_dict(packet.dry) == hits_to_bench_dict([hit])
