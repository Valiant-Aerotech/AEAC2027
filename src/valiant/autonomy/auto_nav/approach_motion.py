"""Shared approach speed scaling (SITL + onboard)."""

from __future__ import annotations

from valiant.autonomy.packets import MetricPacket


def scale_approach_speed_metric(
    approach_speed: float,
    distance_m: float | None,
    *,
    fire_distance_m: float = 0.8,
    slow_zone_m: float = 2.5,
    creep_speed: float = 0.10,
) -> float:
    """Taper forward speed near the target to reduce overshoot."""
    if distance_m is None:
        return approach_speed
    if distance_m <= fire_distance_m:
        return 0.0
    if distance_m >= slow_zone_m:
        return approach_speed
    ratio = (distance_m - fire_distance_m) / max(slow_zone_m - fire_distance_m, 0.1)
    tapered = approach_speed * ratio * ratio
    return max(creep_speed, tapered)


def metric_planner_range(metric: MetricPacket | None) -> float | None:
    if metric is None:
        return None
    return metric.planner_range_m()


def effective_approach_speed(
    cfg: dict, metric: MetricPacket | None, *, creep: bool = False
) -> float:
    nav = cfg.get("auto_nav", {})
    metric_cfg = cfg.get("metric_recon", {})
    base = float(nav.get("approach_speed", 0.25))
    if creep:
        base = min(base, float(nav.get("creep_speed", 0.10)))
    dist = metric_planner_range(metric)
    return scale_approach_speed_metric(
        base,
        dist,
        fire_distance_m=float(metric_cfg.get("fire_distance_m", 0.8)),
        slow_zone_m=float(nav.get("approach_slow_zone_m", 2.5)),
        creep_speed=float(nav.get("creep_speed", 0.10)),
    )
