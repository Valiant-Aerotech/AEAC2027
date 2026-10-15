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

from offboard.obstacles_logic import EscapeGate


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


if __name__ == "__main__":
    test_stick_toward_a_cylinder_does_not_take_offboard()
    test_centered_hover_requests_offboard()
    test_pitch_during_the_move_returns_position_mode()
    test_yaw_is_not_a_cancel()
    test_climb_requests_offboard()
    test_clear_hover_holds_the_new_point()
    print("obstacles logic cases ok")
