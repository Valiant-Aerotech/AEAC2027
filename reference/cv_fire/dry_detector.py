"""Dry target YOLO backends (subframe spiral or legacy center crop)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import cv2
import numpy as np

from valiant.autonomy.cv.constants import CAPTURE_HEIGHT, CAPTURE_WIDTH, CONF_THRESH, R_S
from valiant.autonomy.cv.model_paths import resolve_dry_model_path
from valiant.autonomy.cv.subframe_yolo import SubframeYoloDetector
from valiant.autonomy.cv.yolo_onnx import YoloOnnxDetector
from valiant.autonomy.packets import TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt


class DryYoloBackend(Protocol):
    dry_backend_name: str

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> list[TargetHit]: ...


class CenterCropYoloBackend:
    """Legacy 224px center-crop YOLO dry detection."""

    dry_backend_name = "center_crop"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._onnx: YoloOnnxDetector | None = None
        self._ultra_model = None
        self.r_s = R_S
        self.conf_thresh = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)

    def _ensure_loaded(self) -> bool:
        if self._onnx is not None or self._ultra_model is not None:
            return True
        path = resolve_dry_model_path(self.cfg)
        if path is None:
            return False
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

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> list[TargetHit]:
        if not self._ensure_loaded():
            return []

        if self._onnx is not None:
            hit = self._onnx.detect_dry(frame)
            return [hit] if hit is not None else []

        h, w = frame.shape[:2]
        scale_x = w / CAPTURE_WIDTH
        scale_y = h / CAPTURE_HEIGHT
        crop_w = max(1, int(self.r_s * scale_x))
        crop_h = max(1, int(self.r_s * scale_y))
        start_x = max(0, (w - crop_w) // 2)
        start_y = max(0, (h - crop_h) // 2)
        cropped = frame[start_y : start_y + crop_h, start_x : start_x + crop_w]
        if cropped.shape[0] <= 0 or cropped.shape[1] <= 0:
            return []

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
        return [best_hit] if best_hit is not None else []


class SubframeYoloDryBackend:
    """294px spiral subframe YOLO dry detection."""

    dry_backend_name = "subframe"

    def __init__(self, cfg: dict):
        self._detector = SubframeYoloDetector(cfg)

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> list[TargetHit]:
        return self._detector.detect_dry(frame)


def inference_mode(cfg: dict) -> str:
    return str(cfg.get("cv", {}).get("inference_mode", "subframe")).lower()


def create_yolo_dry_backend(cfg: dict) -> DryYoloBackend | None:
    if resolve_dry_model_path(cfg) is None:
        return None
    if inference_mode(cfg) == "center_crop":
        return CenterCropYoloBackend(cfg)
    return SubframeYoloDryBackend(cfg)
