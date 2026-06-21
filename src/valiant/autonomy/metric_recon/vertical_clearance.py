"""Optional ToF vertical clearance beside an edge-proximity target."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from valiant.autonomy.metric_recon.depth_map import sample_depth_at_bbox, sample_depth_m
from valiant.autonomy.packets import EdgeProximity, TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt


def sample_vertical_clearance_m(
    depth_mm: npt.NDArray[np.uint16],
    hit: TargetHit,
    frame_h: int,
    edges: EdgeProximity,
    cfg: dict,
    *,
    calib: dict[str, Any] | None = None,
) -> float | None:
    """
    Depth jump on the open vertical side of an edge target (optional enrichment).

    bottom edge -> sample above target; top edge -> sample below target.
    """
    if depth_mm is None or depth_mm.size == 0 or frame_h <= 0 or not edges.vertical:
        return None

    metric = cfg.get("metric_recon", {})
    offset_px = int(metric.get("vertical_sample_offset_px", metric.get("lateral_sample_offset_px", 48)))
    jump_min = float(metric.get("lateral_depth_jump_min_m", 0.15))

    center_y = frame_h // 2
    if edges.bottom:
        sample_y = max(0, hit.cy - offset_px)
    elif edges.top:
        sample_y = min(frame_h - 1, hit.cy + offset_px)
    else:
        return None

    target_depth = sample_depth_at_bbox(depth_mm, hit, calib=calib)
    if target_depth is None:
        target_depth = sample_depth_m(depth_mm, hit.cx, hit.cy, calib=calib)

    open_depth = sample_depth_m(depth_mm, hit.cx, sample_y, calib=calib)
    if target_depth is None or open_depth is None:
        return None
    if open_depth - target_depth >= jump_min:
        return open_depth - target_depth
    return None
