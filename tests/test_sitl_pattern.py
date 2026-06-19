"""Unit tests for SITL pattern leg definitions."""

from __future__ import annotations

import math

from valiant.autonomy.sitl_pattern import DEFAULT_PATTERN, _wrap_pi
from valiant.common.mavlink import command_yaw_relative


def test_default_pattern_has_seven_legs():
    assert len(DEFAULT_PATTERN) == 7


def test_default_pattern_sequence():
    kinds = [leg.kind for leg in DEFAULT_PATTERN]
    assert kinds == ["forward", "turn", "forward", "turn", "forward", "turn", "forward"]
    assert DEFAULT_PATTERN[0].value == 10.0
    assert DEFAULT_PATTERN[1].value == 90.0
    assert DEFAULT_PATTERN[3].value == -180.0
    assert DEFAULT_PATTERN[6].value == 10.0


def test_wrap_pi_turn_target():
    yaw0 = 0.0
    target = _wrap_pi(yaw0 + math.radians(90))
    assert abs(target - math.pi / 2) < 1e-6


def test_command_yaw_relative_sends_condition_yaw():
    sent: list[tuple] = []

    class FakeMav:
        target_system = 1
        target_component = 1

        class mav:
            @staticmethod
            def command_long_send(*args):
                sent.append(args)

    command_yaw_relative(FakeMav(), 90.0, rate_deg_s=25.0, clockwise=True)
    assert len(sent) == 1
    args = sent[0]
    assert args[2] == 115  # MAV_CMD_CONDITION_YAW
    assert args[4] == 90.0
    assert args[5] == 25.0
    assert args[6] == 1.0  # clockwise
    assert args[7] == 1.0  # relative
