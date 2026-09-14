"""Live SITL regression: the aircraft must not sink when a script finishes.

This is the test that would have caught the LOITER descent. It needs a running
SITL, so it skips otherwise; ``tests/test_motion_hold.py`` covers the same
logic against a fake autopilot in CI.

Run with SITL up:  pytest -m sitl tests/sitl/test_sitl_hold.py -s
"""

from __future__ import annotations

import time

import pytest

from valiant.comms.gcs_hud import GcsHudReporter
from valiant.core.config import load_config
from valiant.core.motion import hold
from valiant.core.motion.guided import GuidedMotionRunner
from valiant.core.pose import refresh_vehicle_pose, wait_vehicle_pose

pytestmark = pytest.mark.sitl

HOLD_DURATION_S = 20.0
# ArduCopter's default LAND_SPEED is 50 cm/s, so an unheld aircraft loses ~10 m
# over this window. Anything inside 2 m is holding, not sinking.
MAX_ALTITUDE_LOSS_M = 2.0


def _altitude_m(pose) -> float:
    return -pose.z


@pytest.fixture
def motion(sitl_master):
    cfg = load_config()
    runner = GuidedMotionRunner(
        sitl_master,
        cfg,
        hud=GcsHudReporter(sitl_master, cfg),
        log_tag="HoldTest",
    )
    runner.set_last_pose(
        wait_vehicle_pose(sitl_master, timeout_s=20.0, need_position=True, need_attitude=True)
    )
    return runner


def test_altitude_holds_through_a_finish(motion, sitl_master):
    """``finish()`` must keep altitude, which is the whole point of the fix."""
    start_alt = _altitude_m(motion.last_pose)
    assert start_alt > 3.0, f"needs to be airborne to be meaningful (at {start_alt:.1f} m)"

    deadline = time.time() + HOLD_DURATION_S
    lowest = start_alt
    hold_started = time.time()
    motion.finish(hand_back=False, hold_s=1.0, message="Hold regression test")
    while time.time() < deadline:
        # Keep holding by hand so we can sample altitude as it goes.
        hold.hold_position(motion, duration_s=1.0, tick_s=0.05, message="")
        pose = refresh_vehicle_pose(sitl_master, motion.last_pose)
        motion.set_last_pose(pose)
        alt = _altitude_m(pose)
        lowest = min(lowest, alt)
        print(f"[HoldTest] t+{time.time() - hold_started:4.1f}s  alt={alt:6.2f} m")

    loss = start_alt - lowest
    assert loss < MAX_ALTITUDE_LOSS_M, (
        f"lost {loss:.2f} m over {HOLD_DURATION_S:.0f} s "
        f"(from {start_alt:.2f} m down to {lowest:.2f} m) - the hold is not holding"
    )


def test_finish_stays_in_guided(motion, sitl_master):
    """The regression was a mode change; assert the mode does not change."""
    before = sitl_master.flightmode
    motion.finish(hand_back=False, hold_s=2.0, message="Mode stability test")
    hb = sitl_master.recv_match(type="HEARTBEAT", blocking=True, timeout=3.0)
    assert hb is not None
    assert sitl_master.flightmode == before == "GUIDED"


def test_hand_back_is_refused_without_a_transmitter(sitl_master, motion):
    """SITL runs with --no-mavproxy, so nothing drives RC. LOITER must be refused."""
    if hold._rc_input_present(sitl_master):
        pytest.skip("this SITL has live RC input, so the guard correctly allows LOITER")
    assert hold.hand_back_to_pilot(motion) is False
    assert sitl_master.flightmode == "GUIDED"


def test_neutralized_rc_makes_loiter_survivable(sitl_master, motion):
    """Belt and braces: with RC parked at mid-stick, even LOITER holds altitude.

    Guards against a future path reaching LOITER anyway.
    """
    assert hold.neutralize_sitl_rc(sitl_master)
    start_alt = _altitude_m(refresh_vehicle_pose(sitl_master, motion.last_pose))
    assert start_alt > 3.0

    assert hold.hand_back_to_pilot(motion, allow_without_rc=True)
    lowest = start_alt
    deadline = time.time() + 10.0
    while time.time() < deadline:
        pose = refresh_vehicle_pose(sitl_master, motion.last_pose)
        motion.set_last_pose(pose)
        lowest = min(lowest, _altitude_m(pose))
        time.sleep(0.2)

    loss = start_alt - lowest
    assert loss < MAX_ALTITUDE_LOSS_M, (
        f"LOITER with neutral RC still lost {loss:.2f} m - "
        "check that SIM_RC_FAIL is 0 and RC3 override is being accepted"
    )
