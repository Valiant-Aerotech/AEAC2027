"""Center-crop geometry for YOLO dry-target inference (224x224 AI view)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

YOLO_INPUT_SIZE = 320


def center_crop_bounds(frame_w: int, frame_h: int, crop_size: int = YOLO_INPUT_SIZE) -> tuple[int, int, int, int]:
    """Return (start_x, start_y, crop_w, crop_h) for a centered square crop."""
    crop_w = min(crop_size, frame_w)
    crop_h = min(crop_size, frame_h)
    start_x = max(0, (frame_w - crop_w) // 2)
    start_y = max(0, (frame_h - crop_h) // 2)
    return start_x, start_y, crop_w, crop_h


def extract_center_crop(frame: npt.NDArray[np.uint8], crop_size: int = YOLO_INPUT_SIZE) -> tuple:
    """Return (cropped_bgr, start_x, start_y, crop_w, crop_h)."""
    h, w = frame.shape[:2]
    start_x, start_y, crop_w, crop_h = center_crop_bounds(w, h, crop_size)
    y_end = min(start_y + crop_h, h)
    x_end = min(start_x + crop_w, w)
    cropped = frame[start_y:y_end, start_x:x_end]
    return cropped, start_x, start_y, crop_w, crop_h


def resize_for_yolo(cropped, crop_size: int = YOLO_INPUT_SIZE):
    """Resize crop to model input size."""
    return cv2.resize(cropped, (crop_size, crop_size), interpolation=cv2.INTER_AREA)
