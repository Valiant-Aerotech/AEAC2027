"""Pure LOCAL NED orbit geometry for field orbit flight."""

from __future__ import annotations

import math


def wrap_pi(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def circle_center(
    x: float,
    y: float,
    yaw_rad: float,
    radius_m: float,
    *,
    clockwise: bool,
) -> tuple[float, float]:
    """Circle center offset R to the right (CW) or left (CCW) of heading."""
    right_n = math.sin(yaw_rad)
    right_e = math.cos(yaw_rad)
    sign = 1.0 if clockwise else -1.0
    return x + sign * radius_m * right_n, y + sign * radius_m * right_e


def orbit_velocity_ned(
    x: float,
    y: float,
    center_x: float,
    center_y: float,
    radius_m: float,
    orbit_speed_m_s: float,
    radial_kp: float,
    *,
    clockwise: bool,
    min_dist_m: float = 0.5,
) -> tuple[float, float, float]:
    """Tangential + radial hold velocity in LOCAL NED (vn, ve, radius_error)."""
    dx = x - center_x
    dy = y - center_y
    actual_dist = math.hypot(dx, dy)
    err_r = radius_m - actual_dist
    if actual_dist < min_dist_m:
        angle = math.atan2(dy, dx) if actual_dist > 1e-6 else 0.0
        dx = math.cos(angle) * min_dist_m
        dy = math.sin(angle) * min_dist_m
        actual_dist = min_dist_m
    if clockwise:
        tn, te = -dy / actual_dist, dx / actual_dist
    else:
        tn, te = dy / actual_dist, -dx / actual_dist
    rn, re = (x - center_x) / max(actual_dist, 1e-6), (y - center_y) / max(actual_dist, 1e-6)
    vn = orbit_speed_m_s * tn + radial_kp * err_r * rn
    ve = orbit_speed_m_s * te + radial_kp * err_r * re
    return vn, ve, err_r


def update_lap_progress(
    x: float,
    y: float,
    center_x: float,
    center_y: float,
    phi_prev: float | None,
    lap_progress_rad: float,
    *,
    clockwise: bool,
) -> tuple[float, float, float | None]:
    """Return (lap_progress_rad, laps, phi) after one sample about center."""
    dx = x - center_x
    dy = y - center_y
    phi = math.atan2(dy, dx)
    if phi_prev is None:
        return lap_progress_rad, lap_progress_rad / (2 * math.pi), phi
    delta = wrap_pi(phi - phi_prev)
    if clockwise:
        lap_progress_rad += delta
    else:
        lap_progress_rad -= delta
    return lap_progress_rad, lap_progress_rad / (2 * math.pi), phi


def advance_arc_progress_m(
    arc_progress_m: float,
    vn: float,
    ve: float,
    dt_s: float,
) -> float:
    """Integrate path length from commanded horizontal velocity."""
    return arc_progress_m + math.hypot(vn, ve) * dt_s


def combined_laps(
    lap_progress_rad: float,
    arc_progress_m: float,
    radius_m: float,
) -> float:
    """Angle-based laps with arc-length backup (use higher estimate)."""
    laps_angle = lap_progress_rad / (2 * math.pi)
    if radius_m <= 0:
        return laps_angle
    laps_arc = arc_progress_m / (2 * math.pi * radius_m)
    return max(laps_angle, laps_arc)


def velocity_toward_ned(
    x: float,
    y: float,
    target_x: float,
    target_y: float,
    speed_m_s: float,
) -> tuple[float, float]:
    """Unit vector toward target scaled by speed."""
    dx = target_x - x
    dy = target_y - y
    dist = math.hypot(dx, dy)
    if dist < 1e-3:
        return 0.0, 0.0
    scale = min(speed_m_s, dist * 0.5)
    return scale * dx / dist, scale * dy / dist


def simulate_orbit_path(
    center_x: float,
    center_y: float,
    radius_m: float,
    *,
    clockwise: bool = True,
    orbit_speed_m_s: float = 0.4,
    radial_kp: float = 0.25,
    dt_s: float = 0.05,
    duration_s: float = 90.0,
    start_angle_rad: float = 0.0,
) -> tuple[float, list[tuple[float, float]], float]:
    """Integrate orbit velocity; return (laps, path, min_radius)."""
    angle = start_angle_rad
    x = center_x + radius_m * math.cos(angle)
    y = center_y + radius_m * math.sin(angle)
    path: list[tuple[float, float]] = [(x, y)]
    lap_progress = 0.0
    phi_prev: float | None = None
    min_radius = radius_m
    steps = int(duration_s / dt_s)
    for _ in range(steps):
        vn, ve, _ = orbit_velocity_ned(
            x,
            y,
            center_x,
            center_y,
            radius_m,
            orbit_speed_m_s,
            radial_kp,
            clockwise=clockwise,
        )
        x += vn * dt_s
        y += ve * dt_s
        path.append((x, y))
        dist = math.hypot(x - center_x, y - center_y)
        min_radius = min(min_radius, dist)
        lap_progress, laps, phi_prev = update_lap_progress(
            x,
            y,
            center_x,
            center_y,
            phi_prev,
            lap_progress,
            clockwise=clockwise,
        )
        if laps >= 1.0:
            return laps, path, min_radius
    return lap_progress / (2 * math.pi), path, min_radius
