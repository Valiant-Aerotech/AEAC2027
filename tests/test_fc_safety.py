"""Flight-controller safety parameter readback.

The readback is advisory by design: it reads, it warns, and it gets out of the
way. These tests pin that contract, because the tempting "improvement" is to
have it fix parameters or refuse to arm, and either would mean the aircraft
that passed the FRR is not the aircraft that takes off.
"""

from __future__ import annotations

import inspect

import pytest

from valiant.core.flight import fc_safety
from valiant.core.flight.fc_safety import (
    PARAM_SPECS,
    PreflightReport,
    fetch_param_value,
    format_report,
    preflight_readback,
    read_safety_params,
)

# What a correctly configured aircraft reads back.
GOOD_PARAMS = {
    "LAND_SPEED": 200.0,
    "FENCE_ACTION": 2.0,
    "FENCE_ENABLE": 1.0,
    "FENCE_TYPE": 5.0,
    "FENCE_ALT_MAX": 100.0,
    "FENCE_TOTAL": 6.0,
    "FS_THR_ENABLE": 1.0,
    "SCR_ENABLE": 1.0,
    "FS_GCS_ENABLE": 1.0,
}


class _ParamMsg:
    def __init__(self, name: str, value: float, sysid: int = 1):
        self.param_id = name.encode("utf-8")
        self.param_value = value
        self._sysid = sysid

    def get_srcSystem(self) -> int:
        return self._sysid


class _FakeMaster:
    """Answers param reads from a dict. Records any attempt to write."""

    def __init__(self, params: dict[str, float] | None = None):
        self.target_system = 1
        self.target_component = 1
        self.params = dict(params or {})
        self.writes: list[tuple] = []
        self._pending: str | None = None
        self.mav = self

    def param_request_read_send(self, _sys, _comp, param_id, _index):
        name = param_id.decode("utf-8").rstrip("\x00")
        self._pending = name if name in self.params else None

    def param_set_send(self, *args, **kwargs):
        self.writes.append((args, kwargs))

    def recv_match(self, *, type, blocking=True, timeout=0.5):
        del type, blocking, timeout
        if self._pending is None:
            return None
        name, self._pending = self._pending, None
        return _ParamMsg(name, self.params[name])


def _params(**overrides) -> dict[str, float]:
    return {**GOOD_PARAMS, **overrides}


def _finding(report: PreflightReport, name: str):
    return next(f for f in report.findings if f.name == name)


# --- Reading --------------------------------------------------------------


def test_fetch_param_value_reads_a_parameter():
    master = _FakeMaster({"SCR_ENABLE": 1.0})
    assert fetch_param_value(master, "SCR_ENABLE", timeout_s=1.0) == 1.0


def test_fetch_param_value_returns_none_on_silence():
    assert fetch_param_value(_FakeMaster(), "SCR_ENABLE", timeout_s=0.05) is None


def test_a_silent_parameter_is_unread_not_a_problem():
    """A slow or busy link is not a safety finding."""
    report = read_safety_params(_FakeMaster(), timeout_s=0.02)
    assert len(report.unread) == len(PARAM_SPECS)
    assert not report.problems
    assert not report.clean


def test_every_spec_is_checked():
    report = read_safety_params(_FakeMaster(_params()), timeout_s=0.5)
    assert {f.name for f in report.findings} == {s.name for s in PARAM_SPECS}


# --- The checks that matter ----------------------------------------------


def test_a_correct_aircraft_reads_back_clean():
    report = read_safety_params(_FakeMaster(_params()), timeout_s=0.5)
    assert report.clean, [f.problem for f in report.problems]


def test_default_land_speed_is_flagged():
    """ArduPilot ships LAND_SPEED at 50 cm/s. That is not a termination."""
    report = read_safety_params(_FakeMaster(_params(LAND_SPEED=50.0)), timeout_s=0.5)
    finding = _finding(report, "LAND_SPEED")
    assert not finding.ok
    assert "50" in finding.problem
    assert "200" in finding.problem


def test_faster_than_required_land_speed_passes():
    report = read_safety_params(_FakeMaster(_params(LAND_SPEED=250.0)), timeout_s=0.5)
    assert _finding(report, "LAND_SPEED").ok


def test_fence_action_rtl_is_flagged():
    """FENCE_ACTION=1 flies the aircraft home; CONOPS 4.5 wants termination."""
    report = read_safety_params(_FakeMaster(_params(FENCE_ACTION=1.0)), timeout_s=0.5)
    finding = _finding(report, "FENCE_ACTION")
    assert not finding.ok
    assert "is 1, expected 2" in finding.problem


def test_fence_action_report_only_is_flagged():
    report = read_safety_params(_FakeMaster(_params(FENCE_ACTION=0.0)), timeout_s=0.5)
    assert not _finding(report, "FENCE_ACTION").ok


