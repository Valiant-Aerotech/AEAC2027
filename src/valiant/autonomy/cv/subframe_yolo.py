"""294px spiral subframe YOLO dry detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from valiant.autonomy.cv.subframe_grid import (
    DEFAULT_EDGE_MARGIN,
    DEFAULT_MAX_SUBFRAMES,
    DEFAULT_MAX_TARGET_COVER_AREA,
    DEFAULT_NMS_THRESHOLD,
    DEFAULT_SUBFRAME_SIZE,
    convert_to_cropped_coords,
    crop_to_grid,
    extract_subframe,
    get_closest_subframe,
    get_spiral_order,
    is_on_edge,
    compute_area,
    nms_detections,
    to_full_frame,
)
from valiant.autonomy.cv.yolo_onnx import YoloOnnxDetector
from valiant.autonomy.packets import TargetHit
from valiant.common.config import repo_root

if TYPE_CHECKING:
    import numpy.typing as npt


@dataclass(frozen=True)
class SubframeCvConfig:
    subframe_size: int = DEFAULT_SUBFRAME_SIZE
    max_subframes: int = DEFAULT_MAX_SUBFRAMES
    max_target_cover_area: int = DEFAULT_MAX_TARGET_COVER_AREA
    edge_margin: int = DEFAULT_EDGE_MARGIN
    nms_threshold: float = DEFAULT_NMS_THRESHOLD
    confidence_threshold: float = 0.35

    @classmethod
    def from_cfg(cls, cfg: dict) -> SubframeCvConfig:
        cv = cfg.get("cv", {})
        size = int(cv.get("subframe_size", cv.get("yolo_input_size", DEFAULT_SUBFRAME_SIZE)))
        return cls(
            subframe_size=size,
            max_subframes=int(cv.get("max_subframes", DEFAULT_MAX_SUBFRAMES)),
            max_target_cover_area=int(cv.get("max_target_cover_area", DEFAULT_MAX_TARGET_COVER_AREA)),
            edge_margin=int(cv.get("edge_margin", DEFAULT_EDGE_MARGIN)),
            nms_threshold=float(cv.get("nms_threshold", DEFAULT_NMS_THRESHOLD)),
            confidence_threshold=float(cv.get("confidence_threshold", 0.35)),
        )


def _resolve_dry_model_path(cfg: dict) -> Path | None:
    cv_cfg = cfg.get("cv", {})
    model_rel = cv_cfg.get("models", {}).get("dry", "models/dry.onnx")
    candidates = [
        repo_root() / model_rel,
        repo_root() / "models" / "best.onnx",
        repo_root() / "models" / "best.pt",
        repo_root() / "models" / "dry.onnx",
        repo_root() / "models" / "dry.pt",
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None


class _UltralyticsTileBackend:
    def __init__(self, path: Path, conf_threshold: float):
        from ultralytics import YOLO

        self._model = YOLO(str(path), task="detect")
        self.conf_threshold = conf_threshold
        print(f"[YOLO] Ultralytics subframe tiles: {path}")

    def predict_tile(self, tile_bgr: np.ndarray) -> list[tuple[list[float], float, int]]:
        results = self._model(tile_bgr, verbose=False)
        out: list[tuple[list[float], float, int]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box, conf, cls in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.conf.cpu().numpy(),
                result.boxes.cls.cpu().numpy().astype(int),
            ):
                c = float(conf)
                if c < self.conf_threshold:
                    continue
                x1, y1, x2, y2 = box
                out.append(([float(x1), float(y1), float(x2), float(y2)], c, int(cls)))
        return out


class SubframeYoloDetector:
    """Spiral subframe dry detection; returns TargetHit in full sensor frame."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.params = SubframeCvConfig.from_cfg(cfg)
        self.model_path: Path | None = None
        self._onnx: YoloOnnxDetector | None = None
        self._ultra: _UltralyticsTileBackend | None = None

    def _ensure_loaded(self) -> bool:
        if self._onnx is not None or self._ultra is not None:
            return True
        path = _resolve_dry_model_path(self.cfg)
        if path is None:
            return False
        self.model_path = path
        if path.suffix.lower() == ".onnx":
            self._onnx = YoloOnnxDetector(path, conf_thresh=self.params.confidence_threshold)
            if self._onnx.imgsz != self.params.subframe_size:
                print(
                    f"[YOLO] WARNING: ONNX imgsz={self._onnx.imgsz} "
                    f"!= cv.subframe_size={self.params.subframe_size}"
                )
            return True
        try:
            self._ultra = _UltralyticsTileBackend(path, self.params.confidence_threshold)
            return True
        except ImportError as exc:
            print(f"[YOLO] Cannot load {path}: {exc}")
            return False

    def _predict_tile(self, tile: np.ndarray) -> list[tuple[list[float], float, int]]:
        if self._onnx is not None:
            return self._onnx.infer_tile(tile)
        if self._ultra is not None:
            return self._ultra.predict_tile(tile)
        return []

    def detect_dry(self, frame: npt.NDArray[np.uint8]) -> list[TargetHit]:
        if not self._ensure_loaded():
            return []

        size = self.params.subframe_size
        cropped, top_off, left_off = crop_to_grid(frame, size)
        if cropped.size == 0:
            return []

        rows = cropped.shape[0] // size
        cols = cropped.shape[1] // size
        if rows < 1 or cols < 1:
            return []

        spiral = get_spiral_order(rows, cols)
        processed: set[tuple[int, int]] = set()
        all_dets: list[dict[str, Any]] = []

        subframes_processed = 0
        for r, c in spiral:
            if subframes_processed >= self.params.max_subframes:
                break
            tile = extract_subframe(cropped, r, c, size)
            for x1, y1, x2, y2, conf, cls_id in self._expand_tile_preds(tile, r, c, size):
                cropped_bbox = convert_to_cropped_coords([x1, y1, x2, y2], r, c, size)
                full_bbox = to_full_frame(cropped_bbox, top_off, left_off)
                all_dets.append(
                    {
                        "bbox": full_bbox,
                        "sub_bbox": [x1, y1, x2, y2],
                        "confidence": conf,
                        "class_id": cls_id,
                        "sub_r": r,
                        "sub_c": c,
                    }
                )
            processed.add((r, c))
            subframes_processed += 1

        for det in list(all_dets):
            sub_bbox = det["sub_bbox"]
            if not is_on_edge(sub_bbox, size, self.params.edge_margin):
                continue
            if compute_area(sub_bbox) >= self.params.max_target_cover_area:
                continue
            bbox = det["bbox"]
            cx = (bbox[0] + bbox[2]) / 2.0 - top_off
            cy = (bbox[1] + bbox[3]) / 2.0 - top_off
            nr, nc = get_closest_subframe(cx, cy, rows, cols, size)
            if (nr, nc) in processed:
                continue
            tile = extract_subframe(cropped, nr, nc, size)
            for x1, y1, x2, y2, conf, cls_id in self._expand_tile_preds(tile, nr, nc, size):
                cropped_bbox = convert_to_cropped_coords([x1, y1, x2, y2], nr, nc, size)
                full_bbox = to_full_frame(cropped_bbox, top_off, left_off)
                all_dets.append(
                    {
                        "bbox": full_bbox,
                        "sub_bbox": [x1, y1, x2, y2],
                        "confidence": conf,
                        "class_id": cls_id,
                        "sub_r": nr,
                        "sub_c": nc,
                    }
                )
            processed.add((nr, nc))

        final = nms_detections(
            all_dets,
            self.params.nms_threshold,
            self.params.confidence_threshold,
        )
        return [self._det_to_hit(d, frame.shape[1], frame.shape[0]) for d in final]

    def _expand_tile_preds(
        self,
        tile: np.ndarray,
        r: int,
        c: int,
        size: int,
    ) -> list[tuple[float, float, float, float, float, int]]:
        del r, c
        if tile.shape[0] != size or tile.shape[1] != size:
            tile = cv2.resize(tile, (size, size), interpolation=cv2.INTER_AREA)
        preds = self._predict_tile(tile)
        return [(b[0], b[1], b[2], b[3], conf, cls_id) for b, conf, cls_id in preds]

    @staticmethod
    def _det_to_hit(det: dict[str, Any], frame_w: int, frame_h: int) -> TargetHit:
        x1, y1, x2, y2 = det["bbox"]
        x1i = int(max(0, min(frame_w - 1, x1)))
        y1i = int(max(0, min(frame_h - 1, y1)))
        x2i = int(max(0, min(frame_w, x2)))
        y2i = int(max(0, min(frame_h, y2)))
        bw = max(x2i - x1i, 1)
        bh = max(y2i - y1i, 1)
        conf = float(det["confidence"])
        return TargetHit(
            cx=int(x1i + bw / 2),
            cy=int(y1i + bh / 2),
            area=int(bw * bh),
            bbox=(x1i, y1i, x2i, y2i),
            confidence=conf,
        )


def detect_subframe_dry(frame: npt.NDArray[np.uint8], cfg: dict) -> list[TargetHit]:
    """Deprecated: use create_target_detector(cfg).detect(frame).dry instead."""
    return SubframeYoloDetector(cfg).detect_dry(frame)
