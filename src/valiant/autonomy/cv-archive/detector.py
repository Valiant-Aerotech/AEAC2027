"""Target detector - HSV + optional YOLO, outputs CVPacket."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from valiant.autonomy.cv.exceptions import BadFrameError, LowConfidenceError
from valiant.autonomy.cv.hsv import detect_hsv, detect_hsv_shot
from valiant.autonomy.cv.yolo_crop import YOLO_INPUT_SIZE
from valiant.autonomy.cv.yolo_onnx import OnnxYoloDryDetector
from valiant.autonomy.packets import CVPacket
from valiant.common.config import repo_root

if TYPE_CHECKING:
    import numpy.typing as npt

CONF_THRESH = 0.35
DEFAULT_DRY_MODEL = "models/best.onnx"


def _resolve_model_path(cfg: dict) -> Path | None:
    cv_cfg = cfg.get("cv", {})
    model_rel = cv_cfg.get("models", {}).get("dry", DEFAULT_DRY_MODEL)
    candidates = (
        repo_root() / model_rel,
        repo_root() / "models" / "best.onnx",
        repo_root() / "models" / "dry.onnx",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class _YOLOBackend:
    """Lazy-loaded YOLO ONNX backend via onnxruntime (no PyTorch at runtime)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._detector: OnnxYoloDryDetector | None = None
        self.model_path: Path | None = None
        self.input_size = cfg.get("cv", {}).get("yolo_input_size", YOLO_INPUT_SIZE)
        self.conf_thresh = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)

    def _ensure_loaded(self) -> bool:
        if self._detector is not None:
            return True
        path = _resolve_model_path(self.cfg)
        if path is None:
            return False
        print(f"[YOLO] Loading ONNX from: {path} (onnxruntime)")
        self._detector = OnnxYoloDryDetector(
            path,
            input_size=self.input_size,
            conf_thresh=self.conf_thresh,
        )
        self.model_path = path
        self.input_size = self._detector.input_size
        return True

    def detect_dry(self, frame: npt.NDArray[np.uint8]):
        if not self._ensure_loaded() or self._detector is None:
            return None
        return self._detector.detect_dry(frame)


class TargetDetector:
    """Unified detector: hsv, yolo, or both.

    yolo: trained ONNX for dry targets; HSV for blue shot confirmation only.
    both: HSV dry+shot first; YOLO supplements dry if HSV finds nothing.
    hsv: colour thresholds only.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.method = cfg.get("cv", {}).get("method", "hsv").lower()
        self._yolo: _YOLOBackend | None = None
        self._frame_id = 0
        self.min_confidence = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)
        self.yolo_input_size = cfg.get("cv", {}).get("yolo_input_size", YOLO_INPUT_SIZE)

        if self.method in ("yolo", "both"):
            self._yolo = _YOLOBackend(cfg)
            if _resolve_model_path(cfg) is None:
                print("[CV] WARNING: yolo method set but no ONNX model found under models/")
            elif self._yolo._ensure_loaded():
                self.yolo_input_size = self._yolo.input_size
        print(f"[CV] TargetDetector method={self.method}")

    def detect(self, frame: npt.NDArray[np.uint8] | None) -> CVPacket:
        if frame is None or frame.size == 0:
            raise BadFrameError("Frame is None or empty")

        self._frame_id += 1
        packet = CVPacket(frame_id=self._frame_id, method=self.method)

        if self.method in ("hsv", "both"):
            dry_hit, shot_hit = detect_hsv(frame, self.cfg)
            if dry_hit:
                packet.dry.append(dry_hit)
            if shot_hit:
                packet.shot.append(shot_hit)

        if self.method == "yolo":
            yolo_hit = self._yolo.detect_dry(frame) if self._yolo else None
            if yolo_hit:
                if yolo_hit.confidence < self.min_confidence:
                    raise LowConfidenceError(
                        f"YOLO confidence {yolo_hit.confidence:.2f} below {self.min_confidence}"
                    )
                packet.dry.append(yolo_hit)
            elif _resolve_model_path(self.cfg) is None:
                print("[CV] WARNING: no ONNX model - falling back to HSV for dry+shot")
                packet.method = "hsv_fallback"
                dry_hit, shot_hit = detect_hsv(frame, self.cfg)
                if dry_hit:
                    packet.dry.append(dry_hit)
                if shot_hit:
                    packet.shot.append(shot_hit)
            else:
                shot_hit = detect_hsv_shot(frame, self.cfg)
                if shot_hit:
                    packet.shot.append(shot_hit)

        elif self.method == "both" and not packet.dry:
            yolo_hit = self._yolo.detect_dry(frame) if self._yolo else None
            if yolo_hit:
                if yolo_hit.confidence < self.min_confidence:
                    raise LowConfidenceError(
                        f"YOLO confidence {yolo_hit.confidence:.2f} below {self.min_confidence}"
                    )
                packet.dry.append(yolo_hit)

        return packet
