"""Optional ToF lateral clearance beside a corner target."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from valiant.autonomy.metric_recon.depth_map import sample_depth_at_bbox, sample_depth_m
from valiant.autonomy.packets import TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt


def sample_lateral_clearance_m(
    depth_mm: npt.NDArray[np.uint16],
    hit: TargetHit,
    frame_w: int,
    cfg: dict,
    *,
    calib: dict[str, Any] | None = None,
) -> float | None:
    """
    Depth jump on the open side of a corner target (optional enrichment).

    On a flat wall this often returns None; geometric body offset remains primary.
    """
    if depth_mm is None or depth_mm.size == 0 or frame_w <= 0:
        return None

    metric = cfg.get("metric_recon", {})
    offset_px = int(metric.get("lateral_sample_offset_px", 48))
    jump_min = float(metric.get("lateral_depth_jump_min_m", 0.15))

    center_x = frame_w // 2
    if hit.cx < center_x:
        sample_x = min(frame_w - 1, hit.cx + offset_px)
    else:
        sample_x = max(0, hit.cx - offset_px)

    target_depth = sample_depth_at_bbox(depth_mm, hit, calib=calib)
    if target_depth is None:
        target_depth = sample_depth_m(depth_mm, hit.cx, hit.cy, calib=calib)

    open_depth = sample_depth_m(depth_mm, sample_x, hit.cy, calib=calib)
    if target_depth is None or open_depth is None:
        return None
    if open_depth - target_depth >= jump_min:
        return open_depth - target_depth
    return None
