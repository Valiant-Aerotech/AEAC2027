"""Scripted target positions for SITL nav tests without CV."""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

from valiant.autonomy.packets import CVPacket, TargetHit
from valiant.common.config import repo_root


class SyntheticTargetCamera:
    """Blank frames + injected TargetHit from JSON scenario timeline."""

    def __init__(
        self,
        scenario_path: str | Path,
        *,
        width: int = 640,
        height: int = 480,
        synthetic_depth_m: float | None = 3.0,
    ):
        path = Path(scenario_path)
        if not path.is_file():
            path = repo_root() / scenario_path
        if not path.is_file():
            raise FileNotFoundError(f"Scenario not found: {scenario_path}")
        with open(path, encoding="utf-8") as f:
            self._keyframes = json.load(f)
        if not self._keyframes:
            raise ValueError("Scenario JSON is empty")
        self.width = width
        self.height = height
        self._start = time.time()
        self._last_cv: CVPacket | None = None
        self._last_depth_mm: np.ndarray | None = None
        if synthetic_depth_m is not None:
            mm = int(synthetic_depth_m * 1000)
            self._last_depth_mm = np.full((height, width), mm, dtype=np.uint16)
        print(f"[Camera] Synthetic scenario: {path} ({len(self._keyframes)} keyframes)")

    @classmethod
    def from_config(cls, cfg: dict) -> SyntheticTargetCamera:
        cam = cfg.get("camera", {})
        scenario = cam.get("synthetic_scenario", "tests/fixtures/sitl_approach.json")
        return cls(
            scenario,
            width=int(cam.get("width", 640)),
            height=int(cam.get("height", 480)),
            synthetic_depth_m=cam.get("synthetic_depth_m", 3.0),
        )

    def _sample_keyframe(self) -> dict:
        elapsed = time.time() - self._start
        kf = self._keyframes[0]
        for frame in self._keyframes:
            if float(frame.get("t", 0)) <= elapsed:
                kf = frame
            else:
                break
        return kf

    def get_synthetic_cv_packet(self) -> CVPacket | None:
        return self._last_cv

    def get_frame(self) -> np.ndarray | None:
        kf = self._sample_keyframe()
        cx = int(kf.get("cx", self.width // 2))
        cy = int(kf.get("cy", self.height // 2))
        bbox_w = int(kf.get("bbox_w", 80))
        bbox_h = int(kf.get("bbox_h", bbox_w))
        x1 = max(0, cx - bbox_w // 2)
        y1 = max(0, cy - bbox_h // 2)
        x2 = min(self.width, cx + bbox_w // 2)
        y2 = min(self.height, cy + bbox_h // 2)
        area = max((x2 - x1) * (y2 - y1), 1)

        depth_m = kf.get("depth_m")
        if depth_m is not None:
            mm = int(float(depth_m) * 1000)
            self._last_depth_mm = np.full((self.height, self.width), mm, dtype=np.uint16)

        hit = TargetHit(cx=cx, cy=cy, area=area, bbox=(x1, y1, x2, y2), confidence=1.0)
        self._last_cv = CVPacket(dry=[hit], method="synthetic")

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.circle(frame, (cx, cy), max(bbox_w // 2, 10), (180, 50, 180), -1)
        return frame

    @property
    def depth_mm(self) -> np.ndarray | None:
        return self._last_depth_mm

    @property
    def depth_ok(self) -> bool:
        return self._last_depth_mm is not None

    def cleanup(self) -> None:
        pass
