"""Corner-target heuristic for wall-edge detections (legacy wrapper)."""

from __future__ import annotations

from valiant.autonomy.metric_recon.edge_proximity import classify_edges
from valiant.autonomy.packets import TargetHit


def is_corner_target(
    hit: TargetHit,
    frame_w: int,
    frame_h: int,
    cfg: dict,
) -> bool:
    """True when bbox center is near the left/right image edge."""
    return classify_edges(hit, frame_w, frame_h, cfg).lateral