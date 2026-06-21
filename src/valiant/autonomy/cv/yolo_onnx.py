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

    def _blob_from_bgr(self, bgr: npt.NDArray[np.uint8]) -> np.ndarray:
        resized = cv2.resize(bgr, (self.imgsz, self.imgsz), interpolation=cv2.INTER_AREA)
        return cv2.dnn.blobFromImage(
            resized, scalefactor=1 / 255.0, size=(self.imgsz, self.imgsz), swapRB=True
        )

    def _parse_pred_tile(
        self,
        pred: np.ndarray,
        tile_w: int,
        tile_h: int,
    ) -> list[tuple[list[float], float, int]]:
        if pred.shape[0] < 5:
            return []
        num_anchors = pred.shape[1]
        num_classes = pred.shape[0] - 4
        out: list[tuple[list[float], float, int]] = []
        scale_x = tile_w / self.imgsz
        scale_y = tile_h / self.imgsz
        for idx in range(num_anchors):
            if num_classes == 1:
                conf = float(pred[4, idx])
                cls_id = 0
            else:
                class_scores = pred[4:, idx]
                cls_id = int(np.argmax(class_scores))
                conf = float(class_scores[cls_id])
            if conf < self.conf_thresh:
                continue
            cx, cy, bw, bh = (float(pred[i, idx]) for i in range(4))
            x1 = (cx - bw / 2) * scale_x
            y1 = (cy - bh / 2) * scale_y
            x2 = (cx + bw / 2) * scale_x
            y2 = (cy + bh / 2) * scale_y
            out.append(([x1, y1, x2, y2], conf, cls_id))
        return out

    def infer_tile(self, tile_bgr: npt.NDArray[np.uint8]) -> list[tuple[list[float], float, int]]:
        """Run ONNX on a square tile; boxes in tile-local pixel coordinates."""
        if tile_bgr.size == 0:
            return []
        th, tw = tile_bgr.shape[:2]
        blob = self._blob_from_bgr(tile_bgr)
        outputs = self._session.run(None, {self._input_name: blob})
        pred = outputs[0][0]
        return self._parse_pred_tile(pred, tw, th)

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> TargetHit | None:
        cropped, start_x, start_y, crop_w, crop_h = self._center_crop(frame)
        if cropped.size == 0:
            return None

        blob = self._blob_from_bgr(cropped)
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
