"""HSV colour detection for purple (dry) and blue (shot) paper targets."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from valiant.autonomy.packets import TargetHit

if TYPE_CHECKING:
    import numpy.typing as npt


def _hsv_range_mask(hsv: npt.NDArray[np.uint8], h_min: int, h_max: int, s_min: int, v_min: int):
    """Build mask; handles hue wrap when h_min > h_max (red/purple edge)."""
    lower = np.array([h_min, s_min, v_min], dtype=np.uint8)
    upper = np.array([h_max, 255, 255], dtype=np.uint8)
    if h_min <= h_max:
        return cv2.inRange(hsv, lower, upper)
    mask1 = cv2.inRange(hsv, np.array([h_min, s_min, v_min]), np.array([179, 255, 255]))
    mask2 = cv2.inRange(hsv, np.array([0, s_min, v_min]), np.array([h_max, 255, 255]))
    return cv2.bitwise_or(mask1, mask2)


def _largest_contour_hit(
    mask: npt.NDArray[np.uint8],
    *,
    min_area: int,
    confidence: float = 1.0,
) -> TargetHit | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = min_area
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < best_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        best_area = area
        best = TargetHit(
            cx=int(x + w / 2),
            cy=int(y + h / 2),
            area=area,
            bbox=(x, y, x + w, y + h),
            confidence=confidence,
        )
    return best


def detect_hsv(
    frame: npt.NDArray[np.uint8],
    cfg: dict,
) -> tuple[TargetHit | None, TargetHit | None]:
    """Return (dry_hit, shot_hit) from HSV thresholds in config."""
    cv_cfg = cfg.get("cv", {})
    dry_cfg = cv_cfg.get("hsv_dry", {})
    shot_cfg = cv_cfg.get("hsv_shot", {})
    min_area = cv_cfg.get("hsv_min_area_px", 500)

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    dry_mask = _hsv_range_mask(
        hsv,
        dry_cfg.get("h_min", 130),
        dry_cfg.get("h_max", 170),
        dry_cfg.get("s_min", 50),
        dry_cfg.get("v_min", 50),
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dry_mask = cv2.morphologyEx(dry_mask, cv2.MORPH_OPEN, kernel)
    dry_mask = cv2.morphologyEx(dry_mask, cv2.MORPH_CLOSE, kernel)

    shot_mask = _hsv_range_mask(
        hsv,
        shot_cfg.get("h_min", 100),
        shot_cfg.get("h_max", 130),
        shot_cfg.get("s_min", 50),
        shot_cfg.get("v_min", 50),
    )
    shot_mask = cv2.morphologyEx(shot_mask, cv2.MORPH_OPEN, kernel)
    shot_mask = cv2.morphologyEx(shot_mask, cv2.MORPH_CLOSE, kernel)

    dry_hit = _largest_contour_hit(dry_mask, min_area=min_area)
    shot_hit = _largest_contour_hit(shot_mask, min_area=min_area)
    return dry_hit, shot_hit


def detect_hsv_shot(frame: npt.NDArray[np.uint8], cfg: dict) -> TargetHit | None:
    """Blue/wetted target only (used for shot confirmation when dry uses YOLO)."""
    _, shot_hit = detect_hsv(frame, cfg)
    return shot_hit
