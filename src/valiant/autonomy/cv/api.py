"""Public CV subsystem API (orchestrator, bench, and tools import from here)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from valiant.autonomy.cv.detector import TargetDetector
from valiant.autonomy.cv.model_paths import resolve_dry_model_path
from valiant.autonomy.cv.subframe_grid import DEFAULT_SUBFRAME_SIZE, crop_to_grid
from valiant.autonomy.cv.ui import draw_overlay
from valiant.autonomy.packets import CVPacket, MetricPacket, TargetHit

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


def create_target_detector(cfg: dict) -> TargetDetector:
    """Factory for the production CV detector."""
    return TargetDetector(cfg)


def hits_to_bench_dict(hits: list[TargetHit]) -> list[dict[str, Any]]:
    """Convert TargetHit list to bench dict format (full sensor frame coords)."""
    return [
        {
            "bbox": list(hit.bbox),
            "confidence": hit.confidence,
            "class_id": 0,
            "cx": hit.cx,
            "cy": hit.cy,
            "area": hit.area,
        }
        for hit in hits
    ]


def crop_preview_for_display(frame: npt.NDArray[np.uint8], cfg: dict) -> np.ndarray:
    """Center-crop frame to subframe grid multiples (display-only helper)."""
    size = int(cfg.get("cv", {}).get("subframe_size", DEFAULT_SUBFRAME_SIZE))
    cropped, _, _ = crop_to_grid(frame, size)
    return cropped


def draw_mission_overlay(
    frame: npt.NDArray[np.uint8],
    packet: CVPacket | None,
    state: str,
    cfg: dict,
    *,
    metric: MetricPacket | None = None,
    vel_cmd_body: tuple[float, float, float] | None = None,
    vel_actual_body: tuple[float, float, float] | None = None,
    compact_hud: bool = False,
) -> npt.NDArray[np.uint8]:
    """Draw mission HUD; reads cv method and inference settings from cfg internally."""
    cv_cfg = cfg.get("cv", {})
    method = cv_cfg.get("method", "hsv")
    return draw_overlay(
        frame,
        packet,
        state,
        metric=metric,
        show_yolo_crop=method in ("yolo", "both"),
        inference_mode=cv_cfg.get("inference_mode", "subframe"),
        subframe_size=int(cv_cfg.get("subframe_size", DEFAULT_SUBFRAME_SIZE)),
        vel_cmd_body=vel_cmd_body,
        vel_actual_body=vel_actual_body,
        compact_hud=compact_hud,
    )


__all__ = [
    "TargetDetector",
    "create_target_detector",
    "crop_preview_for_display",
    "draw_mission_overlay",
    "hits_to_bench_dict",
    "resolve_dry_model_path",
]
