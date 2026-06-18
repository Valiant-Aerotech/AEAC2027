"""
target_detector.py
Reusable library for target detection using a YOLO model on subframes from a camera feed.
Exposes simple endpoints for integration into a larger project.
"""

import cv2
import numpy as np
import time
import math
from typing import List, Tuple, Optional, Dict, Any

# ============================================================
#  CONFIGURATION (can be overridden in constructor)
# ============================================================
DEFAULT_SUBFRAME_SIZE = 294
DEFAULT_MAX_SUBFRAMES = 10
DEFAULT_MAX_ALLOWED_TARGET_COVER_AREA = 100
DEFAULT_EDGE_MARGIN = 10
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_NMS_THRESHOLD = 0.4


# ============================================================
#  YOLO MODEL WRAPPER (using Ultralytics)
# ============================================================
class _YOLOModel:
    """Wrapper for Ultralytics YOLO model."""
    def __init__(self, model_path: str, conf_threshold: float):
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.conf_threshold = conf_threshold
            print(f"YOLO model loaded from {model_path}")
        except ImportError:
            raise ImportError("Ultralytics is not installed. Please install it with: pip install ultralytics")
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLO model: {e}")

    def predict(self, image: np.ndarray) -> List[List[float]]:
        """Run inference on a single image and return detections."""
        results = self.model(image, verbose=False)
        detections = []
        for r in results:
            if r.boxes is not None:
                boxes = r.boxes.xyxy.cpu().numpy()
                confs = r.boxes.conf.cpu().numpy()
                cls = r.boxes.cls.cpu().numpy().astype(int)
                for box, conf, cl in zip(boxes, confs, cls):
                    if conf >= self.conf_threshold:
                        detections.append([box[0], box[1], box[2], box[3], conf, cl])
        return detections


