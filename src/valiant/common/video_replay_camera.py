"""Replay prerecorded video as a camera source for SITL / bench."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from valiant.common.config import repo_root


class VideoReplayCamera:
    """OpenCV video file replay with optional loop and synthetic depth."""

    def __init__(
        self,
        video_path: str | Path,
        *,
        loop: bool = True,
        synthetic_depth_m: float | None = None,
    ):
        path = Path(video_path)
        if not path.is_file():
            path = repo_root() / video_path
        if not path.is_file():
            raise FileNotFoundError(f"Video not found: {video_path}")
        self._path = path
        self._loop = loop
        self._synthetic_depth_m = synthetic_depth_m
        self._cap = cv2.VideoCapture(str(path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open video: {path}")
        self._last_depth_mm: np.ndarray | None = None
        if synthetic_depth_m is not None:
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
            mm = int(synthetic_depth_m * 1000)
            self._last_depth_mm = np.full((h, w), mm, dtype=np.uint16)
        print(f"[Camera] Video replay: {path} loop={loop}")

    @classmethod
    def from_config(cls, cfg: dict) -> VideoReplayCamera:
        cam = cfg.get("camera", {})
        video = cam.get("video_path", "")
        if not video:
            raise ValueError("camera.video_path required for source=video")
        return cls(
            video,
            loop=bool(cam.get("video_loop", True)),
            synthetic_depth_m=cam.get("synthetic_depth_m"),
        )

    def get_frame(self) -> np.ndarray | None:
        ret, frame = self._cap.read()
        if not ret:
            if not self._loop:
                return None
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
            if not ret:
                return None
        return frame

    @property
    def depth_mm(self) -> np.ndarray | None:
        return self._last_depth_mm

    @property
    def depth_ok(self) -> bool:
        return self._last_depth_mm is not None

    def cleanup(self) -> None:
        self._cap.release()
