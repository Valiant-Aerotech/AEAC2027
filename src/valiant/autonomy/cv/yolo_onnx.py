"""YOLOv8 ONNX inference via onnxruntime (no PyTorch required)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from valiant.autonomy.packets import TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt

CAPTURE_WIDTH = 1280
CAPTURE_HEIGHT = 720


class YoloOnnxDetector:
    """Run exported YOLOv8 .onnx weights with onnxruntime."""

    def __init__(self, model_path: Path, *, conf_thresh: float = 0.35):
        import onnxruntime as ort

        self.model_path = model_path
        self.conf_thresh = conf_thresh
        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        inp = self._session.get_inputs()[0]
        self._input_name = inp.name
        shape = inp.shape
        self.imgsz = int(shape[2]) if isinstance(shape[2], int) else 320
        print(f"[YOLO] ONNX runtime: {model_path} (imgsz={self.imgsz})")

    def _center_crop(self, frame: npt.NDArray[np.uint8]) -> tuple[np.ndarray, int, int, int, int]:
        h, w = frame.shape[:2]
        scale_x = w / CAPTURE_WIDTH
        scale_y = h / CAPTURE_HEIGHT
        crop_w = max(1, int(self.imgsz * scale_x))
        crop_h = max(1, int(self.imgsz * scale_y))
        start_x = max(0, (w - crop_w) // 2)
        start_y = max(0, (h - crop_h) // 2)
        cropped = frame[start_y : start_y + crop_h, start_x : start_x + crop_w]
        return cropped, start_x, start_y, crop_w, crop_h

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> TargetHit | None:
        cropped, start_x, start_y, crop_w, crop_h = self._center_crop(frame)
        if cropped.size == 0:
            return None

        resized = cv2.resize(
            cropped, (self.imgsz, self.imgsz), interpolation=cv2.INTER_AREA
        )
        blob = cv2.dnn.blobFromImage(resized, scalefactor=1 / 255.0, size=(self.imgsz, self.imgsz), swapRB=True)
        outputs = self._session.run(None, {self._input_name: blob})
        pred = outputs[0][0]  # (4+nc, anchors)

        if pred.shape[0] < 5:
            return None

        scores = pred[4]
        best_idx = int(np.argmax(scores))
        conf = float(scores[best_idx])
        if conf < self.conf_thresh:
            return None

        cx, cy, bw, bh = (float(pred[i, best_idx]) for i in range(4))
        x1 = (cx - bw / 2) / self.imgsz * crop_w + start_x
        y1 = (cy - bh / 2) / self.imgsz * crop_h + start_y
        x2 = (cx + bw / 2) / self.imgsz * crop_w + start_x
        y2 = (cy + bh / 2) / self.imgsz * crop_h + start_y

        full_x1 = int(max(0, min(frame.shape[1] - 1, x1)))
        full_y1 = int(max(0, min(frame.shape[0] - 1, y1)))
        full_x2 = int(max(0, min(frame.shape[1], x2)))
        full_y2 = int(max(0, min(frame.shape[0], y2)))
        box_w = max(full_x2 - full_x1, 1)
        box_h = max(full_y2 - full_y1, 1)

        return TargetHit(
            cx=int(full_x1 + box_w / 2),
            cy=int(full_y1 + box_h / 2),
            area=int(box_w * box_h),
            bbox=(full_x1, full_y1, full_x2, full_y2),
            confidence=conf,
        )
