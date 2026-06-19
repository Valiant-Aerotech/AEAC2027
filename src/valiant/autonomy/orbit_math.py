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
) -> tuple[float, float, float]:
    """Tangential + radial hold velocity in LOCAL NED (vn, ve, radius_error)."""
    dx = x - center_x
    dy = y - center_y
    dist = math.hypot(dx, dy)
    if dist < 1e-3:
        return 0.0, 0.0, radius_m - dist
    if clockwise:
        tn, te = dy / dist, -dx / dist
    else:
        tn, te = -dy / dist, dx / dist
    err_r = radius_m - dist
    rn, re = dx / dist, dy / dist
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
        lap_progress_rad -= delta
    else:
        lap_progress_rad += delta
    return lap_progress_rad, lap_progress_rad / (2 * math.pi), phi


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
