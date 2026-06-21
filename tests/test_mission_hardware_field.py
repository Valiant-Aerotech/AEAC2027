"""Hardware field-day helpers on AutoExtinguisher (LOITER handoff, GUIDED standby)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from valiant.autonomy.orchestrator import AutoExtinguisher


def _minimal_ext(*, cfg: dict | None = None, sitl: bool = False, sim: bool = False) -> AutoExtinguisher:
    base_cfg = {
        "spray": {"method": "MAVLINK_SERVO"},
        "mission": {"loiter_on_complete": True, "loiter_settle_s": 0.0, "pilot_standby": False},
        "flight": {"require_gps": True},
    }
    if cfg:
        base_cfg.update(cfg)
    ext = AutoExtinguisher.__new__(AutoExtinguisher)
    ext.cfg = base_cfg
    ext.sitl = sitl
    ext.sim = sim
    ext.hand_test = False
    ext._handed_off_loiter = False
    ext.master = MagicMock()
    ext._gcs_hud = MagicMock()
    ext.nav = MagicMock()
    return ext


def test_complete_handoff_loiter_skips_sitl():
    ext = _minimal_ext(sitl=True)
    ext._complete_handoff_loiter()
    ext.nav.stop.assert_not_called()


@patch("valiant.autonomy.guided_motion.GuidedMotionRunner")
def test_complete_handoff_loiter_commands_loiter(mock_runner_cls):
    ext = _minimal_ext()
    motion = MagicMock()
    mock_runner_cls.return_value = motion

    ext._complete_handoff_loiter()

    ext.nav.stop.assert_called()
    motion.set_loiter.assert_called_once_with(message="Loiter - manual control")
    assert ext._handed_off_loiter is True


def test_sitl_stop_motion_skips_after_loiter_handoff():
    ext = _minimal_ext()
    ext._handed_off_loiter = True
    ext._sitl_stop_motion()
    ext.nav.stop.assert_not_called()


def test_mission_pilot_standby_enabled():
    ext = _minimal_ext(cfg={"mission": {"pilot_standby": True}})
    ext._allow_motion = MagicMock(return_value=True)
    assert ext._mission_pilot_standby_enabled() is True

    ext.sitl = True
    assert ext._mission_pilot_standby_enabled() is False


def test_mission_pilot_standby_disabled_when_false():
    ext = _minimal_ext(cfg={"mission": {"pilot_standby": False}})
    ext._allow_motion = MagicMock(return_value=True)
    assert ext._mission_pilot_standby_enabled() is False
