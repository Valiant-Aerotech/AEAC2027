"""YOLOv8 ONNX inference via onnxruntime (no PyTorch required at runtime)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from valiant.autonomy.cv.yolo_crop import extract_center_crop, resize_for_yolo
from valiant.autonomy.packets import TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt


class OnnxYoloDryDetector:
    """Run a YOLOv8-exported dry-target ONNX model on a center crop."""

    def __init__(self, model_path: Path, *, input_size: int, conf_thresh: float):
        import onnxruntime as ort

        self.input_size = input_size
        self.conf_thresh = conf_thresh
        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        inputs = self.session.get_inputs()
        if inputs:
            shape = inputs[0].shape
            if len(shape) == 4 and isinstance(shape[2], int) and shape[2] > 0:
                self.input_size = shape[2]
        self.input_name = inputs[0].name

    def _preprocess(self, bgr: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(
            rgb,
            (self.input_size, self.input_size),
            interpolation=cv2.INTER_LINEAR,
        )
        blob = resized.astype(np.float32) / 255.0
        return np.transpose(blob, (2, 0, 1))[np.newaxis, ...]

    def _best_detection(
        self,
        output: npt.NDArray[np.float32],
        crop_w: int,
        crop_h: int,
        start_x: int,
        start_y: int,
    ) -> TargetHit | None:
        # YOLOv8 ONNX: [1, 4 + num_classes, num_predictions]
        preds = np.squeeze(output, axis=0)
        if preds.ndim != 2:
            return None
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T

        best_conf = self.conf_thresh
        best_hit = None
        scale_x = crop_w / self.input_size
        scale_y = crop_h / self.input_size

        for row in preds:
            cx, cy, w, h = row[0:4]
            if row.shape[0] > 4:
                conf = float(np.max(row[4:]))
            else:
                conf = 1.0
            if conf < best_conf:
                continue

            x1 = int((cx - w / 2) * scale_x + start_x)
            y1 = int((cy - h / 2) * scale_y + start_y)
            x2 = int((cx + w / 2) * scale_x + start_x)
            y2 = int((cy + h / 2) * scale_y + start_y)
            bw, bh = x2 - x1, y2 - y1
            if bw <= 0 or bh <= 0:
                continue

            best_conf = conf
            best_hit = TargetHit(
                cx=int(x1 + bw / 2),
                cy=int(y1 + bh / 2),
                area=int(bw * bh),
                bbox=(x1, y1, x2, y2),
                confidence=conf,
            )
        return best_hit

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> TargetHit | None:
        cropped, start_x, start_y, crop_w, crop_h = extract_center_crop(
            frame,
            self.input_size,
        )
        if cropped.size == 0:
            return None

        blob = self._preprocess(cropped)
        outputs = self.session.run(None, {self.input_name: blob})
        return self._best_detection(outputs[0], crop_w, crop_h, start_x, start_y)
