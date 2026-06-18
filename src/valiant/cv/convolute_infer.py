import cv2
import numpy as np
import time
import math
from typing import List, Tuple, Optional

# ============================================================
#  CONFIGURATION
# ============================================================
SUBFRAME_SIZE = 294
MAX_SUBFRAMES = 10                # maximum initial subframes to process per frame
MAX_ALLOWED_TARGET_COVER_AREA = 100  # area threshold in pixels² (subframe coordinates)
EDGE_MARGIN = 10                  # pixels from subframe border to be considered "on edge"
CONFIDENCE_THRESHOLD = 0.5
NMS_THRESHOLD = 0.4

# ============================================================
#  CAMERA ABSTRACTION (placeholder – Depends on what camera/on computer being used.)
# ============================================================
class Camera_abstraction:
    """
    Dummy camera class – replace with your actual implementation.
    Must have a method get_frame() that returns a numpy array (BGR).
    """
    def __init__(self, source=1):
        self.cap = cv2.VideoCapture(source)

    def get_frame(self) -> Optional[np.ndarray]:
        ret, frame = self.cap.read()
        return frame if ret else None

# ============================================================
#  YOLO MODEL WRAPPER (implemented with Ultralytics)
# ============================================================
class YOLOModel:
    """
    Wrapper for Ultralytics YOLO model.
    The predict() method accepts a 294×294 image (BGR) and returns
    a list of detections, each as [x1, y1, x2, y2, confidence, class_id]
    with coordinates in the subframe's local coordinate system (pixels).
    """
    def __init__(self, model_path: str):
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            print(f"YOLO model loaded from {model_path}")
        except ImportError:
            raise ImportError("Ultralytics is not installed. Please install it with: pip install ultralytics")
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLO model: {e}")

    def predict(self, image: np.ndarray) -> List[List[float]]:
        """
        Run inference on a single image (294x294) and return detections.
        """
        # Ultralytics YOLO expects RGB, but it can handle BGR as well (it converts internally)
        # We'll keep the image as is (OpenCV loads BGR)
        results = self.model(image, verbose=False)  # verbose=False to avoid printing

        detections = []
        for r in results:
            if r.boxes is not None:
                boxes = r.boxes.xyxy.cpu().numpy()      # (N, 4) in [x1,y1,x2,y2]
                confs = r.boxes.conf.cpu().numpy()      # (N,)
                cls = r.boxes.cls.cpu().numpy().astype(int)  # (N,)
                for box, conf, cl in zip(boxes, confs, cls):
                    if conf >= CONFIDENCE_THRESHOLD:
                        detections.append([box[0], box[1], box[2], box[3], conf, cl])
        return detections

