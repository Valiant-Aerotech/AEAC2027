"""Target detector - HSV + optional YOLO, outputs CVPacket."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from valiant.autonomy.cv.exceptions import BadFrameError, LowConfidenceError
from valiant.autonomy.cv.hsv import detect_hsv
from valiant.autonomy.cv.yolo_onnx import YoloOnnxDetector
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
    candidates = [
        repo_root() / model_rel,
        repo_root() / "models" / "dry.onnx",
        repo_root() / "models" / "dry.pt",
        repo_root() / "models" / "best.onnx",
        repo_root() / "models" / "best.pt",
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None


def _resolve_shot_model_path(cfg: dict) -> Path | None:
    cv_cfg = cfg.get("cv", {})
    model_rel = cv_cfg.get("models", {}).get("shot", "models/shot.onnx")
    candidates = [
        repo_root() / model_rel,
        repo_root() / "models" / "shot.onnx",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class _ShotYOLOBackend:
    """Optional YOLO ONNX for wet/shot target confirmation."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._onnx: YoloOnnxDetector | None = None
        self.model_path: Path | None = None
        self.conf_thresh = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)

    def _ensure_loaded(self) -> bool:
        if self._onnx is not None:
            return True
        path = _resolve_shot_model_path(self.cfg)
        if path is None:
            return False
        self.model_path = path
        self._onnx = YoloOnnxDetector(path, conf_thresh=self.conf_thresh)
        return True

    def detect_shot(self, frame: npt.NDArray[np.uint8]) -> TargetHit | None:
        if not self._ensure_loaded() or self._onnx is None:
            return None
        return self._onnx.detect_dry(frame)


class _YOLOBackend:
    """Lazy-loaded YOLO backend (.onnx via onnxruntime, .pt via ultralytics)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._onnx: YoloOnnxDetector | None = None
        self._ultra_model = None
        self.model_path: Path | None = None
        self.r_s = R_S
        self.conf_thresh = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)

    def _ensure_loaded(self) -> bool:
        if self._onnx is not None or self._ultra_model is not None:
            return True
        path = _resolve_model_path(self.cfg)
        if path is None:
            return False
        self.model_path = path
        if path.suffix.lower() == ".onnx":
            self._onnx = YoloOnnxDetector(path, conf_thresh=self.conf_thresh)
            return True
        try:
            from ultralytics import YOLO

            print(f"[YOLO] Ultralytics loading: {path}")
            self._ultra_model = YOLO(str(path), task="detect")
            return True
        except ImportError as exc:
            print(f"[YOLO] Cannot load {path.suffix}: {exc}")
            print("[YOLO] Export to ONNX or fix PyTorch install (pip install --force-reinstall torch)")
            return False

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> TargetHit | None:
        if not self._ensure_loaded():
            return None

        if self._onnx is not None:
            return self._onnx.detect_dry(frame)

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
        results = self._ultra_model(resized, verbose=False)

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
    """Unified detector: yolo (dry) + hsv shot, or hsv-only, or both."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.method = cfg.get("cv", {}).get("method", "hsv").lower()
        self._yolo: _YOLOBackend | None = None
        self._shot_yolo: _ShotYOLOBackend | None = None
        self._frame_id = 0
        self.min_confidence = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)

        if self.method in ("yolo", "both"):
            self._yolo = _YOLOBackend(cfg)
        if self.method in ("yolo", "both") and _resolve_shot_model_path(cfg):
            self._shot_yolo = _ShotYOLOBackend(cfg)
        print(f"[CV] TargetDetector method={self.method}")

    def _append_yolo_dry(self, packet: CVPacket, frame: npt.NDArray[np.uint8]) -> None:
        if not self._yolo:
            return
        yolo_hit = self._yolo.detect_dry(frame)
        if yolo_hit is None:
            return
        if yolo_hit.confidence < self.min_confidence:
            raise LowConfidenceError(
                f"YOLO confidence {yolo_hit.confidence:.2f} below {self.min_confidence}"
            )
        packet.dry.append(yolo_hit)

    def _append_shot(self, packet: CVPacket, frame: npt.NDArray[np.uint8]) -> None:
        if self._shot_yolo:
            shot_hit = self._shot_yolo.detect_shot(frame)
            if shot_hit is not None and shot_hit.confidence >= self.min_confidence:
                packet.shot.append(shot_hit)
                return
        _, shot_hit = detect_hsv(frame, self.cfg)
        if shot_hit:
            packet.shot.append(shot_hit)

    def detect(self, frame: npt.NDArray[np.uint8] | None) -> CVPacket:
        if frame is None or frame.size == 0:
            raise BadFrameError("Frame is None or empty")

        self._frame_id += 1
        packet = CVPacket(frame_id=self._frame_id, method=self.method)

        if self.method == "hsv":
            dry_hit, shot_hit = detect_hsv(frame, self.cfg)
            if dry_hit:
                packet.dry.append(dry_hit)
            if shot_hit:
                packet.shot.append(shot_hit)
            return packet

        if self.method in ("yolo", "both"):
            # Trained YOLO for dry purple; shot via shot ONNX or HSV blue/wet.
            self._append_shot(packet, frame)

            if self.method == "yolo":
                if self._yolo and _resolve_model_path(self.cfg):
                    self._append_yolo_dry(packet, frame)
                else:
                    print("[CV] WARNING: yolo method set but no model in models/ - falling back to HSV dry")
                    dry_hit, _ = detect_hsv(frame, self.cfg)
                    packet.method = "hsv_fallback"
                    if dry_hit:
                        packet.dry.append(dry_hit)
                return packet

        # both: YOLO dry first, HSV dry fallback
        if self._yolo and _resolve_model_path(self.cfg):
            self._append_yolo_dry(packet, frame)
        if not packet.dry:
            dry_hit, shot_hit = detect_hsv(frame, self.cfg)
            if dry_hit:
                packet.dry.append(dry_hit)
            if shot_hit and not packet.shot:
                packet.shot.append(shot_hit)
        return packet
