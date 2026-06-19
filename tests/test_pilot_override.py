"""Tests for pilot override and kill-switch detection."""

from __future__ import annotations

from valiant.autonomy.pilot_override import (
    OverrideKind,
    PilotOverrideMonitor,
    _rc_channel_pwm,
    override_message,
)


class _FakeHb:
    def __init__(self, *, mode_id: int = 4, armed: bool = True, sysid: int = 1):
        self.custom_mode = mode_id
        self.base_mode = 128 if armed else 0
        self._sysid = sysid

    def get_srcSystem(self) -> int:
        return self._sysid

    def get_type(self) -> str:
        return "HEARTBEAT"


class _FakeRc:
    def __init__(self, pwm_by_ch: dict[int, int], sysid: int = 1):
        for ch, pwm in pwm_by_ch.items():
            setattr(self, f"chan{ch}_raw", pwm)
        self._sysid = sysid

    def get_srcSystem(self) -> int:
        return self._sysid

    def get_type(self) -> str:
        return "RC_CHANNELS"


class _FakeMaster:
    def __init__(self, messages: list, *, flightmode: str = "GUIDED"):
        self._messages = list(messages)
        self.target_system = 1
        self.flightmode = flightmode
        self._mapping = {"GUIDED": 4, "LOITER": 5, "LAND": 9, "STABILIZE": 0}

    def mode_mapping(self) -> dict:
        return dict(self._mapping)

    def recv_match(self, *, type, blocking=False, timeout=0.5):
        del type, blocking, timeout
        if not self._messages:
            return None
        return self._messages.pop(0)


def test_override_none_when_guided_armed():
    master = _FakeMaster([_FakeHb(mode_id=4, armed=True)])
    monitor = PilotOverrideMonitor(master, {"field_orbit": {"pilot": {}}})
    assert monitor.poll() == OverrideKind.NONE


def test_manual_takeover_when_left_guided():
    master = _FakeMaster([_FakeHb(mode_id=5, armed=True)], flightmode="LOITER")
    monitor = PilotOverrideMonitor(master, {"field_orbit": {"pilot": {}}})
    assert monitor.poll() == OverrideKind.MANUAL_TAKEOVER
    assert "takeover" in override_message(OverrideKind.MANUAL_TAKEOVER).lower()


def test_emergency_on_land_mode():
    master = _FakeMaster([_FakeHb(mode_id=9, armed=True)], flightmode="LAND")
    monitor = PilotOverrideMonitor(master, {"field_orbit": {"pilot": {}}})
    assert monitor.poll() == OverrideKind.EMERGENCY


def test_kill_switch_pwm_high():
    cfg = {
        "field_orbit": {
            "pilot": {"kill_switch_rc_channel": 8, "kill_switch_pwm_high": 1300},
        },
    }
    master = _FakeMaster(
        [
            _FakeHb(mode_id=4, armed=True),
            _FakeRc({8: 1800}),
        ],
    )
    monitor = PilotOverrideMonitor(master, cfg)
    assert monitor.poll() == OverrideKind.KILL_SWITCH


def test_disarmed_override():
    master = _FakeMaster([_FakeHb(mode_id=4, armed=False)])
    monitor = PilotOverrideMonitor(master, {"field_orbit": {"pilot": {}}})
    assert monitor.poll() == OverrideKind.DISARMED


def test_poll_empty_buffer_keeps_armed_snapshot():
    """No HEARTBEAT in drain must not false-disarm when snapshot is armed."""
    master = _FakeMaster([_FakeHb(mode_id=4, armed=True)])
    monitor = PilotOverrideMonitor(master, {"field_orbit": {"pilot": {}}})
    assert monitor.poll() == OverrideKind.NONE
    assert monitor.poll() == OverrideKind.NONE


def test_poll_empty_buffer_stays_disarmed_when_never_synced():
    master = _FakeMaster([], flightmode="GUIDED")
    monitor = PilotOverrideMonitor(master, {"field_orbit": {"pilot": {}}})
    assert monitor.poll() == OverrideKind.DISARMED


def test_rc_channel_pwm_1_based():
    msg = _FakeRc({8: 1500})
    assert _rc_channel_pwm(msg, 8) == 1500
    assert _rc_channel_pwm(msg, 0) is None


def test_guided_motion_stops_stream_on_override():
    from valiant.autonomy.guided_motion import GuidedMotionRunner

    master = _FakeMaster([_FakeHb(mode_id=5, armed=True)], flightmode="LOITER")
    cfg = {"field_orbit": {"pilot": {}}}
    motion = GuidedMotionRunner(master, cfg, log_tag="Test")
    motion.set_pilot_monitor(PilotOverrideMonitor(master, cfg))
    motion._stream._active = True
    kind = motion.check_pilot_override()
    assert kind == OverrideKind.MANUAL_TAKEOVER
    assert not motion._stream._active
