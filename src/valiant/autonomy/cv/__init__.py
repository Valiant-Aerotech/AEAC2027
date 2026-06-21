"""Computer vision: dry/shot target detection and CVPacket export."""

from valiant.autonomy.cv.api import (
    TargetDetector,
    create_target_detector,
    crop_preview_for_display,
    draw_mission_overlay,
    hits_to_bench_dict,
    render_sitl_dashboard,
    resolve_dry_model_path,
)

__all__ = [
    "TargetDetector",
    "create_target_detector",
    "crop_preview_for_display",
    "draw_mission_overlay",
    "hits_to_bench_dict",
    "render_sitl_dashboard",
    "resolve_dry_model_path",
]