# ============================================================
#  HELPER FUNCTIONS (copied from original script)
# ============================================================
def _crop_to_grid(frame: np.ndarray, size: int) -> Tuple[np.ndarray, int, int]:
    h, w = frame.shape[:2]
    new_h = (h // size) * size
    new_w = (w // size) * size
    top = (h - new_h) // 2
    left = (w - new_w) // 2
    cropped = frame[top:top+new_h, left:left+new_w]
    return cropped, top, left

def _extract_subframe(cropped: np.ndarray, r: int, c: int, size: int) -> np.ndarray:
    top = r * size
    left = c * size
    return cropped[top:top+size, left:left+size]

def _convert_to_fullframe(bbox: List[float], r: int, c: int, size: int) -> List[float]:
    x1, y1, x2, y2 = bbox
    return [x1 + c*size, y1 + r*size, x2 + c*size, y2 + r*size]

def _is_on_edge(bbox: List[float], size: int, margin: int) -> bool:
    x1, y1, x2, y2 = bbox
    return (x1 < margin or x2 > size - margin or y1 < margin or y2 > size - margin)

def _compute_area(bbox: List[float]) -> float:
    x1, y1, x2, y2 = bbox
    return (x2 - x1) * (y2 - y1)

def _get_closest_subframe(px: float, py: float, rows: int, cols: int, size: int) -> Tuple[int, int]:
    best_r, best_c = 0, 0
    best_dist = float('inf')
    for r in range(rows):
        for c in range(cols):
            cx = (c + 0.5) * size
            cy = (r + 0.5) * size
            dist = (px - cx)**2 + (py - cy)**2
            if dist < best_dist:
                best_dist = dist
                best_r, best_c = r, c
    return best_r, best_c

def _get_spiral_order(rows: int, cols: int) -> List[Tuple[int, int]]:
    center_x = (cols - 1) / 2.0
    center_y = (rows - 1) / 2.0
    cells = []
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

def _nms(detections: List[Dict], iou_threshold: float, conf_threshold: float) -> List[Dict]:
    if not detections:
        return []
    boxes = []
    confs = []
    for d in detections:
        x1, y1, x2, y2 = d['bbox']
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confs.append(d['confidence'])
    indices = cv2.dnn.NMSBoxes(boxes, confs, conf_threshold, iou_threshold)
    if len(indices) == 0:
        return []
    if isinstance(indices, tuple):
        indices = indices[0]
    return [detections[i] for i in indices]

def _draw_grid_and_status(frame: np.ndarray,
                          size: int,
                          initial_processed: set,
                          reinf_processed: set) -> np.ndarray:
    h, w = frame.shape[:2]
    rows = h // size
    cols = w // size
    overlay = np.zeros_like(frame, dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            x1 = c * size
            y1 = r * size
            x2 = (c+1) * size
            y2 = (r+1) * size
            if (r, c) in initial_processed:
                color = (0, 255, 0)      # green
            elif (r, c) in reinf_processed:
                color = (255, 0, 0)      # blue
            else:
                continue
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    blended = cv2.addWeighted(frame, 1.0, overlay, 0.3, 0)
    for r in range(1, rows):
        y = r * size
        cv2.line(blended, (0, y), (w, y), (255, 255, 255), 1)
    for c in range(1, cols):
        x = c * size
        cv2.line(blended, (x, 0), (x, h), (255, 255, 255), 1)
    return blended


# ============================================================
#  MAIN PUBLIC CLASS
# ============================================================
class TargetDetector:
    """
    Reusable target detector using subframe sliding window with YOLO.
    Provides simple methods for status, detection, and frame retrieval.
    """

    def __init__(self,
                 camera_source: int = 1,
                 model_path: str = 'Put your model path here :p',
                 subframe_size: int = DEFAULT_SUBFRAME_SIZE,
                 max_subframes: int = DEFAULT_MAX_SUBFRAMES,
                 max_target_cover_area: int = DEFAULT_MAX_ALLOWED_TARGET_COVER_AREA,
                 edge_margin: int = DEFAULT_EDGE_MARGIN,
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 nms_threshold: float = DEFAULT_NMS_THRESHOLD):
        """
        Args:
            camera_source: camera device index (int) or video file path.
            model_path: path to YOLO weights (.pt).
            subframe_size: size of square subframe (pixels).
            max_subframes: maximum number of subframes processed per frame.
            max_target_cover_area: area threshold for re-inference (pixels²).
            edge_margin: margin from subframe border to consider edge.
            confidence_threshold: minimum confidence for detections.
            nms_threshold: IoU threshold for NMS.
        """
        self.subframe_size = subframe_size
        self.max_subframes = max_subframes
        self.max_target_cover_area = max_target_cover_area
        self.edge_margin = edge_margin
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold

        # Initialise camera
        self.cap = cv2.VideoCapture(camera_source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera source {camera_source}")

        # Get frame size
        ret, test_frame = self.cap.read()
        if not ret:
            raise RuntimeError("Failed to read first frame from camera")
        self.frame_width = test_frame.shape[1]
        self.frame_height = test_frame.shape[0]

        # Initialise model
        self.model = _YOLOModel(model_path, confidence_threshold)

        # Determine grid layout from first frame
        cropped, _, _ = _crop_to_grid(test_frame, self.subframe_size)
        self.rows = cropped.shape[0] // self.subframe_size
        self.cols = cropped.shape[1] // self.subframe_size
        self.spiral_order = _get_spiral_order(self.rows, self.cols)
        print(f"Grid: {self.rows} x {self.cols} subframes (cropped area)")

        # Internal state
        self.last_raw_frame = None          # cropped raw frame (BGR)
        self.last_annotated_frame = None    # frame with overlays and boxes
        self.last_detections = []           # list of detection dicts (full frame coords)
        self.last_initial_processed = set()
        self.last_reinf_processed = set()
        self.last_frame_ready = False

    def status(self) -> Dict[str, Any]:
        """
        Return status information about the detector.
        """
        return {
            'camera_open': self.cap.isOpened(),
            'frame_width': self.frame_width,
            'frame_height': self.frame_height,
            'subframe_size': self.subframe_size,
            'grid_rows': self.rows,
            'grid_cols': self.cols,
            'model_path': self.model.model.ckpt_path if hasattr(self.model.model, 'ckpt_path') else 'unknown',
            'confidence_threshold': self.confidence_threshold,
            'nms_threshold': self.nms_threshold,
            'max_subframes': self.max_subframes,
            'last_frame_processed': self.last_frame_ready,
        }

    def getCamFrame(self) -> Optional[np.ndarray]:
        """
        Return the raw unprocessed camera frame (BGR).
        If no frame is available, returns None.
        """
        ret, frame = self.cap.read()
        if not ret:
            return None
        # Crop to grid (centred)
        cropped, _, _ = _crop_to_grid(frame, self.subframe_size)
        self.last_raw_frame = cropped
        return cropped

    def getTargets(self) -> List[Dict[str, Any]]:
        """
        Process the current camera frame and return detections.
        Each detection is a dict with keys:
            'bbox': [x1, y1, x2, y2] in cropped frame coordinates,
            'confidence': float,
            'class_id': int,
            'sub_r': int, 'sub_c': int (grid position of subframe)
        """
        # Capture fresh frame
        ret, frame = self.cap.read()
        if not ret:
            self.last_frame_ready = False
            return []

        # Crop to grid
        cropped, top_off, left_off = _crop_to_grid(frame, self.subframe_size)
        self.last_raw_frame = cropped
        orig_h, orig_w = cropped.shape[:2]

        # Process subframes
        processed_subframes = set()
        initial_processed = set()
        reinf_processed = set()
        all_detections = []

        # Initial spiral inference
        subframes_processed = 0
        for r, c in self.spiral_order:
            if subframes_processed >= self.max_subframes:
                break
            subframe = _extract_subframe(cropped, r, c, self.subframe_size)
            dets = self.model.predict(subframe)
            for det in dets:
                x1, y1, x2, y2, conf, cls = det
                full_bbox = _convert_to_fullframe([x1, y1, x2, y2], r, c, self.subframe_size)
                all_detections.append({
                    'bbox': full_bbox,
                    'sub_bbox': [x1, y1, x2, y2],
                    'confidence': conf,
                    'class_id': cls,
                    'sub_r': r,
                    'sub_c': c
                })
            processed_subframes.add((r, c))
            initial_processed.add((r, c))
            subframes_processed += 1

        # Re-inference for edge detections with small area
        initial_detections = all_detections[:]
        for det in initial_detections:
            sub_bbox = det['sub_bbox']
            if _is_on_edge(sub_bbox, self.subframe_size, self.edge_margin):
                if _compute_area(sub_bbox) < self.max_target_cover_area:
                    bbox = det['bbox']
                    cx = (bbox[0] + bbox[2]) / 2.0
                    cy = (bbox[1] + bbox[3]) / 2.0
                    nr, nc = _get_closest_subframe(cx, cy, self.rows, self.cols, self.subframe_size)
                    if (nr, nc) not in processed_subframes:
                        subframe = _extract_subframe(cropped, nr, nc, self.subframe_size)
                        dets = self.model.predict(subframe)
                        for det2 in dets:
                            x1, y1, x2, y2, conf, cls = det2
                            full_bbox = _convert_to_fullframe([x1, y1, x2, y2], nr, nc, self.subframe_size)
                            all_detections.append({
                                'bbox': full_bbox,
                                'sub_bbox': [x1, y1, x2, y2],
                                'confidence': conf,
                                'class_id': cls,
                                'sub_r': nr,
                                'sub_c': nc
                            })
                        processed_subframes.add((nr, nc))
                        reinf_processed.add((nr, nc))

        # Apply NMS
        final_detections = _nms(all_detections, self.nms_threshold, self.confidence_threshold)

        # Store state for later retrieval
        self.last_initial_processed = initial_processed
        self.last_reinf_processed = reinf_processed
        self.last_detections = final_detections
        self.last_frame_ready = True

        # Build annotated frame (overlay + boxes)
        annotated = _draw_grid_and_status(cropped, self.subframe_size,
                                          initial_processed, reinf_processed)
        for det in final_detections:
            x1, y1, x2, y2 = det['bbox']
            x1 = max(0, min(x1, orig_w))
            y1 = max(0, min(y1, orig_h))
            x2 = max(0, min(x2, orig_w))
            y2 = max(0, min(y2, orig_h))
            if x2 > x1 and y2 > y1:
                cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                label = f"cls{det['class_id']}: {det['confidence']:.2f}"
                cv2.putText(annotated, label, (int(x1), int(y1)-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        self.last_annotated_frame = annotated

        # Return detections in a simple list of dicts with coordinates (cropped frame)
        return [{
            'bbox': d['bbox'],
            'confidence': d['confidence'],
            'class_id': d['class_id'],
            'sub_r': d['sub_r'],
            'sub_c': d['sub_c']
        } for d in final_detections]

    def getCVFrame(self) -> Optional[np.ndarray]:
        """
        Return the last annotated frame with overlays and bounding boxes.
        Returns None if no frame has been processed yet.
        """
        return self.last_annotated_frame

    def release(self):
        """Release camera resources."""
        if self.cap is not None:
            self.cap.release()

    def __del__(self):
        self.release()