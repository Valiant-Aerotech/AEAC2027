"""Target detector - HSV + optional YOLO, outputs CVPacket."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from valiant.autonomy.cv.exceptions import BadFrameError, LowConfidenceError
from valiant.autonomy.cv.hsv import detect_hsv
from valiant.autonomy.packets import CVPacket, TargetHit
from valiant.common.config import repo_root

if TYPE_CHECKING:
    import numpy.typing as npt

CAPTURE_WIDTH = 1280
CAPTURE_HEIGHT = 720
R_S = 224
CONF_THRESH = 0.35


def _resolve_model_path(cfg: dict) -> Path | None:
    cv_cfg = cfg.get("cv", {})
    model_rel = cv_cfg.get("models", {}).get("dry", "models/dry.onnx")
    for candidate in (repo_root() / model_rel, repo_root() / "models" / "best.onnx"):
        if candidate.is_file():
            return candidate
    return None


class _YOLOBackend:
    """Lazy-loaded YOLO ONNX backend."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.model = None
        self.model_path: Path | None = None
        self.r_s = R_S
        self.conf_thresh = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)

    def _ensure_loaded(self) -> bool:
        if self.model is not None:
            return True
        path = _resolve_model_path(self.cfg)
        if path is None:
            return False
        from ultralytics import YOLO

        print(f"[YOLO] Loading ONNX from: {path}")
        self.model = YOLO(str(path), task="detect")
        self.model_path = path
        return True

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> TargetHit | None:
        if not self._ensure_loaded():
            return None

        h, w = frame.shape[:2]
        scale_x = w / CAPTURE_WIDTH
        scale_y = h / CAPTURE_HEIGHT
        crop_w = max(1, int(self.r_s * scale_x))
        crop_h = max(1, int(self.r_s * scale_y))
        start_x = max(0, (w - crop_w) // 2)
        start_y = max(0, (h - crop_h) // 2)
        cropped = frame[start_y : start_y + crop_h, start_x : start_x + crop_w]
        if cropped.shape[0] <= 0 or cropped.shape[1] <= 0:
            return None

        resized = cv2.resize(cropped, (self.r_s, self.r_s), interpolation=cv2.INTER_AREA)
        results = self.model(resized, verbose=False)

        best_conf = self.conf_thresh
        best_hit = None
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0].cpu().numpy())
                if conf < best_conf:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                full_x1 = int((x1 / self.r_s) * crop_w + start_x)
                full_y1 = int((y1 / self.r_s) * crop_h + start_y)
                full_x2 = int((x2 / self.r_s) * crop_w + start_x)
                full_y2 = int((y2 / self.r_s) * crop_h + start_y)
                bw, bh = full_x2 - full_x1, full_y2 - full_y1
                best_conf = conf
                best_hit = TargetHit(
                    cx=int(full_x1 + bw / 2),
                    cy=int(full_y1 + bh / 2),
                    area=int(bw * bh),
                    bbox=(full_x1, full_y1, full_x2, full_y2),
                    confidence=conf,
                )
        return best_hit


class TargetDetector:
    """Unified detector: hsv, yolo, or both (HSV primary, YOLO fallback for dry)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.method = cfg.get("cv", {}).get("method", "hsv").lower()
        self._yolo: _YOLOBackend | None = None
        self._frame_id = 0
        self.min_confidence = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)

        if self.method in ("yolo", "both"):
            self._yolo = _YOLOBackend(cfg)
        print(f"[CV] TargetDetector method={self.method}")

    def detect(self, frame: npt.NDArray[np.uint8] | None) -> CVPacket:
        if frame is None or frame.size == 0:
            raise BadFrameError("Frame is None or empty")

        self._frame_id += 1
        packet = CVPacket(frame_id=self._frame_id, method=self.method)

        dry_hit: TargetHit | None = None
        shot_hit: TargetHit | None = None

        if self.method in ("hsv", "both"):
            dry_hit, shot_hit = detect_hsv(frame, self.cfg)
            if dry_hit:
                packet.dry.append(dry_hit)
            if shot_hit:
                packet.shot.append(shot_hit)

        if self.method == "yolo" or (self.method == "both" and not packet.dry):
            yolo_hit = self._yolo.detect_dry(frame) if self._yolo else None
            if yolo_hit:
                if yolo_hit.confidence < self.min_confidence:
                    raise LowConfidenceError(
                        f"YOLO confidence {yolo_hit.confidence:.2f} below {self.min_confidence}"
                    )
                packet.dry.append(yolo_hit)

        if self.method == "yolo" and not self._yolo:
            path = _resolve_model_path(self.cfg)
            if path is None:
                print("[CV] WARNING: yolo method set but no ONNX model found - falling back to HSV")
                dry_hit, shot_hit = detect_hsv(frame, self.cfg)
                packet.method = "hsv_fallback"
                if dry_hit:
                    packet.dry.append(dry_hit)
                if shot_hit:
                    packet.shot.append(shot_hit)

        return packet

    def detect_target(self, frame: npt.NDArray[np.uint8] | None):
        """Return primary dry target as (cx, cy, area, bbox) or None."""
        try:
            packet = self.detect(frame)
        except (BadFrameError, LowConfidenceError):
            return None
        return packet.primary_dry_tuple()


# Backwards-compatible alias
YOLODetector = TargetDetector
