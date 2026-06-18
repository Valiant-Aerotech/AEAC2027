"""Motion planner gating for SITL wall-range checks."""

from __future__ import annotations

from valiant.autonomy.auto_nav.planner import MotionPlanner
from valiant.autonomy.packets import MetricPacket


def _planner() -> MotionPlanner:
    return MotionPlanner(
        {
            "auto_nav": {"target_lock_area_px": 15000, "side_clearance_m": 1.0},
            "metric_recon": {
                "min_approach_distance_m": 2.0,
                "fire_distance_m": 0.8,
            },
        }
    )


def _metric(**kwargs) -> MetricPacket:
    base = {"target_px": (320, 240), "pixel_offset": (0.0, 0.0)}
    base.update(kwargs)
    return MetricPacket(**base)


def test_aiming_blocked_until_within_slow_zone():
    planner = _planner()
    metric = _metric(distance_m=1.0, distance_min_m=1.0, distance_max_m=1.0)
    assert not planner.should_switch_to_aiming(
        metric, 20000, wall_range_m=5.0, aim_wall_range_m=3.0
    )
    assert planner.should_switch_to_aiming(
        metric, 20000, wall_range_m=2.5, aim_wall_range_m=3.0
    )


def test_can_fire_requires_wall_proximity_in_sitl():
    planner = _planner()
    planner.update_approach_tracking(_metric(distance_m=3.0, distance_max_m=3.0))
    metric = _metric(distance_m=0.85, distance_min_m=0.85, distance_max_m=0.85)
    assert not planner.can_fire(
        metric, lock_duration_met=True, wall_range_m=5.0, wall_standoff_m=1.2
    )
    assert not planner.can_fire(
        metric, lock_duration_met=True, wall_range_m=1.1, wall_standoff_m=1.2
    )
    assert planner.can_fire(
        metric, lock_duration_met=True, wall_range_m=0.9, wall_standoff_m=1.2
    )


def test_fire_blockers_trigger_approach_remediation():
    planner = _planner()
    metric = _metric(distance_m=2.5, distance_min_m=2.5, distance_max_m=2.5)
    blockers = planner.fire_blockers(metric, lock_duration_met=True)
    assert "approach_not_proven" in blockers
    assert "too_far_metric" in blockers
    assert planner.needs_approach_remediation(blockers)


def test_scale_approach_speed_tapers_near_target():
    from valiant.autonomy.auto_nav.approach_motion import scale_approach_speed_metric

    far = scale_approach_speed_metric(0.20, 2.0, slow_zone_m=2.5, creep_speed=0.05)
    near = scale_approach_speed_metric(0.20, 1.0, slow_zone_m=2.5, fire_distance_m=0.8, creep_speed=0.05)
    assert far > near
    assert near >= 0.05
