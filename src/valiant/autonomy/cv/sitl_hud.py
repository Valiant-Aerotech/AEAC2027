"""Shared HUD drawing primitives for SITL visualization windows."""

from __future__ import annotations

import cv2
import numpy as np


# BGR palette
C_BG = (18, 20, 26)
C_PANEL = (28, 32, 42)
C_BORDER = (55, 62, 78)
C_TEXT = (220, 224, 232)
C_MUTED = (130, 138, 155)
C_ACCENT = (255, 196, 64)
C_CYAN = (255, 210, 80)
C_GREEN = (100, 220, 140)
C_MAGENTA = (220, 90, 200)
C_WALL = (255, 170, 90)

STATE_COLORS = {
    "SEARCHING": (255, 170, 60),
    "REPOSITION": (160, 200, 255),
    "APPROACHING": (80, 200, 255),
    "AIMING": (100, 230, 150),
    "FIRING": (80, 120, 255),
    "CAPTURING": (200, 160, 255),
    "COMPLETE": (120, 255, 180),
    "ABORTED": (80, 80, 220),
}


def state_color(state: str) -> tuple[int, int, int]:
    return STATE_COLORS.get(state, C_ACCENT)


def draw_panel(
    img: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    alpha: float = 0.72,
    border: bool = True,
) -> None:
    roi = img[y : y + h, x : x + w]
    if roi.size == 0:
        return
    overlay = roi.copy()
    overlay[:] = C_PANEL
    cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0, roi)
    if border:
        cv2.rectangle(img, (x, y), (x + w, y + h), C_BORDER, 1, cv2.LINE_AA)


def draw_title_bar(img: np.ndarray, title: str, subtitle: str = "", *, compact: bool = False) -> None:
    h, w = img.shape[:2]
    bar_h = 22 if compact else (36 if subtitle else 28)
    draw_panel(img, 0, 0, w, bar_h, alpha=0.82)
    font = 0.42 if compact else 0.55
    cv2.putText(img, title, (8, 15 if compact else 20), cv2.FONT_HERSHEY_SIMPLEX, font, C_TEXT, 1, cv2.LINE_AA)
    if subtitle and not compact:
        cv2.putText(img, subtitle, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.38, C_MUTED, 1, cv2.LINE_AA)


def draw_footer(img: np.ndarray, text: str, *, right: str = "", compact: bool = False) -> None:
    h, w = img.shape[:2]
    fh = 20 if compact else 26
    draw_panel(img, 0, h - fh, w, fh, alpha=0.78)
    cv2.putText(
        img, text, (8, h - 6 if compact else h - 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.36 if compact else 0.42, C_CYAN, 1, cv2.LINE_AA,
    )
    if right:
        tw = cv2.getTextSize(right, cv2.FONT_HERSHEY_SIMPLEX, 0.34 if compact else 0.38, 1)[0][0]
        cv2.putText(
            img, right, (w - tw - 6, h - 6 if compact else h - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.34 if compact else 0.38, C_MUTED, 1, cv2.LINE_AA,
        )


def draw_corner_brackets(img: np.ndarray, margin: int = 8, length: int = 18, color=C_BORDER) -> None:
    h, w = img.shape[:2]
    pts = [
        ((margin, margin), (margin + length, margin), (margin, margin + length)),
        ((w - margin, margin), (w - margin - length, margin), (w - margin, margin + length)),
        ((margin, h - margin), (margin + length, h - margin), (margin, h - margin - length)),
        ((w - margin, h - margin), (w - margin - length, h - margin), (w - margin, h - margin - length)),
    ]
    for a, b, c in pts:
        cv2.line(img, a, b, color, 1, cv2.LINE_AA)
        cv2.line(img, a, c, color, 1, cv2.LINE_AA)


def draw_compass(img: np.ndarray, cx: int, cy: int, radius: int = 22) -> None:
    cv2.circle(img, (cx, cy), radius, C_BORDER, 1, cv2.LINE_AA)
    cv2.putText(img, "N", (cx - 5, cy - radius + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, C_TEXT, 1, cv2.LINE_AA)
    cv2.line(img, (cx, cy - radius + 14), (cx, cy - 4), C_TEXT, 1, cv2.LINE_AA)
    cv2.line(img, (cx + radius - 6, cy), (cx + 4, cy), C_MUTED, 1, cv2.LINE_AA)
    cv2.putText(img, "E", (cx + radius - 10, cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.32, C_MUTED, 1, cv2.LINE_AA)


def draw_scale_bar(img: np.ndarray, x: int, y: int, meters: float, px_per_m: float) -> None:
    bar_px = max(int(meters * px_per_m), 20)
    cv2.line(img, (x, y), (x + bar_px, y), C_TEXT, 2, cv2.LINE_AA)
    cv2.line(img, (x, y - 3), (x, y + 3), C_TEXT, 1, cv2.LINE_AA)
    cv2.line(img, (x + bar_px, y - 3), (x + bar_px, y + 3), C_TEXT, 1, cv2.LINE_AA)
    label = f"{meters:.0f} m" if meters >= 1 else f"{meters:.1f} m"
    cv2.putText(img, label, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, C_MUTED, 1, cv2.LINE_AA)


def draw_drone_icon(img: np.ndarray, cx: int, cy: int, yaw_rad: float, *, scale: float = 1.0) -> None:
    import math

    r = int(12 * scale)
    cv2.circle(img, (cx, cy), r, (20, 24, 30), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), r, C_CYAN, 2, cv2.LINE_AA)
    for arm in range(4):
        ang = yaw_rad + arm * math.pi / 2
        ax = int(cx + (r + 6) * math.sin(ang))
        ay = int(cy - (r + 6) * math.cos(ang))
        cv2.line(img, (cx, cy), (ax, ay), (90, 100, 115), 2, cv2.LINE_AA)
        cv2.circle(img, (ax, ay), 4, C_MAGENTA, -1, cv2.LINE_AA)
    nose = int(r + 10)
    nx = int(cx + nose * math.sin(yaw_rad))
    ny = int(cy - nose * math.cos(yaw_rad))
    cv2.arrowedLine(img, (cx, cy), (nx, ny), C_GREEN, 2, tipLength=0.35, line_type=cv2.LINE_AA)


def draw_target_marker(img: np.ndarray, x: int, y: int, color: tuple[int, int, int], *, label: str = "") -> None:
    cv2.circle(img, (x, y), 10, color, 2, cv2.LINE_AA)
    cv2.circle(img, (x, y), 3, color, -1, cv2.LINE_AA)
    cv2.drawMarker(img, (x, y), (255, 255, 255), cv2.MARKER_CROSS, 12, 1)
    if label:
        cv2.putText(img, label, (x + 12, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)


def vignette(img: np.ndarray, strength: float = 0.35) -> None:
    h, w = img.shape[:2]
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    mask = ((x - cx) ** 2 / (cx**2) + (y - cy) ** 2 / (cy**2))
    mask = np.clip(mask, 0, 1)
    darken = (1.0 - strength * mask)[..., np.newaxis]
    img[:] = np.clip(img.astype(np.float32) * darken, 0, 255).astype(np.uint8)
