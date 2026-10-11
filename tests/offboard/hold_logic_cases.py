"""Plain asserts for the offboard hold rules. No ROS."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "offboard"))

from offboard.hold_logic import HoldLogic, LocalSample


def sample(**changes) -> LocalSample:
    fields = dict(
        x=1.0,
        y=2.0,
        z=-3.0,
        heading=0.4,
        xy_valid=True,
        z_valid=True,
        heading_good_for_control=True,
        xy_reset_counter=0,
        z_reset_counter=0,
        heading_reset_counter=0,
    )
    fields.update(changes)
    return LocalSample(**fields)


def test_waits_for_offboard() -> None:
    logic = HoldLogic()
    logic.set_sample(sample())
    assert logic.setpoint() is None
    assert logic.idle_line() == "waiting for offboard"


def test_bad_sample_at_switch_does_not_stick() -> None:
    logic = HoldLogic()
    logic.set_sample(sample(xy_valid=False))
    logic.set_offboard(True)
    assert logic.setpoint() is None
    assert logic.idle_line() == "waiting for local position"


def test_good_sample_latches_after_offboard() -> None:
    logic = HoldLogic()
    logic.set_offboard(True)
    logic.set_sample(sample())
    hold = logic.setpoint()
    assert hold is not None
    assert (hold.x, hold.y, hold.z, hold.yaw) == (1.0, 2.0, -3.0, 0.4)


def test_lost_position_keeps_latch() -> None:
    logic = HoldLogic()
    logic.set_offboard(True)
    logic.set_sample(sample())
    assert logic.set_sample(sample(x=math.nan, xy_valid=False)) == "position lost"
    assert logic.setpoint() is not None
    assert logic.setpoint().x == 1.0


def test_lost_heading_keeps_latch() -> None:
    logic = HoldLogic()
    logic.set_offboard(True)
    logic.set_sample(sample())
    assert logic.set_sample(sample(heading_good_for_control=False)) == "heading lost"
    assert logic.setpoint() is not None
    assert logic.setpoint().yaw == 0.4


def test_offboard_off_drops_latch() -> None:
    logic = HoldLogic()
    logic.set_offboard(True)
    logic.set_sample(sample())
    logic.set_offboard(False)
    assert logic.setpoint() is None
    assert logic.idle_line() == "waiting for offboard"


def test_reset_relatches_when_the_sample_is_good() -> None:
    logic = HoldLogic()
    logic.set_offboard(True)
    logic.set_sample(sample())
    assert logic.set_sample(sample(x=8.0, xy_reset_counter=1)) == "estimator reset"
    assert logic.setpoint().x == 8.0


def test_reset_drops_latch_when_the_sample_is_bad() -> None:
    logic = HoldLogic()
    logic.set_offboard(True)
    logic.set_sample(sample())
    assert logic.set_sample(sample(xy_valid=False, xy_reset_counter=1)) == "estimator reset"
    assert logic.setpoint() is None


if __name__ == "__main__":
    test_waits_for_offboard()
    test_bad_sample_at_switch_does_not_stick()
    test_good_sample_latches_after_offboard()
    test_lost_position_keeps_latch()
    test_lost_heading_keeps_latch()
    test_offboard_off_drops_latch()
    test_reset_relatches_when_the_sample_is_good()
    test_reset_drops_latch_when_the_sample_is_bad()
    print("hold logic cases ok")
