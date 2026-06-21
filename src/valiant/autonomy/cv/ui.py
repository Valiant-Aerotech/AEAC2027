"""Debug UI overlay for CV and orchestrator state."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import cv2
import numpy as np

from valiant.autonomy.cv.constants import CAPTURE_HEIGHT, CAPTURE_WIDTH, R_S, SUBFRAME_SIZE
from valiant.autonomy.cv.subframe_grid import grid_crop_bounds
from valiant.autonomy.cv.sitl_hud import (
    C_GREEN,
    C_MAGENTA,
    C_MUTED,
    C_TEXT,
    draw_corner_brackets,
    draw_panel,
    draw_target_marker,
    state_color,
    vignette,
)
from valiant.autonomy.packets import CVPacket, MetricPacket

if TYPE_CHECKING:
    import numpy.typing as npt


def _draw_velocity_arrow(
    overlay: npt.NDArray[np.uint8],
    origin: tuple[int, int],
    vel_body: tuple[float, float, float],
    *,
    scale: float,
    color: tuple[int, int, int],
    label: str,
) -> None:
    vx, vy, _vz = vel_body
    mag = math.hypot(vx, vy)
    if mag < 0.03:
        return
    ox, oy = origin
    end_x = int(ox + vy * scale)
    end_y = int(oy - vx * scale)
    cv2.arrowedLine(overlay, (ox, oy), (end_x, end_y), color, 2, tipLength=0.25, line_type=cv2.LINE_AA)
    cv2.putText(overlay, label, (ox + 8, oy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def _draw_reticle(overlay: np.ndarray, cx: int, cy: int, size: int = 28) -> None:
    cv2.circle(overlay, (cx, cy), size, (70, 78, 92), 1, cv2.LINE_AA)
    cv2.line(overlay, (cx - size - 6, cy), (cx - 8, cy), C_MUTED, 1, cv2.LINE_AA)
    cv2.line(overlay, (cx + 8, cy), (cx + size + 6, cy), C_MUTED, 1, cv2.LINE_AA)
    cv2.line(overlay, (cx, cy - size - 6), (cx, cy - 8), C_MUTED, 1, cv2.LINE_AA)
    cv2.line(overlay, (cx, cy + 8), (cx, cy + size + 6), C_MUTED, 1, cv2.LINE_AA)
    cv2.drawMarker(overlay, (cx, cy), (200, 208, 220), cv2.MARKER_CROSS, 10, 1)


def draw_overlay(
    frame: npt.NDArray[np.uint8],
    packet: CVPacket | None,
    state: str,
    *,
    metric: MetricPacket | None = None,
    show_yolo_crop: bool = False,
    inference_mode: str = "subframe",
    subframe_size: int = SUBFRAME_SIZE,
    vel_cmd_body: tuple[float, float, float] | None = None,
    vel_actual_body: tuple[float, float, float] | None = None,
    compact_hud: bool = False,
) -> npt.NDArray[np.uint8]:
    """Draw detection boxes, crosshair, and state on a copy of the frame."""
    overlay = frame.copy()
    h, w = overlay.shape[:2]

    if overlay.mean() < 20:
        for i in range(0, w, 48):
            cv2.line(overlay, (i, 0), (i, h), (28, 30, 36), 1)
        for j in range(0, h, 48):
            cv2.line(overlay, (0, j), (w, j), (28, 30, 36), 1)

    panel_top = 8
    if not compact_hud:
        sc = state_color(state)
        draw_panel(overlay, 8, 8, min(280, w - 16), 58, alpha=0.78)
        cv2.putText(overlay, state, (18, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.85, sc, 2, cv2.LINE_AA)
        cv2.putText(overlay, "MISSION VIEW", (18, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.38, C_MUTED, 1, cv2.LINE_AA)
        panel_top = 72

    if packet:
        method_label = f"{packet.method}   dry {len(packet.dry)}   shot {len(packet.shot)}"
        draw_panel(overlay, 8, panel_top, min(240, w - 16), 24, alpha=0.65)
        cv2.putText(
            overlay, method_label, (16, panel_top + 18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, C_TEXT, 1, cv2.LINE_AA,
        )

        for hit in packet.dry:
            x1, y1, x2, y2 = hit.bbox
            cv2.rectangle(overlay, (x1, y1), (x2, y2), C_MAGENTA, 2, cv2.LINE_AA)
            draw_target_marker(overlay, hit.cx, hit.cy, C_MAGENTA, label=f"{hit.area}px")

        for hit in packet.shot:
            x1, y1, x2, y2 = hit.bbox
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (80, 160, 255), 2, cv2.LINE_AA)

    if show_yolo_crop:
        if inference_mode == "center_crop":
            scale_x = w / CAPTURE_WIDTH
            scale_y = h / CAPTURE_HEIGHT
            crop_w = max(1, int(R_S * scale_x))
            crop_h = max(1, int(R_S * scale_y))
            start_x = max(0, (w - crop_w) // 2)
            start_y = max(0, (h - crop_h) // 2)
            cv2.rectangle(overlay, (start_x, start_y), (start_x + crop_w, start_y + crop_h), (80, 120, 255), 1)
        else:
            left, top, right, bottom = grid_crop_bounds(w, h, subframe_size)
            cv2.rectangle(overlay, (left, top), (right, bottom), (80, 120, 255), 1)
            rows = (bottom - top) // subframe_size
            cols = (right - left) // subframe_size
            for r in range(1, rows):
                y = top + r * subframe_size
                cv2.line(overlay, (left, y), (right, y), (60, 90, 140), 1)
            for c in range(1, cols):
                x = left + c * subframe_size
                cv2.line(overlay, (x, top), (x, bottom), (60, 90, 140), 1)

    _draw_reticle(overlay, w // 2, h // 2)

    if metric:
        dist_txt = f"{metric.distance_m:.2f} m" if metric.distance_m is not None else "?"
        horiz = metric.horizontal_range_m
        alt_err = metric.altitude_error_m
        side_txt = f"{metric.side_clearance_m:.2f} m" if metric.side_clearance_m is not None else "?"
        extra = horiz is not None or alt_err is not None
        panel_h = 44 if extra else 28
        base_y = h - panel_h - 8
        draw_panel(overlay, 8, base_y, min(420, w - 16), panel_h, alpha=0.75)
        cv2.putText(
            overlay, f"range {dist_txt}   clearance {side_txt}", (16, base_y + 18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, C_GREEN, 1, cv2.LINE_AA,
        )
        if extra:
            h_txt = f"{horiz:.2f}" if horiz is not None else "?"
            a_txt = f"{alt_err:+.2f}" if alt_err is not None else "?"
            cv2.putText(
                overlay, f"horiz {h_txt} m   alt err {a_txt} m", (16, base_y + 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, C_GREEN, 1, cv2.LINE_AA,
            )

    arrow_origin = (w // 2, h - 56)
    if vel_cmd_body is not None:
        _draw_velocity_arrow(overlay, arrow_origin, vel_cmd_body, scale=70.0, color=C_GREEN, label="cmd")
    if vel_actual_body is not None:
        _draw_velocity_arrow(
            overlay, (arrow_origin[0] - 14, arrow_origin[1] + 14),
            vel_actual_body, scale=70.0, color=(80, 180, 255), label="sim",
        )

    draw_corner_brackets(overlay)
    vignette(overlay, 0.22)
    return overlay
