"""Debug UI overlay for CV and orchestrator state."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import cv2

from valiant.autonomy.packets import CVPacket, MetricPacket

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

CAPTURE_WIDTH = 1280
CAPTURE_HEIGHT = 720
R_S = 224


def _draw_velocity_arrow(
    overlay: npt.NDArray[np.uint8],
    origin: tuple[int, int],
    vel_body: tuple[float, float, float],
    *,
    scale: float,
    color: tuple[int, int, int],
    label: str,
) -> None:
    """Body frame: x=forward, y=right, z=down — arrow on image (forward = up)."""
    vx, vy, _vz = vel_body
    mag = math.hypot(vx, vy)
    if mag < 0.03:
        return
    ox, oy = origin
    # Forward motion draws arrow upward; right motion draws to the right.
    end_x = int(ox + vy * scale)
    end_y = int(oy - vx * scale)
    cv2.arrowedLine(overlay, (ox, oy), (end_x, end_y), color, 2, tipLength=0.25)
    cv2.putText(
        overlay,
        label,
        (ox + 8, oy - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
    )


def draw_overlay(
    frame: npt.NDArray[np.uint8],
    packet: CVPacket | None,
    state: str,
    *,
    metric: MetricPacket | None = None,
    show_yolo_crop: bool = False,
    vel_cmd_body: tuple[float, float, float] | None = None,
    vel_actual_body: tuple[float, float, float] | None = None,
) -> npt.NDArray[np.uint8]:
    """Draw detection boxes, crosshair, and state on a copy of the frame."""
    overlay = frame.copy()
    h, w = overlay.shape[:2]

    cv2.putText(
        overlay,
        f"STATE: {state}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        2,
    )

    if packet:
        method_label = f"CV: {packet.method}  dry={len(packet.dry)} shot={len(packet.shot)}"
        cv2.putText(
            overlay,
            method_label,
            (10, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1,
        )

        for hit in packet.dry:
            x1, y1, x2, y2 = hit.bbox
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 0, 255), 2)
            cv2.circle(overlay, (hit.cx, hit.cy), 6, (255, 0, 255), -1)
            cv2.putText(
                overlay,
                f"dry {hit.area}px",
                (x1, max(y1 - 8, 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 255),
                1,
            )

        for hit in packet.shot:
            x1, y1, x2, y2 = hit.bbox
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 128, 0), 2)
            cv2.circle(overlay, (hit.cx, hit.cy), 6, (255, 128, 0), -1)
            cv2.putText(
                overlay,
                f"shot {hit.area}px",
                (x1, max(y1 - 8, 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 128, 0),
                1,
            )

    if show_yolo_crop:
        scale_x = w / CAPTURE_WIDTH
        scale_y = h / CAPTURE_HEIGHT
        crop_w = max(1, int(R_S * scale_x))
        crop_h = max(1, int(R_S * scale_y))
        start_x = max(0, (w - crop_w) // 2)
        start_y = max(0, (h - crop_h) // 2)
        cv2.rectangle(
            overlay,
            (start_x, start_y),
            (start_x + crop_w, start_y + crop_h),
            (255, 0, 0),
            1,
        )

    if metric:
        dist_txt = f"{metric.distance_m:.2f}m" if metric.distance_m is not None else "dist=?"
        side_txt = (
            f"{metric.side_clearance_m:.2f}m"
            if metric.side_clearance_m is not None
            else "side=?"
        )
        cv2.putText(
            overlay,
            f"metric: {dist_txt}  side: {side_txt}",
            (10, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 220, 0),
            1,
        )

    cv2.line(overlay, (w // 2 - 20, h // 2), (w // 2 + 20, h // 2), (128, 128, 128), 1)
    cv2.line(overlay, (w // 2, h // 2 - 20), (w // 2, h // 2 + 20), (128, 128, 128), 1)

    arrow_origin = (w // 2, h - 50)
    if vel_cmd_body is not None:
        _draw_velocity_arrow(
            overlay,
            arrow_origin,
            vel_cmd_body,
            scale=70.0,
            color=(0, 255, 120),
            label="cmd",
        )
    if vel_actual_body is not None:
        _draw_velocity_arrow(
            overlay,
            (arrow_origin[0] - 12, arrow_origin[1] + 12),
            vel_actual_body,
            scale=70.0,
            color=(255, 180, 0),
            label="sim",
        )

    return overlay
