"""Regression tests for the SITL LOITER descent.

The bug: every scripted flight ended with an unconditional switch to LOITER.
LOITER is pilot-controlled, SITL has no transmitter, so channel 3 read at
minimum, LOITER read that as full-down throttle, and the aircraft descended
into the ground. These tests pin the three properties of the fix.
"""

from __future__ import annotations

import pytest

from valiant.core.errors import FlightPreconditionError
from valiant.core.motion import hold


class _Hb:
    def __init__(self, custom_mode: int):
        self.custom_mode = custom_mode

    def get_type(self) -> str:
        return "HEARTBEAT"

    def get_srcSystem(self) -> int:
        return 1


class _Rc:
    """RC_CHANNELS as the autopilot reports it."""

    def __init__(self, throttle_pwm: int):
        self.chan3_raw = throttle_pwm

    def get_type(self) -> str:
        return "RC_CHANNELS"

    def get_srcSystem(self) -> int:
        return 1


class _FakeMav:
    def __init__(self):
        self.overrides: list[tuple[int, ...]] = []
        self.params: dict[bytes, float] = {}

    def rc_channels_override_send(self, _sys, _comp, *channels):
        self.overrides.append(tuple(channels))

    def param_set_send(self, _sys, _comp, name, value, _type):
        self.params[name] = value


class _FakeMaster:
    """Minimal autopilot stand-in: mode mapping, RC feed, heartbeat feed."""

    def __init__(self, *, throttle_pwm: int | None = 1500, has_loiter: bool = True):
        self.target_system = 1
        self.target_component = 1
        self.mav = _FakeMav()
        self.modes = {"GUIDED": 4, "LAND": 9}
        if has_loiter:
            self.modes["LOITER"] = 5
        self.mode_set_to: int | None = None
        self._throttle_pwm = throttle_pwm

    def mode_mapping(self) -> dict[str, int]:
        return self.modes

    def set_mode(self, mode_id: int) -> None:
        self.mode_set_to = mode_id

    def recv_match(self, type=None, blocking=False, timeout=None):  # noqa: A002
        wanted = [type] if isinstance(type, str) else (type or [])
        if "RC_CHANNELS" in wanted:
            return None if self._throttle_pwm is None else _Rc(self._throttle_pwm)
        if "HEARTBEAT" in wanted:
            return _Hb(self.mode_set_to if self.mode_set_to is not None else 4)
        return None


class _FakeServo:
    def __init__(self):
        self.sent: list[tuple[float, float, float]] = []

    def send_velocity_body(self, vx, vy, vz):
        self.sent.append((vx, vy, vz))


class _FakePose:
    def __init__(self, z: float):
        self.z = z
        self.ok = True


class _FakeMotion:
    """Stands in for GuidedMotionRunner."""

    def __init__(self, master: _FakeMaster, *, alt_m: float = 20.0):
        self.master = master
        self.servo = _FakeServo()
        self.last_pose = _FakePose(-alt_m)
        self.said: list[str] = []
        self.z_hold: float | None = None
        self.streaming = False
        self.vz_command = 0.0

    def say(self, message, *, force=True):
        self.said.append(message)

    def heartbeat(self):
        pass

    def refresh_pose(self, previous=None):
        return self.last_pose

    def set_last_pose(self, pose):
        self.last_pose = pose

    def set_z_hold(self, z_ned):
        self.z_hold = z_ned

    def altitude_vz(self, target_alt_m, *, tolerance_m=0.35):
        return self.vz_command

    def start_stream(self):
        self.streaming = True

    def stop_stream(self):
        self.streaming = False

    def check_pilot_override(self):
        class _None:
            name = "NONE"

        return _None()


# --- 1. An autonomous hold must stay in GUIDED, not LOITER ----------------


def test_hold_position_never_changes_mode():
    master = _FakeMaster()
    motion = _FakeMotion(master)
    assert hold.hold_position(motion, duration_s=0.15, tick_s=0.01)
    assert master.mode_set_to is None, "an autonomous hold must not switch modes"