# ============================================================
#  HELPER FUNCTIONS
# ============================================================
def crop_to_grid(frame: np.ndarray, size: int) -> Tuple[np.ndarray, int, int]:
    """
    Crop the frame to the largest centred rectangle whose dimensions
    are multiples of `size`. Returns the cropped image and the top/left offsets
    used to crop from the original.
    """
    h, w = frame.shape[:2]
    new_h = (h // size) * size
    new_w = (w // size) * size
    top = (h - new_h) // 2
    left = (w - new_w) // 2
    cropped = frame[top:top+new_h, left:left+new_w]
    return cropped, top, left

def extract_subframe(cropped: np.ndarray, r: int, c: int, size: int) -> np.ndarray:
    """Extract the subframe at grid position (r, c) from the cropped image."""
    top = r * size
    left = c * size
    return cropped[top:top+size, left:left+size]

def convert_to_fullframe(bbox: List[float], r: int, c: int, size: int) -> List[float]:
    """Convert subframe coordinates to full cropped-frame coordinates."""
    x1, y1, x2, y2 = bbox
    return [x1 + c*size, y1 + r*size, x2 + c*size, y2 + r*size]

def is_on_edge(bbox: List[float], size: int, margin: int) -> bool:
    """Check if the bounding box touches the subframe border within `margin` pixels."""
    x1, y1, x2, y2 = bbox
    return (x1 < margin or x2 > size - margin or y1 < margin or y2 > size - margin)

def compute_area(bbox: List[float]) -> float:
    """Compute area of bounding box."""
    x1, y1, x2, y2 = bbox
    return (x2 - x1) * (y2 - y1)

def get_closest_subframe(px: float, py: float, rows: int, cols: int, size: int) -> Tuple[int, int]:
    """
    Given a point (px, py) in full cropped-frame coordinates,
    return the grid index (r, c) of the subframe whose centre is closest.
    """
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

def get_spiral_order(rows: int, cols: int) -> List[Tuple[int, int]]:
    """
    Return a list of (row, col) indices sorted by distance from the centre
    and then by angle (clockwise) to approximate a spiral order.
    """
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

def nms(detections: List[dict], iou_threshold: float) -> List[dict]:
    """
    Apply Non-Maximum Suppression on detections (each dict must have 'bbox' and 'confidence').
    """
    if not detections:
        return []
    boxes = []
    confs = []
    for d in detections:
        x1, y1, x2, y2 = d['bbox']
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confs.append(d['confidence'])
    indices = cv2.dnn.NMSBoxes(boxes, confs, CONFIDENCE_THRESHOLD, iou_threshold)
    if len(indices) == 0:
        return []
    if isinstance(indices, tuple):
        indices = indices[0]
    return [detections[i] for i in indices]

def draw_grid_and_status(frame: np.ndarray,
                         size: int,
                         initial_processed: set,
                         reinf_processed: set) -> np.ndarray:
    """
    Draw subframe grid lines and colour‑coded status on the cropped frame.
    - Green overlay: subframe processed in the initial spiral.
    - Blue overlay: subframe processed during re‑inference.
    - Transparent: not processed.
    Grid lines are drawn in white.
    """
    h, w = frame.shape[:2]
    rows = h // size
    cols = w // size

    # Create an overlay
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

    # Blend overlay with original frame
    blended = cv2.addWeighted(frame, 1.0, overlay, 0.3, 0)

    # Draw grid lines
    for r in range(1, rows):
        y = r * size
        cv2.line(blended, (0, y), (w, y), (255, 255, 255), 1)
    for c in range(1, cols):
        x = c * size
        cv2.line(blended, (x, 0), (x, h), (255, 255, 255), 1)

    return blended

# ============================================================
#  MAIN SCRIPT
# ============================================================
def main():
    # 1. Initialise camera and model
    camera = Camera_abstraction()  # replace with your actual camera class
    model = YOLOModel('runs/detect/runs/train/target_detector-3/weights/best.pt')

    # 2. Get first frame to determine grid size (after cropping)
    first_frame = camera.get_frame()
    if first_frame is None:
        print("Failed to get frame from camera.")
        return
    cropped, _, _ = crop_to_grid(first_frame, SUBFRAME_SIZE)
    rows = cropped.shape[0] // SUBFRAME_SIZE
    cols = cropped.shape[1] // SUBFRAME_SIZE
    print(f"Grid: {rows} x {cols} subframes (cropped area)")

    # Pre-compute spiral order (depends only on grid dimensions)
    spiral_order = get_spiral_order(rows, cols)

    # 3. Loop for live feed
    frame_count = 0
    start_time = time.time()
    fps = 0
    show_overlay = True   # toggle state

    while True:
        frame = camera.get_frame()
        if frame is None:
            break

        # Crop to grid (centred)
        cropped, top_off, left_off = crop_to_grid(frame, SUBFRAME_SIZE)
        orig_h, orig_w = cropped.shape[:2]   # dimensions are multiples of SUBFRAME_SIZE

        # Process subframes
        processed_subframes = set()      # (r, c) already inferred
        initial_processed = set()        # from the spiral pass
        reinf_processed = set()          # from re‑inference
        all_detections = []              # each: dict with 'bbox', 'confidence', 'class_id', 'sub_r', 'sub_c'

        # --- 3a. Initial spiral inference (up to MAX_SUBFRAMES) ---
        subframes_processed = 0
        for r, c in spiral_order:
            if subframes_processed >= MAX_SUBFRAMES:
                break
            subframe = extract_subframe(cropped, r, c, SUBFRAME_SIZE)
            dets = model.predict(subframe)   # list of [x1, y1, x2, y2, conf, cls]
            for det in dets:
                x1, y1, x2, y2, conf, cls = det
                full_bbox = convert_to_fullframe([x1, y1, x2, y2], r, c, SUBFRAME_SIZE)
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

        # --- 3b. Re‑inference for edge detections with small area ---
        initial_detections = all_detections[:]
        for det in initial_detections:
            sub_bbox = det['sub_bbox']
            if is_on_edge(sub_bbox, SUBFRAME_SIZE, EDGE_MARGIN):
                if compute_area(sub_bbox) < MAX_ALLOWED_TARGET_COVER_AREA:
                    bbox = det['bbox']
                    cx = (bbox[0] + bbox[2]) / 2.0
                    cy = (bbox[1] + bbox[3]) / 2.0
                    nr, nc = get_closest_subframe(cx, cy, rows, cols, SUBFRAME_SIZE)
                    if (nr, nc) not in processed_subframes:
                        subframe = extract_subframe(cropped, nr, nc, SUBFRAME_SIZE)
                        dets = model.predict(subframe)
                        for det2 in dets:
                            x1, y1, x2, y2, conf, cls = det2
                            full_bbox = convert_to_fullframe([x1, y1, x2, y2], nr, nc, SUBFRAME_SIZE)
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

        # --- 3c. Apply NMS ---
        final_detections = nms(all_detections, NMS_THRESHOLD)

        # --- 3d. Prepare display frame (with or without overlay) ---
        if show_overlay:
            display_frame = draw_grid_and_status(cropped, SUBFRAME_SIZE,
                                                 initial_processed, reinf_processed)
        else:
            display_frame = cropped.copy()

        # --- 3e. Draw bounding boxes (always) ---
        for det in final_detections:
            x1, y1, x2, y2 = det['bbox']
            # Coordinates are already within the cropped frame
            x1 = max(0, min(x1, orig_w))
            y1 = max(0, min(y1, orig_h))
            x2 = max(0, min(x2, orig_w))
            y2 = max(0, min(y2, orig_h))
            if x2 > x1 and y2 > y1:
                cv2.rectangle(display_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                label = f"cls{det['class_id']}: {det['confidence']:.2f}"
                cv2.putText(display_frame, label, (int(x1), int(y1)-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)

        # --- 3f. FPS and overlay status ---
        frame_count += 1
        if frame_count % 30 == 0:
            end_time = time.time()
            fps = 30 / (end_time - start_time)
            start_time = end_time

        overlay_status = "ON" if show_overlay else "OFF"
        cv2.putText(display_frame, f"FPS: {fps:.1f}  Overlay: {overlay_status} (G to toggle)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # --- 3g. Terminal output ---
        print(f"FPS: {fps:.1f}")
        for det in final_detections:
            x1, y1, x2, y2 = det['bbox']
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            print(f"  Target: class={det['class_id']}, confidence={det['confidence']:.3f}, "
                  f"center=({cx:.1f}, {cy:.1f}), box=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f})")

        # Show the live feed
        cv2.imshow("Live Detection", display_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('g'):
            show_overlay = not show_overlay

    camera.cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()