@pytest.mark.parametrize("name", ["FENCE_ENABLE", "FS_THR_ENABLE", "SCR_ENABLE", "FS_GCS_ENABLE"])
def test_disabled_switches_are_flagged(name):
    report = read_safety_params(_FakeMaster(_params(**{name: 0.0})), timeout_s=0.5)
    finding = _finding(report, name)
    assert not finding.ok
    assert "disabled" in finding.problem


def test_fence_type_without_the_polygon_bit_is_flagged():
    """FENCE_TYPE=1 is altitude only - the Appendix C polygon is not enforced."""
    report = read_safety_params(_FakeMaster(_params(FENCE_TYPE=1.0)), timeout_s=0.5)
    finding = _finding(report, "FENCE_TYPE")
    assert not finding.ok
    assert "polygon" in finding.problem


def test_fence_type_with_extra_bits_passes():
    """7 adds the min-altitude fence. More fences is not a problem."""
    report = read_safety_params(_FakeMaster(_params(FENCE_TYPE=7.0)), timeout_s=0.5)
    assert _finding(report, "FENCE_TYPE").ok


def test_wrong_ceiling_is_flagged():
    report = read_safety_params(_FakeMaster(_params(FENCE_ALT_MAX=120.0)), timeout_s=0.5)
    assert not _finding(report, "FENCE_ALT_MAX").ok


def test_empty_fence_is_flagged():
    """FENCE_TOTAL=0 means the polygon was drawn but never written."""
    report = read_safety_params(_FakeMaster(_params(FENCE_TOTAL=0.0)), timeout_s=0.5)
    assert not _finding(report, "FENCE_TOTAL").ok


def test_several_problems_are_all_reported():
    master = _FakeMaster(_params(LAND_SPEED=50.0, FENCE_ACTION=1.0, FENCE_ENABLE=0.0))
    report = read_safety_params(master, timeout_s=0.5)
    assert {f.name for f in report.problems} == {"LAND_SPEED", "FENCE_ACTION", "FENCE_ENABLE"}


# --- Never writes, never blocks ------------------------------------------


def test_readback_never_writes_a_parameter():
    master = _FakeMaster(_params(LAND_SPEED=50.0, FENCE_ACTION=0.0, FENCE_ENABLE=0.0))
    read_safety_params(master, timeout_s=0.5)
    assert master.writes == [], "the readback must never write to the flight controller"


def test_module_contains_no_param_set_call():
    """Guards against a future 'helpful' auto-fix being added here."""
    source = inspect.getsource(fc_safety)
    assert "param_set_send" not in source


def test_readback_never_raises_on_bad_parameters():
    master = _FakeMaster(_params(LAND_SPEED=50.0, FENCE_ACTION=0.0))
    report = preflight_readback(master, sitl=False, timeout_s=0.5)
    assert report.problems


def test_readback_never_raises_on_a_dead_link():
    assert preflight_readback(_FakeMaster(), sitl=False, timeout_s=0.02).unread


def test_module_defines_no_blocking_helpers():
    for name in ("assert_safety_lua", "SafetyPreflightError", "require_params"):
        assert not hasattr(fc_safety, name), f"{name} would let software veto a takeoff"


def test_sitl_is_skipped():
    """SITL parameters are whatever the last test left behind."""
    report = preflight_readback(_FakeMaster(), sitl=True)
    assert report.findings == ()
    assert report.notes


# --- The report a human reads --------------------------------------------


def test_report_explains_why_and_how_to_fix():
    report = read_safety_params(_FakeMaster(_params(LAND_SPEED=50.0)), timeout_s=0.5)
    text = format_report(report)
    assert "LAND_SPEED" in text
    assert "Why it matters:" in text
    assert "Mission Planner" in text


def test_clean_report_says_so():
    text = format_report(read_safety_params(_FakeMaster(_params()), timeout_s=0.5))
    assert "as expected" in text


def test_report_flags_an_unreadable_link():
    text = format_report(read_safety_params(_FakeMaster(), timeout_s=0.02))
    assert "Could not read" in text


def test_every_spec_carries_a_reason_and_a_fix():
    """A warning nobody understands gets ignored."""
    for spec in PARAM_SPECS:
        assert spec.why.strip(), spec.name
        assert spec.fix.strip(), spec.name


def test_readback_sends_forced_hud_on_land_speed_mismatch():
    class Hud:
        def __init__(self):
            self.sent = []

        def send(self, message, *, force=False):
            self.sent.append((message, force))

    hud = Hud()
    preflight_readback(
        _FakeMaster(_params(LAND_SPEED=50.0)),
        sitl=False,
        timeout_s=0.5,
        hud=hud,
    )
    assert hud.sent == [("LAND_SPEED mismatch", True)]
