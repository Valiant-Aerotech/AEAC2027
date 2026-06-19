"""Tests for FC safety.lua preflight."""

from __future__ import annotations

from valiant.autonomy.flight.fc_safety import (
    SafetyLuaReport,
    fetch_param_value,
    verify_safety_lua,
)


class _ParamMsg:
    def __init__(self, name: str, value: float, sysid: int = 1):
        self.param_id = name.encode("utf-8")
        self.param_value = value
        self._sysid = sysid

    def get_srcSystem(self) -> int:
        return self._sysid


class _FakeMaster:
    def __init__(self, messages: list | None = None):
        self.target_system = 1
        self.target_component = 1
        self._messages = list(messages or [])
        self.mav = self

    def param_request_read_send(self, *args, **kwargs):
        del args, kwargs

    def recv_match(self, *, type, blocking=True, timeout=0.5):
        del type, blocking, timeout
        if not self._messages:
            return None
        return self._messages.pop(0)


def test_fetch_param_value_reads_scr_enable():
    master = _FakeMaster([_ParamMsg("SCR_ENABLE", 1.0)])
    assert fetch_param_value(master, "SCR_ENABLE", timeout_s=1.0) == 1.0


def test_verify_safety_lua_fails_when_scr_disabled():
    master = _FakeMaster([_ParamMsg("SCR_ENABLE", 0.0)])
    cfg = {"safety": {"require_lua_safety": True, "verify_lua_file": False}}
    report = verify_safety_lua(master, cfg, sitl=False)
    assert not report.ok
    assert any("SCR_ENABLE" in e for e in report.errors)


def test_verify_safety_lua_skipped_for_sitl():
    report = verify_safety_lua(_FakeMaster(), {}, sitl=True)
    assert report.ok


def test_verify_safety_lua_ok_when_scr_enabled_no_ftp():
    master = _FakeMaster([_ParamMsg("SCR_ENABLE", 1.0)])
    cfg = {"safety": {"require_lua_safety": True, "verify_lua_file": False}}
    report = verify_safety_lua(master, cfg, sitl=False)
    assert report.ok
