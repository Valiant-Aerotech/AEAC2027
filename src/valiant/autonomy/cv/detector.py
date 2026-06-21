"""Target detector - composes dry + shot backends, outputs CVPacket."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from valiant.autonomy.cv.constants import CONF_THRESH
from valiant.autonomy.cv.dry_detector import create_yolo_dry_backend, inference_mode
from valiant.autonomy.cv.exceptions import BadFrameError, LowConfidenceError
from valiant.autonomy.cv.hsv import detect_hsv
from valiant.autonomy.cv.model_paths import resolve_dry_model_path
from valiant.autonomy.cv.shot_detector import ShotDetector
from valiant.autonomy.packets import CVPacket

if TYPE_CHECKING:
    import numpy.typing as npt


class TargetDetector:
    """Unified detector: yolo (dry) + hsv shot, or hsv-only, or both."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.method = cfg.get("cv", {}).get("method", "hsv").lower()
        self.inference_mode = inference_mode(cfg)
        self._yolo_dry = create_yolo_dry_backend(cfg) if self.method in ("yolo", "both") else None
        self._shot = ShotDetector(cfg) if self.method in ("yolo", "both") else None
        self._frame_id = 0
        self.min_confidence = cfg.get("cv", {}).get("confidence_threshold", CONF_THRESH)
        print(f"[CV] TargetDetector method={self.method} inference={self.inference_mode}")

    def _append_yolo_dry(self, packet: CVPacket, frame: npt.NDArray[np.uint8]) -> None:
        if self._yolo_dry is None:
            return
        hits = self._yolo_dry.detect_dry(frame)
        if not hits:
            return
        best_conf = max(h.confidence for h in hits)
        if best_conf < self.min_confidence:
            raise LowConfidenceError(
                f"YOLO confidence {best_conf:.2f} below {self.min_confidence}"
            )
        for hit in hits:
            if hit.confidence >= self.min_confidence:
                packet.dry.append(hit)
        packet.debug = {"dry_backend": self._yolo_dry.dry_backend_name}

    def _append_shot(self, packet: CVPacket, frame: npt.NDArray[np.uint8]) -> None:
        if self._shot is None:
            return
        shot_hit = self._shot.detect(frame, self.min_confidence)
        if shot_hit is not None:
            packet.shot.append(shot_hit)

    def detect(self, frame: npt.NDArray[np.uint8] | None) -> CVPacket:
        if frame is None or frame.size == 0:
            raise BadFrameError("Frame is None or empty")

        self._frame_id += 1
        packet = CVPacket(frame_id=self._frame_id, method=self.method)

        if self.method == "hsv":
            dry_hit, shot_hit = detect_hsv(frame, self.cfg)
            if dry_hit:
                packet.dry.append(dry_hit)
            if shot_hit:
                packet.shot.append(shot_hit)
            return packet

        if self.method in ("yolo", "both"):
            self._append_shot(packet, frame)

            if self.method == "yolo":
                if self._yolo_dry is not None and resolve_dry_model_path(self.cfg):
                    self._append_yolo_dry(packet, frame)
                else:
                    print("[CV] WARNING: yolo method set but no model in models/ - falling back to HSV dry")
                    dry_hit, _ = detect_hsv(frame, self.cfg)
                    packet.method = "hsv_fallback"
                    if dry_hit:
                        packet.dry.append(dry_hit)
                return packet

        if self._yolo_dry is not None and resolve_dry_model_path(self.cfg):
            self._append_yolo_dry(packet, frame)
        if not packet.dry:
            dry_hit, shot_hit = detect_hsv(frame, self.cfg)
            if dry_hit:
                packet.dry.append(dry_hit)
            if shot_hit and not packet.shot:
                packet.shot.append(shot_hit)
        return packet
