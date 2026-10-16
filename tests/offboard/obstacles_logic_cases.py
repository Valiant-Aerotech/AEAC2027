"""Stick gate for a centered hover. No ROS.

The three SITL checks that do not need Gazebo: a deflected stick does not
take offboard, a centered hover with a closing cylinder does, and pitch or
roll during that move gives position mode back. Yaw does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(_SRC / "offboard"))

from offboard.obstacles_logic import (
    EscapeAction,
    EscapeGate,
    EscapeTarget,
    EscapeTargetLatch,
    LocalSample,
    TrafficFreshness,
)


def local_sample(
    *,
    x: float = 100.0,
    y: float = 200.0,
    z: float = -30.0,
    yaw: float = 0.5,
    xy_valid: bool = True,
    z_valid: bool = True,
    heading_good_for_control: bool = True,
    xy_reset_counter: int = 0,
    z_reset_counter: int = 0,
    heading_reset_counter: int = 0,
) -> LocalSample:
    return LocalSample(
        x=x,
        y=y,
        z=z,
        yaw=yaw,
        xy_valid=xy_valid,
        z_valid=z_valid,
        heading_good_for_control=heading_good_for_control,
        xy_reset_counter=xy_reset_counter,
        z_reset_counter=z_reset_counter,
        heading_reset_counter=heading_reset_counter,
    )


def test_stick_toward_a_cylinder_does_not_take_offboard() -> None:
    gate = EscapeGate()
    action = gate.update(armed=True, pitch=0.6, roll=0.0, north_m=0.0, east_m=-20.0)
    assert action.mode is None
    assert action.heartbeat is False


def test_centered_hover_requests_offboard() -> None:
    gate = EscapeGate()
    action = gate.update(armed=True, pitch=0.0, roll=0.0, north_m=0.0, east_m=-20.0)
    assert action.mode == "offboard"
    assert action.heartbeat is True
    assert abs(action.east_m - (-20.0)) < 0.1


def test_pitch_during_the_move_returns_position_mode() -> None:
    gate = EscapeGate()
    gate.update(armed=True, pitch=0.0, roll=0.0, north_m=0.0, east_m=-20.0)
    action = gate.update(armed=True, pitch=0.4, roll=0.0, north_m=0.0, east_m=-20.0)
    assert action.mode == "position"
    assert action.heartbeat is False
    later = gate.update(armed=True, pitch=0.4, roll=0.0, north_m=0.0, east_m=-20.0)
    assert later.mode is None


def test_yaw_is_not_a_cancel() -> None:
    gate = EscapeGate()
    first = gate.update(armed=True, pitch=0.0, roll=0.0, north_m=10.0, east_m=0.0)
    second = gate.update(armed=True, pitch=0.0, roll=0.0, north_m=10.0, east_m=0.0)
    assert first.mode == "offboard"
    assert second.mode == "offboard"


def test_climb_requests_offboard() -> None:
    gate = EscapeGate()
    action = gate.update(armed=True, pitch=0.0, roll=0.0, north_m=0.0, east_m=0.0, up_m=30.0)
    assert action.mode == "offboard"
    assert action.up_m == 30.0
    assert gate.remembered() == (0.0, 0.0, 30.0)


def test_clear_hover_holds_the_new_point() -> None:
    gate = EscapeGate()
    gate.update(armed=True, pitch=0.0, roll=0.0, north_m=0.0, east_m=-20.0)
    release = gate.update(armed=True, pitch=0.0, roll=0.0, north_m=0.0, east_m=0.0)
    assert release.mode == "position"
    assert release.heartbeat is False
    stayed = gate.update(armed=True, pitch=0.0, roll=0.0, north_m=0.0, east_m=0.0)
    assert stayed.mode is None


def test_traffic_freshness_expires_at_the_boundary() -> None:
    freshness = TrafficFreshness()
    freshness.observe(accepted=True, now_s=10.0)
    assert freshness.fresh(11.999)
    assert not freshness.fresh(12.0)


def test_duplicate_does_not_renew_traffic_freshness() -> None:
    freshness = TrafficFreshness()
    freshness.observe(accepted=True, now_s=10.0)
    freshness.observe(accepted=False, now_s=11.5)
    assert not freshness.fresh(12.0)


def test_accepted_empty_snapshot_is_fresh() -> None:
    freshness = TrafficFreshness()
    freshness.observe(accepted=True, now_s=10.0)
    assert freshness.fresh(10.0)


def test_gate_reset_is_silent() -> None:
    gate = EscapeGate()
    gate.update(armed=True, pitch=0.0, roll=0.0, north_m=10.0, east_m=0.0)
    gate.reset()
    assert gate.remembered() is None
    action = gate.update(armed=True, pitch=0.4, roll=0.0, north_m=10.0, east_m=0.0)
    assert action.mode is None


def test_escape_target_is_absolute_and_stable() -> None:
    latch = EscapeTargetLatch()
    action = EscapeAction(True, 10.0, -20.0, 8.0, "offboard")
    expected = EscapeTarget(110.0, 180.0, -38.0, 0.5)
    assert latch.update(action, local_sample()) == expected
    assert latch.update(action, local_sample(x=107.0, y=190.0, z=-36.0)) == expected


def test_invalid_local_sample_clears_escape_target() -> None:
    latch = EscapeTargetLatch()
    action = EscapeAction(True, 10.0, 0.0, 0.0, "offboard")
    assert latch.update(action, local_sample()) is not None
    assert latch.update(action, local_sample(xy_valid=False)) is None


def test_estimator_reset_clears_escape_target() -> None:
    action = EscapeAction(True, 10.0, 0.0, 0.0, "offboard")
    for changed_counter in (
        {"xy_reset_counter": 1},
        {"z_reset_counter": 1},
        {"heading_reset_counter": 1},
    ):
        latch = EscapeTargetLatch()
        assert latch.update(action, local_sample()) is not None
        assert latch.update(action, local_sample(**changed_counter)) is None


if __name__ == "__main__":
    test_stick_toward_a_cylinder_does_not_take_offboard()
    test_centered_hover_requests_offboard()
    test_pitch_during_the_move_returns_position_mode()
    test_yaw_is_not_a_cancel()
    test_climb_requests_offboard()
    test_clear_hover_holds_the_new_point()
    test_traffic_freshness_expires_at_the_boundary()
    test_duplicate_does_not_renew_traffic_freshness()
    test_accepted_empty_snapshot_is_fresh()
    test_gate_reset_is_silent()
    test_escape_target_is_absolute_and_stable()
    test_invalid_local_sample_clears_escape_target()
    test_estimator_reset_clears_escape_target()
    print("obstacles logic cases ok")
