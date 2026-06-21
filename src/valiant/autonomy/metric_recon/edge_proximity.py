"""Image-edge proximity classification for clearance avoidance."""

from __future__ import annotations

from valiant.autonomy.packets import EdgeProximity, TargetHit


def _edge_frac(cfg: dict) -> float:
    metric = cfg.get("metric_recon", {})
    return float(metric.get("edge_edge_frac", metric.get("corner_edge_frac", 0.18)))


def _min_bbox_area(cfg: dict) -> int:
    metric = cfg.get("metric_recon", {})
    return int(metric.get("corner_min_bbox_area_px", 800))


def _near_edge(norm_offset: float, edge_frac: float) -> bool:
    return norm_offset > (1.0 - edge_frac)


def classify_edges(
    hit: TargetHit,
    frame_w: int,
    frame_h: int,
    cfg: dict,
) -> EdgeProximity:
    """Classify left/right/top/bottom edge proximity."""
    if hit.area < _min_bbox_area(cfg):
        return EdgeProximity()

    edge_frac = _edge_frac(cfg)
    left = right = top = bottom = False

    if frame_w > 0:
        half_w = frame_w / 2.0
        norm_x = abs(hit.cx - half_w) / half_w
        if _near_edge(norm_x, edge_frac):
            left = hit.cx < half_w
            right = not left

    if frame_h > 0:
        half_h = frame_h / 2.0
        norm_y = abs(hit.cy - half_h) / half_h
        if _near_edge(norm_y, edge_frac):
            top = hit.cy < half_h
            bottom = not top

    return EdgeProximity(left=left, right=right, top=top, bottom=bottom)
