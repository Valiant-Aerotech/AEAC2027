"""Top-down and wall side views for physics SITL."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from valiant.common.sitl_map_asset import SitlMapAsset
from valiant.common.sitl_physics import VehiclePose

_DEFAULT_VIEW_RADIUS_M = 24.0


def _ned_to_screen(
    north_m: float,
    east_m: float,
    *,
    drone_n: float,
    drone_e: float,
    scale: float,
    width: int,
    height: int,
) -> tuple[int, int]:
    """North up, east right; drone at viewport centre."""
    sx = int(width // 2 + (east_m - drone_e) * scale)
    sy = int(height // 2 - (north_m - drone_n) * scale)
    return sx, sy


def render_topdown(
    scene: dict[str, Any],
    pose: VehiclePose,
    *,
    vel_cmd: tuple[float, float, float] | None = None,
    width: int = 420,
    height: int = 420,
    map_asset: SitlMapAsset | None = None,
    view_radius_m: float = _DEFAULT_VIEW_RADIUS_M,
) -> np.ndarray:
    """North-east top-down map; drone always at centre."""
    drone_n = pose.x if pose.ok else 0.0
    drone_e = pose.y if pose.ok else 0.0
    scale = min(width, height) / (2.0 * view_radius_m)

    if map_asset is not None:
        img = map_asset.crop_drone_centered(
            drone_n, drone_e, width=width, height=height, view_radius_m=view_radius_m
        ).copy()
    else:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (24, 24, 28)

    wall = scene.get("wall") or {}
    wx = float(wall.get("x_m", 5.0))
    y0 = float(wall.get("y_min", -3.0))
    y1 = float(wall.get("y_max", 3.0))

    if map_asset is None:
        for ring in (2.0, 4.0, 6.0):
            r_px = int(ring * scale)
            if r_px > 5:
                cv2.circle(img, (width // 2, height // 2), r_px, (40, 42, 48), 1)
                cv2.putText(
                    img,
                    f"{ring:.0f}m",
                    (width // 2 + r_px + 2, height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    (55, 58, 65),
                    1,
                )

    w1 = _ned_to_screen(wx, y0, drone_n=drone_n, drone_e=drone_e, scale=scale, width=width, height=height)
    w2 = _ned_to_screen(wx, y1, drone_n=drone_n, drone_e=drone_e, scale=scale, width=width, height=height)
    cv2.line(img, w1, w2, (90, 200, 255), 4)
    cv2.putText(img, "wall", (w1[0] + 4, w1[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 220, 255), 1)

    for spec in scene.get("targets", []):
        pos = spec.get("position_ned", [0, 0, 0])
        color = tuple(spec.get("color", [180, 50, 180]))
        pt = _ned_to_screen(
            float(pos[0]),
            float(pos[1]),
            drone_n=drone_n,
            drone_e=drone_e,
            scale=scale,
            width=width,
            height=height,
        )
        cv2.circle(img, pt, 8, color, -1)
        cv2.circle(img, pt, 10, (255, 255, 255), 1)

    drone = (width // 2, height // 2)
    if pose.ok:
        cv2.circle(img, drone, 10, (0, 220, 255), -1)
        cv2.circle(img, drone, 12, (0, 0, 0), 1)
        tip_len = 22
        tip = (
            int(drone[0] + tip_len * math.sin(pose.yaw)),
            int(drone[1] - tip_len * math.cos(pose.yaw)),
        )
        cv2.arrowedLine(img, drone, tip, (0, 255, 255), 2, tipLength=0.35)
        if vel_cmd:
            vx, vy, _ = vel_cmd
            vel_tip = (
                int(drone[0] + vy * scale * 0.4),
                int(drone[1] - vx * scale * 0.4),
            )
            cv2.arrowedLine(img, drone, vel_tip, (0, 255, 120), 2, tipLength=0.3)
        for spec in scene.get("targets", []):
            pos = spec.get("position_ned", [0, 0, 0])
            tgt = _ned_to_screen(
                float(pos[0]),
                float(pos[1]),
                drone_n=drone_n,
                drone_e=drone_e,
                scale=scale,
                width=width,
                height=height,
            )
            cv2.line(img, drone, tgt, (60, 200, 60), 1, cv2.LINE_AA)

    cv2.drawMarker(img, drone, (255, 255, 255), cv2.MARKER_CROSS, 14, 1)
    cv2.putText(img, "TOP-DOWN (N up, E right)", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1)
    if pose.ok:
        cv2.putText(
            img,
            f"N={pose.x:.1f}m E={pose.y:.1f}m alt {-pose.z:.1f}m",
            (8, height - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 220, 255),
            1,
        )
    if map_asset is not None:
        cv2.putText(
            img,
            "© Esri",
            (width - 58, height - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (200, 200, 200),
            1,
        )
    return img


def render_wall_side(
    scene: dict[str, Any],
    pose: VehiclePose,
    *,
    width: int = 420,
    height: int = 320,
) -> np.ndarray:
    """Side view: horizontal distance to wall (x) vs altitude (z down)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (20, 22, 26)

    wall = scene.get("wall") or {}
    wx = float(wall.get("x_m", 5.0))
    z_top = float(wall.get("z_top", -2.5))
    z_base = float(wall.get("z_base", 0.0))
    y0 = float(wall.get("y_min", -3.0))
    y1 = float(wall.get("y_max", 3.0))

    dx = wx - (pose.x if pose.ok else 0.0)
    margin = 1.5
    x_min = min(0.0, dx) - margin
    x_max = max(wx, dx) + margin
    z_min = min(z_top, pose.z if pose.ok else 0.0) - 0.5
    z_max = max(z_base, pose.z if pose.ok else 0.0) + 0.5

    def to_px(x_n: float, z_n: float) -> tuple[int, int]:
        px = int((x_n - x_min) / max(x_max - x_min, 0.1) * (width - 40) + 20)
        py = int((z_n - z_min) / max(z_max - z_min, 0.1) * (height - 40) + 20)
        return px, py

    g1 = to_px(x_min, z_base)
    g2 = to_px(x_max, z_base)
    cv2.line(img, g1, g2, (50, 55, 60), 2)

    wtl = to_px(wx, z_top)
    wbl = to_px(wx, z_base)
    cv2.line(img, wtl, wbl, (100, 100, 120), 6)
    cv2.putText(img, "WALL", (wbl[0] + 6, (wtl[1] + wbl[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 180), 1)

    for spec in scene.get("targets", []):
        pos = spec.get("position_ned", [0, 0, 0])
        color = tuple(spec.get("color", [180, 50, 180]))
        pt = to_px(float(pos[0]), float(pos[2]))
        cv2.circle(img, pt, 9, color, -1)
        cv2.circle(img, pt, 11, (255, 255, 255), 1)

    if pose.ok:
        drone = to_px(pose.x, pose.z)
        cv2.circle(img, drone, 9, (0, 220, 255), -1)
        cv2.line(img, drone, to_px(pose.x + 1.2 * math.cos(pose.yaw), pose.z), (0, 255, 255), 2)
        cv2.putText(
            img, f"drone alt {-pose.z:.1f}m", (drone[0] + 10, drone[1]),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 255), 1,
        )
        wall_dist = wx - pose.x
        cv2.putText(
            img, f"range {wall_dist:.1f}m", (8, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 200), 1,
        )

    cv2.putText(img, "WALL VIEW (alt vs range)", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    cv2.putText(img, f"wall y=[{y0:.0f},{y1:.0f}]m", (8, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 130), 1)
    return img
