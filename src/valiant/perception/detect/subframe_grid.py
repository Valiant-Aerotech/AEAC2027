"""294px subframe grid geometry for spiral YOLO inference."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy.typing as npt

DEFAULT_SUBFRAME_SIZE = 294
DEFAULT_MAX_SUBFRAMES = 10
DEFAULT_MAX_TARGET_COVER_AREA = 100
DEFAULT_EDGE_MARGIN = 10
DEFAULT_NMS_THRESHOLD = 0.4


def crop_to_grid(frame: npt.NDArray[np.uint8], size: int) -> tuple[np.ndarray, int, int]:
    """Center-crop frame to a multiple of subframe size."""
    h, w = frame.shape[:2]
    new_h = (h // size) * size
    new_w = (w // size) * size
    if new_h <= 0 or new_w <= 0:
        return frame.copy(), 0, 0
    top = (h - new_h) // 2
    left = (w - new_w) // 2
    cropped = frame[top : top + new_h, left : left + new_w]
    return cropped, top, left


def extract_subframe(cropped: np.ndarray, r: int, c: int, size: int) -> np.ndarray:
    top = r * size
    left = c * size
    return cropped[top : top + size, left : left + size]


def convert_to_cropped_coords(
    bbox: list[float] | tuple[float, ...],
    r: int,
    c: int,
    size: int,
) -> list[float]:
    x1, y1, x2, y2 = bbox
    return [x1 + c * size, y1 + r * size, x2 + c * size, y2 + r * size]


def to_full_frame(
    bbox_cropped: list[float] | tuple[float, ...],
    top_off: int,
    left_off: int,
) -> list[float]:
    x1, y1, x2, y2 = bbox_cropped
    return [x1 + left_off, y1 + top_off, x2 + left_off, y2 + top_off]


def is_on_edge(bbox: list[float] | tuple[float, ...], size: int, margin: int) -> bool:
    x1, y1, x2, y2 = bbox
    return bool(x1 < margin or x2 > size - margin or y1 < margin or y2 > size - margin)


def compute_area(bbox: list[float] | tuple[float, ...]) -> float:
    x1, y1, x2, y2 = bbox
    return float((x2 - x1) * (y2 - y1))


def get_closest_subframe(px: float, py: float, rows: int, cols: int, size: int) -> tuple[int, int]:
    best_r, best_c = 0, 0
    best_dist = float("inf")
    for r in range(rows):
        for c in range(cols):
            cx = (c + 0.5) * size
            cy = (r + 0.5) * size
            dist = (px - cx) ** 2 + (py - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best_r, best_c = r, c
    return best_r, best_c


def get_spiral_order(rows: int, cols: int) -> list[tuple[int, int]]:
    center_x = (cols - 1) / 2.0
    center_y = (rows - 1) / 2.0
    cells: list[tuple[float, float, int, int]] = []
    for r in range(rows):
        for c in range(cols):
            dx = c - center_x
            dy = r - center_y
            dist = math.hypot(dx, dy)
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360.0
            cells.append((dist, angle, r, c))
    cells.sort(key=lambda x: (x[0], x[1]))
    return [(r, c) for _, _, r, c in cells]


def nms_detections(
    detections: list[dict[str, Any]],
    iou_threshold: float,
    conf_threshold: float,
) -> list[dict[str, Any]]:
    if not detections:
        return []
    boxes = []
    confs = []
    for d in detections:
        x1, y1, x2, y2 = d["bbox"]
        boxes.append([float(x1), float(y1), float(x2 - x1), float(y2 - y1)])
        confs.append(float(d["confidence"]))
    indices = cv2.dnn.NMSBoxes(boxes, confs, conf_threshold, iou_threshold)
    if len(indices) == 0:
        return []
    flat = indices.flatten() if hasattr(indices, "flatten") else indices
    return [detections[int(i)] for i in flat]


def grid_crop_bounds(frame_w: int, frame_h: int, size: int) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) of grid crop in full-frame coords."""
    _, top, left = crop_to_grid(np.zeros((frame_h, frame_w, 3), dtype=np.uint8), size)
    new_h = (frame_h // size) * size
    new_w = (frame_w // size) * size
    return left, top, left + new_w, top + new_h
