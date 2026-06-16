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


def test_aiming_blocked_until_within_slow_zone():
    planner = _planner()
    metric = MetricPacket(distance_m=1.0, distance_min_m=1.0, distance_max_m=1.0)
    assert planner.should_switch_to_aiming(metric, 20000, wall_range_m=5.0, aim_wall_range_m=3.0)
    assert not planner.should_switch_to_aiming(
        metric, 20000, wall_range_m=4.0, aim_wall_range_m=3.0
    )


def test_can_fire_requires_wall_proximity_in_sitl():
    planner = _planner()
    planner.update_approach_tracking(
        MetricPacket(distance_m=3.0, distance_max_m=3.0),
    )
    metric = MetricPacket(distance_m=1.0, distance_min_m=1.0, distance_max_m=1.0)
    assert not planner.can_fire(
        metric, lock_duration_met=True, wall_range_m=5.0, wall_standoff_m=1.2
    )
    assert planner.can_fire(
        metric, lock_duration_met=True, wall_range_m=1.1, wall_standoff_m=1.2
    )
