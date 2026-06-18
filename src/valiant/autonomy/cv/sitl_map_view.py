"""Top-down and wall side views for physics SITL."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from valiant.autonomy.cv.sitl_hud import (
    C_BORDER,
    C_GREEN,
    C_WALL,
    draw_compass,
    draw_corner_brackets,
    draw_drone_icon,
    draw_footer,
    draw_scale_bar,
    draw_target_marker,
    draw_title_bar,
    state_color,
    vignette,
)
from valiant.common.sitl_map_asset import SitlMapAsset
from valiant.common.sitl_physics import VehiclePose, target_display_color

_DEFAULT_VIEW_RADIUS_M = 24.0
_VIEW_W = 480
_VIEW_H = 480
_WALL_W = 480
_WALL_H = 360
_SITL_WINDOW_W = 1280
_SITL_WINDOW_H = 720


def _fit_panel(src: np.ndarray, width: int, height: int) -> np.ndarray:
    """Letterbox-scale *src* into a panel of size (width, height)."""
    sh, sw = src.shape[:2]
    if sw <= 0 or sh <= 0:
        out = np.zeros((height, width, 3), dtype=np.uint8)
        out[:] = (18, 20, 26)
        return out
    scale = min(width / sw, height / sh)
    nw, nh = max(int(sw * scale), 1), max(int(sh * scale), 1)
    resized = cv2.resize(src, (nw, nh), interpolation=cv2.INTER_AREA)
    out = np.zeros((height, width, 3), dtype=np.uint8)
    out[:] = (18, 20, 26)
    x0 = (width - nw) // 2
    y0 = (height - nh) // 2
    out[y0 : y0 + nh, x0 : x0 + nw] = resized
    return out


def render_sitl_dashboard(
    fov_overlay: np.ndarray,
    scene: dict[str, Any],
    pose: VehiclePose,
    *,
    state: str = "",
    vel_cmd: tuple[float, float, float] | None = None,
    map_asset: SitlMapAsset | None = None,
    view_radius_m: float = _DEFAULT_VIEW_RADIUS_M,
    width: int = _SITL_WINDOW_W,
    height: int = _SITL_WINDOW_H,
    mode_label: str = "",
) -> np.ndarray:
    """Single-window grid: 50% FOV | 25% wall side + 25% top-down."""
    if scene is None:
        return _fit_panel(fov_overlay, width, height)
    fov_w = width // 2
    side_w = width - fov_w
    side_h = height // 2
    top_h = height - side_h

    fov_panel = _fit_panel(fov_overlay, fov_w, height)
    wall = render_wall_side(scene, pose, width=side_w, height=side_h, compact=True)
    top = render_topdown(
        scene,
        pose,
        vel_cmd=vel_cmd,
        width=side_w,
        height=top_h,
        map_asset=map_asset,
        view_radius_m=view_radius_m,
        compact=True,
    )

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:] = (14, 16, 22)
    canvas[:, :fov_w] = fov_panel
    canvas[0:side_h, fov_w:] = wall
    canvas[side_h:, fov_w:] = top

    cv2.line(canvas, (fov_w, 0), (fov_w, height), C_BORDER, 2, cv2.LINE_AA)
    cv2.line(canvas, (fov_w, side_h), (width, side_h), C_BORDER, 1, cv2.LINE_AA)

    if state:
        pill = f" {state} "
        color = state_color(state)
        pill_w = min(len(pill) * 9 + 16, fov_w - 16)
        cv2.rectangle(canvas, (8, 8), (8 + pill_w, 30), color, -1, cv2.LINE_AA)
        cv2.putText(
            canvas, pill, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 22, 28), 1, cv2.LINE_AA,
        )
    if mode_label:
        tw = cv2.getTextSize(mode_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0][0]
        cv2.putText(
            canvas,
            mode_label,
            (fov_w - tw - 12, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (130, 138, 155),
            1,
            cv2.LINE_AA,
        )
    return canvas


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
    sx = int(width // 2 + (east_m - drone_e) * scale)
    sy = int(height // 2 - (north_m - drone_n) * scale)
    return sx, sy


def _enhance_map(img: np.ndarray) -> np.ndarray:
    if img.mean() < 25:
        return img
    out = cv2.convertScaleAbs(img, alpha=1.12, beta=18)
    return cv2.GaussianBlur(out, (3, 3), 0)


def render_topdown(
    scene: dict[str, Any],
    pose: VehiclePose,
    *,
    vel_cmd: tuple[float, float, float] | None = None,
    width: int = _VIEW_W,
    height: int = _VIEW_H,
    map_asset: SitlMapAsset | None = None,
    view_radius_m: float = _DEFAULT_VIEW_RADIUS_M,
    compact: bool = False,
) -> np.ndarray:
    """North-east top-down map; drone always at centre."""
    if scene is None:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (22, 24, 30)
        draw_title_bar(img, "TOP-DOWN", "no world scene", compact=compact)
        return img
    drone_n = pose.x if pose.ok else 0.0
    drone_e = pose.y if pose.ok else 0.0
    scale = min(width, height) / (2.0 * view_radius_m)

    if map_asset is not None:
        img = map_asset.crop_drone_centered(
            drone_n, drone_e, width=width, height=height, view_radius_m=view_radius_m
        ).copy()
        img = _enhance_map(img)
    else:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (22, 24, 30)
        for i in range(0, width, 40):
            cv2.line(img, (i, 0), (i, height), (32, 34, 40), 1)
        for j in range(0, height, 40):
            cv2.line(img, (0, j), (width, j), (32, 34, 40), 1)

    overlay = img.copy()
    wall = scene.get("wall") or {}
    wx = float(wall.get("x_m", 5.0))
    y0 = float(wall.get("y_min", -3.0))
    y1 = float(wall.get("y_max", 3.0))

    w1 = _ned_to_screen(wx, y0, drone_n=drone_n, drone_e=drone_e, scale=scale, width=width, height=height)
    w2 = _ned_to_screen(wx, y1, drone_n=drone_n, drone_e=drone_e, scale=scale, width=width, height=height)
    cv2.line(overlay, w1, w2, C_WALL, 5, cv2.LINE_AA)
    cv2.putText(overlay, "WALL", (w1[0] + 6, (w1[1] + w2[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, C_WALL, 1, cv2.LINE_AA)

    for spec in scene.get("targets", []):
        pos = spec.get("position_ned", [0, 0, 0])
        color = target_display_color(spec)
        pt = _ned_to_screen(
            float(pos[0]), float(pos[1]),
            drone_n=drone_n, drone_e=drone_e, scale=scale, width=width, height=height,
        )
        draw_target_marker(overlay, pt[0], pt[1], color)

    drone = (width // 2, height // 2)
    if pose.ok:
        if vel_cmd:
            vx, vy, _ = vel_cmd
            vel_tip = (int(drone[0] + vy * scale * 0.5), int(drone[1] - vx * scale * 0.5))
            cv2.arrowedLine(overlay, drone, vel_tip, C_GREEN, 2, tipLength=0.3, line_type=cv2.LINE_AA)
        draw_drone_icon(overlay, drone[0], drone[1], pose.yaw, scale=1.1)
        for spec in scene.get("targets", []):
            pos = spec.get("position_ned", [0, 0, 0])
            tgt = _ned_to_screen(
                float(pos[0]), float(pos[1]),
                drone_n=drone_n, drone_e=drone_e, scale=scale, width=width, height=height,
            )
            cv2.line(overlay, drone, tgt, (70, 160, 90), 1, cv2.LINE_AA)

    cv2.addWeighted(overlay, 0.92, img, 0.08, 0, img)
    if not compact:
        vignette(img, 0.28)
    draw_corner_brackets(img, margin=6 if compact else 8, length=12 if compact else 18)
    draw_title_bar(
        img,
        "TOP-DOWN",
        "" if compact else "N up  |  E right  |  drone centred",
        compact=compact,
    )
    if not compact:
        draw_compass(img, width - 36, 52, radius=24)
    scale_m = 5.0 if view_radius_m > 15 else 2.0
    fh = 20 if compact else 26
    scale_y = height - fh - 10 if compact else height - 48
    draw_scale_bar(img, 14, scale_y, scale_m, scale)
    if pose.ok:
        wall_range = wx - pose.x
        footer_left = (
            f"N{pose.x:+.1f} E{pose.y:+.1f} alt{-pose.z:.1f}m | wall{wall_range:.1f}m"
            if compact
            else f"N {pose.x:+.1f} E {pose.y:+.1f} alt {-pose.z:.1f}m  |  wall {wall_range:.1f}m"
        )
        draw_footer(
            img,
            footer_left,
            right="Esri" if map_asset else "",
            compact=compact,
        )
    return img


def render_wall_side(
    scene: dict[str, Any],
    pose: VehiclePose,
    *,
    width: int = _WALL_W,
    height: int = _WALL_H,
    compact: bool = False,
) -> np.ndarray:
    """Side view: horizontal distance to wall (x) vs altitude (z down)."""
    if scene is None:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (32, 34, 40)
        draw_title_bar(img, "WALL SIDE", "no world scene", compact=compact)
        return img
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # sky gradient
    for row in range(height):
        t = row / max(height - 1, 1)
        img[row, :] = (int(40 + 20 * t), int(36 + 18 * t), int(32 + 14 * t))

    wall = scene.get("wall") or {}
    wx = float(wall.get("x_m", 5.0))
    z_top = float(wall.get("z_top", -2.5))
    z_base = float(wall.get("z_base", 0.0))
    y0 = float(wall.get("y_min", -3.0))
    y1 = float(wall.get("y_max", 3.0))

    margin_x = 1.8
    margin_z = 0.6
    drone_x = pose.x if pose.ok else 0.0
    drone_z = pose.z if pose.ok else 0.0
    x_min = min(0.0, drone_x, wx) - margin_x
    x_max = max(wx, drone_x) + margin_x
    z_min = min(z_top, drone_z) - margin_z
    z_max = max(z_base, 0.0) + margin_z

    plot_l, plot_t, plot_r, plot_b = 36, 44, width - 16, height - 36
    plot_w = plot_r - plot_l
    plot_h = plot_b - plot_t

    def to_px(x_n: float, z_n: float) -> tuple[int, int]:
        px = int(plot_l + (x_n - x_min) / max(x_max - x_min, 0.1) * plot_w)
        py = int(plot_t + (z_n - z_min) / max(z_max - z_min, 0.1) * plot_h)
        return px, py

    for frac in (0.25, 0.5, 0.75):
        gy = int(plot_t + plot_h * frac)
        cv2.line(img, (plot_l, gy), (plot_r, gy), (50, 54, 62), 1, cv2.LINE_AA)

    g1 = to_px(x_min, z_base)
    g2 = to_px(x_max, z_base)
    cv2.line(img, g1, g2, (70, 78, 88), 3, cv2.LINE_AA)
    cv2.putText(img, "ground", (g1[0], g1[1] + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 128, 140), 1, cv2.LINE_AA)

    wtl = to_px(wx, z_top)
    wbl = to_px(wx, z_base)
    cv2.line(img, wtl, wbl, C_WALL, 8, cv2.LINE_AA)
    cv2.putText(img, "WALL", (wbl[0] + 8, (wtl[1] + wbl[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, C_WALL, 1, cv2.LINE_AA)

    for spec in scene.get("targets", []):
        pos = spec.get("position_ned", [0, 0, 0])
        color = target_display_color(spec)
        pt = to_px(float(pos[0]), float(pos[2]))
        draw_target_marker(img, pt[0], pt[1], color)

    wall_dist = 0.0
    alt_m = 0.0
    if pose.ok:
        drone = to_px(pose.x, pose.z)
        draw_drone_icon(img, drone[0], drone[1], pose.yaw, scale=0.85)
        wall_dist = wx - pose.x
        alt_m = -pose.z

    cv2.rectangle(img, (plot_l, plot_t), (plot_r, plot_b), (55, 62, 78), 1, cv2.LINE_AA)
    draw_corner_brackets(img, margin=6 if compact else 8, length=12 if compact else 18)
    draw_title_bar(
        img,
        "WALL SIDE",
        "" if compact else "range (N) vs altitude",
        compact=compact,
    )
    draw_footer(
        img,
        (
            f"range {wall_dist:.1f}m  alt {alt_m:.1f}m"
            if pose.ok
            else ""
        ),
        right="wall anchor",
        compact=compact,
    )
    return img
