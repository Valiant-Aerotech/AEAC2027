"""Depth frame providers for depth_at_target metric recon."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class DepthSource(Protocol):
    """Provides a depth frame aligned (via calibration) to the RGB frame."""

    def get_depth_mm(self) -> np.ndarray | None:
        """Return uint16 depth in millimeters, or None if unavailable."""

    def stop(self) -> None:
        """Release resources."""


class NullDepthSource:
    """No depth available (FOV-only fallback)."""

    def get_depth_mm(self) -> np.ndarray | None:
        return None

    def stop(self) -> None:
        pass


class InlineDepthSource:
    """Depth supplied by the camera driver each frame."""

    def __init__(self) -> None:
        self._depth_mm: np.ndarray | None = None

    def set_frame(self, depth_mm: np.ndarray | None) -> None:
        self._depth_mm = depth_mm

    def get_depth_mm(self) -> np.ndarray | None:
        return self._depth_mm

    def stop(self) -> None:
        self._depth_mm = None


class RecordingDepthSource:
    """Replay depth frames from Pi calibration/mission recordings."""

    def __init__(self, recording_dir: str | Path):
        self.recording_dir = Path(recording_dir)
        self._index_path = self.recording_dir / "index.json"
        self._entries: list[dict[str, Any]] = []
        self._cursor = 0
        if self._index_path.is_file():
            with open(self._index_path, encoding="utf-8") as f:
                data = json.load(f)
            self._entries = data.get("frames", data if isinstance(data, list) else [])

    def get_depth_mm(self) -> np.ndarray | None:
        if not self._entries:
            return None
        entry = self._entries[self._cursor % len(self._entries)]
        self._cursor += 1
        depth_path = self.recording_dir / entry["depth_file"]
        if not depth_path.is_file():
            return None
        depth = np.load(str(depth_path))
        if depth.dtype != np.uint16:
            depth = depth.astype(np.uint16)
        return depth

    def stop(self) -> None:
        pass
