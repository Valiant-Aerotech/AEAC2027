"""Sample depth at RGB pixel coordinates from a depth frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


def sample_depth_m(
    depth_mm: npt.NDArray[np.uint16],
    cx: int,
    cy: int,
    *,
    patch_radius: int = 5,
) -> float | None:
    """Median depth in a square patch around (cx, cy), returned in metres."""
    if depth_mm is None or depth_mm.size == 0:
        return None
    h, w = depth_mm.shape[:2]
    cx = int(np.clip(cx, 0, w - 1))
    cy = int(np.clip(cy, 0, h - 1))
    r = max(patch_radius, 1)
    y0, y1 = max(0, cy - r), min(h, cy + r + 1)
    x0, x1 = max(0, cx - r), min(w, cx + r + 1)
    patch = depth_mm[y0:y1, x0:x1]
    valid = patch[(patch > 0) & (patch < 60000)]
    if valid.size == 0:
        return None
    return float(np.median(valid)) / 1000.0
