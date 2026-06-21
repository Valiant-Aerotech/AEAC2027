"""
Bench wrapper for spiral subframe YOLO dry detection.

Production path: valiant.autonomy.cv.create_target_detector(cfg).detect(frame).
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from valiant.autonomy.cv import (
    create_target_detector,
    crop_preview_for_display,
    hits_to_bench_dict,
)
from valiant.autonomy.cv.exceptions import LowConfidenceError
from valiant.autonomy.cv.subframe_grid import (
    DEFAULT_EDGE_MARGIN,
    DEFAULT_MAX_SUBFRAMES,
    DEFAULT_MAX_TARGET_COVER_AREA,
    DEFAULT_NMS_THRESHOLD,
    DEFAULT_SUBFRAME_SIZE,
    crop_to_grid,
)


def _bench_cfg(
    *,
    subframe_size: int,
    max_subframes: int,
    max_target_cover_area: int,
    edge_margin: int,
    confidence_threshold: float,
    nms_threshold: float,
    model_path: str,
) -> dict:
    return {
        "cv": {
            "method": "yolo",
            "inference_mode": "subframe",
            "subframe_size": subframe_size,
            "max_subframes": max_subframes,
            "max_target_cover_area": max_target_cover_area,
            "edge_margin": edge_margin,
            "confidence_threshold": confidence_threshold,
            "nms_threshold": nms_threshold,
            "models": {"dry": model_path},
        }
    }


class SubframeDetectorBench:
    """Camera + getTargets() bench; inference via production TargetDetector."""

    def __init__(
        self,
        camera_source: int | str = 1,
        model_path: str = "models/best.pt",
        subframe_size: int = DEFAULT_SUBFRAME_SIZE,
        max_subframes: int = DEFAULT_MAX_SUBFRAMES,
        max_target_cover_area: int = DEFAULT_MAX_TARGET_COVER_AREA,
        edge_margin: int = DEFAULT_EDGE_MARGIN,
        confidence_threshold: float = 0.5,
        nms_threshold: float = DEFAULT_NMS_THRESHOLD,
    ):
        self.subframe_size = subframe_size
        self.cfg = _bench_cfg(
            subframe_size=subframe_size,
            max_subframes=max_subframes,
            max_target_cover_area=max_target_cover_area,
            edge_margin=edge_margin,
            confidence_threshold=confidence_threshold,
            nms_threshold=nms_threshold,
            model_path=model_path,
        )
        self._detector = create_target_detector(self.cfg)

        self.cap = cv2.VideoCapture(camera_source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera source {camera_source}")

        ret, test_frame = self.cap.read()
        if not ret:
            raise RuntimeError("Failed to read first frame from camera")
        self.frame_width = test_frame.shape[1]
        self.frame_height = test_frame.shape[0]

        cropped = crop_preview_for_display(test_frame, self.cfg)
        self.rows = cropped.shape[0] // self.subframe_size
        self.cols = cropped.shape[1] // self.subframe_size
        print(f"Grid: {self.rows} x {self.cols} subframes (cropped area)")

        self.last_raw_frame: np.ndarray | None = None
        self.last_annotated_frame: np.ndarray | None = None
        self.last_detections: list[dict[str, Any]] = []
        self.last_frame_ready = False

    def status(self) -> dict[str, Any]:
        return {
            "camera_open": self.cap.isOpened(),
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "subframe_size": self.subframe_size,
            "grid_rows": self.rows,
            "grid_cols": self.cols,
            "model_path": self.cfg["cv"]["models"]["dry"],
            "confidence_threshold": self.cfg["cv"]["confidence_threshold"],
            "nms_threshold": self.cfg["cv"]["nms_threshold"],
            "max_subframes": self.cfg["cv"]["max_subframes"],
            "last_frame_processed": self.last_frame_ready,
        }

    def getCamFrame(self) -> np.ndarray | None:
        ret, frame = self.cap.read()
        if not ret:
            return None
        cropped = crop_preview_for_display(frame, self.cfg)
        self.last_raw_frame = cropped
        return cropped

    def getTargets(self) -> list[dict[str, Any]]:
        """
        Process the current camera frame and return detections.

        Each detection dict:
            bbox: [x1, y1, x2, y2] in full sensor frame coordinates
            confidence, class_id (always 0 for single-class dry model)
            cx, cy, area
        """
        ret, frame = self.cap.read()
        if not ret:
            self.last_frame_ready = False
            return []

        try:
            packet = self._detector.detect(frame)
        except LowConfidenceError:
            self.last_frame_ready = True
            self.last_detections = []
            return []

        detections = hits_to_bench_dict(packet.dry)
        cropped, top_off, left_off = crop_to_grid(frame, self.subframe_size)
        self.last_raw_frame = cropped
        self.last_detections = detections
        self.last_frame_ready = True

        annotated = cropped.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cx1 = int(x1 - left_off)
            cy1 = int(y1 - top_off)
            cx2 = int(x2 - left_off)
            cy2 = int(y2 - top_off)
            if cx2 > cx1 and cy2 > cy1:
                cv2.rectangle(annotated, (cx1, cy1), (cx2, cy2), (0, 255, 0), 2)
                label = f"{det['confidence']:.2f}"
                cv2.putText(
                    annotated, label, (cx1, max(cy1 - 5, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
                )
        self.last_annotated_frame = annotated
        return detections

    def getCVFrame(self) -> np.ndarray | None:
        return self.last_annotated_frame

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()

    def __del__(self) -> None:
        self.release()