def test_hold_position_streams_zero_horizontal_velocity():
    motion = _FakeMotion(_FakeMaster())
    hold.hold_position(motion, duration_s=0.15, tick_s=0.01)
    assert motion.servo.sent, "hold must keep commanding, or GUIDED times out"
    assert all(vx == 0.0 and vy == 0.0 for vx, vy, _ in motion.servo.sent)


def test_hold_position_latches_the_current_altitude():
    motion = _FakeMotion(_FakeMaster(), alt_m=32.5)
    hold.hold_position(motion, duration_s=0.05, tick_s=0.01)
    assert motion.z_hold == -32.5


def test_hold_position_corrects_altitude_error():
    motion = _FakeMotion(_FakeMaster())
    motion.vz_command = -0.12  # NED: negative is up, so this is a climb
    hold.hold_position(motion, duration_s=0.05, tick_s=0.01)
    assert any(vz == -0.12 for _, _, vz in motion.servo.sent)


def test_hold_position_reports_pilot_takeover():
    motion = _FakeMotion(_FakeMaster())

    class _Override:
        name = "MODE_CHANGE"

    motion.check_pilot_override = lambda: _Override()
    assert hold.hold_position(motion, duration_s=0.05, tick_s=0.01) is False


# --- 2. LOITER handoff requires a real transmitter ------------------------


def test_hand_back_refuses_when_there_is_no_rc_input():
    """The exact SITL failure. Refusing here is what saves the aircraft."""
    master = _FakeMaster(throttle_pwm=0)
    motion = _FakeMotion(master)
    assert hold.hand_back_to_pilot(motion) is False
    assert master.mode_set_to is None


def test_hand_back_refuses_when_rc_is_at_minimum():
    master = _FakeMaster(throttle_pwm=800)
    assert hold.hand_back_to_pilot(_FakeMotion(master)) is False
    assert master.mode_set_to is None


def test_hand_back_refuses_when_rc_is_silent():
    master = _FakeMaster(throttle_pwm=None)
    assert hold.hand_back_to_pilot(_FakeMotion(master)) is False
    assert master.mode_set_to is None


def test_hand_back_switches_to_loiter_with_a_live_transmitter():
    master = _FakeMaster(throttle_pwm=1500)
    assert hold.hand_back_to_pilot(_FakeMotion(master)) is True
    assert master.mode_set_to == master.modes["LOITER"]


def test_hand_back_can_be_forced_for_a_deliberate_field_handoff():
    master = _FakeMaster(throttle_pwm=0)
    assert hold.hand_back_to_pilot(_FakeMotion(master), allow_without_rc=True) is True
    assert master.mode_set_to == master.modes["LOITER"]


def test_hand_back_raises_when_the_vehicle_has_no_loiter():
    master = _FakeMaster(throttle_pwm=1500, has_loiter=False)
    with pytest.raises(FlightPreconditionError, match="LOITER"):
        hold.hand_back_to_pilot(_FakeMotion(master))


# --- 3. The simulator gets its RC parked at neutral ----------------------


def test_neutralize_sitl_rc_centres_throttle_and_clears_rc_failsafe():
    master = _FakeMaster()
    assert hold.neutralize_sitl_rc(master) is True
    (override,) = master.mav.overrides
    assert override[hold.RC_CHANNEL_THROTTLE - 1] == hold.RC_MID_PWM
    # Every other channel must be left alone, not forced to zero.
    others = [v for i, v in enumerate(override) if i != hold.RC_CHANNEL_THROTTLE - 1]
    assert set(others) == {hold.RC_NO_CHANGE}
    assert master.mav.params[b"SIM_RC_FAIL"] == 0


def test_neutralize_sitl_rc_is_never_fatal():
    class _Unsupported:
        target_system = 1
        target_component = 1

        class mav:  # noqa: N801
            @staticmethod
            def rc_channels_override_send(*_a):
                raise OSError("link does not support override")

    assert hold.neutralize_sitl_rc(_Unsupported()) is False


def test_release_rc_override_clears_every_channel():
    master = _FakeMaster()
    hold.release_rc_override(master)
    (override,) = master.mav.overrides
    assert set(override) == {hold.RC_NO_CHANGE}
