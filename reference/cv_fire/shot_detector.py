"""Shot (wet) target detection: optional YOLO ONNX + HSV fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from valiant.autonomy.cv.constants import CONF_THRESH
from valiant.autonomy.cv.hsv import detect_hsv
from valiant.autonomy.cv.model_paths import resolve_shot_model_path
from valiant.autonomy.cv.yolo_onnx import YoloOnnxDetector
from valiant.autonomy.packets import TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt


class ShotDetector:
    """Detect extinguished / wetted targets."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._onnx: YoloOnnxDetector | None = None
        self.conf_thresh = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)
        if resolve_shot_model_path(cfg):
            self._yolo_enabled = True
        else:
            self._yolo_enabled = False

    def _ensure_loaded(self) -> bool:
        if self._onnx is not None:
            return True
        if not self._yolo_enabled:
            return False
        path = resolve_shot_model_path(self.cfg)
        if path is None:
            return False
        self._onnx = YoloOnnxDetector(path, conf_thresh=self.conf_thresh)
        return True

    def detect(self, frame: npt.NDArray[np.uint8], min_confidence: float) -> TargetHit | None:
        if self._yolo_enabled and self._ensure_loaded() and self._onnx is not None:
            hit = self._onnx.detect_dry(frame)
            if hit is not None and hit.confidence >= min_confidence:
                return hit
        _, shot_hit = detect_hsv(frame, self.cfg)
        return shot_hit
