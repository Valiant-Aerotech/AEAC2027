#!/usr/bin/env python3
"""Bench-test SafetyMonitor with simulated MAVLink messages (no drone)."""

from __future__ import annotations

import time

from valiant.autonomy.safety.monitor import SafetyMonitor
from valiant.common.config import load_config


class _FakeMsg:
    def __init__(self, msg_type: str, **fields):
        self._type = msg_type
        for key, value in fields.items():
            setattr(self, key, value)

    def get_type(self) -> str:
        return self._type


class _FakeMaster:
    def __init__(self, messages: list):
        self._messages = list(messages)

    def recv_match(self, blocking=False, type=None, **kwargs):
        if not self._messages:
            return None
        if type is None:
            return self._messages.pop(0)
        allowed = type if isinstance(type, (list, tuple)) else [type]
        for idx, msg in enumerate(self._messages):
            if msg.get_type() in allowed:
                return self._messages.pop(idx)
        return None


def main() -> int:
    cfg = load_config("vion")
    cfg["safety"]["mission_timeout_s"] = 0

    master = _FakeMaster(
        [
            _FakeMsg("SYS_STATUS", battery_remaining=15),
        ]
    )
    monitor = SafetyMonitor(master, cfg, sim=False)
    abort = monitor.check()
    if abort is None or "battery" not in abort.reason:
        print("FAIL: expected battery abort")
        return 1
    print(f"OK battery abort: {abort.reason}")

    master2 = _FakeMaster([_FakeMsg("FENCE_STATUS", breach_status=1)])
    monitor2 = SafetyMonitor(master2, cfg, sim=False)
    abort2 = monitor2.check()
    if abort2 is None or "geofence" not in abort2.reason:
        print("FAIL: expected geofence abort")
        return 1
    print(f"OK geofence abort: {abort2.reason}")

    cfg_timeout = load_config("vion")
    cfg_timeout["safety"]["mission_timeout_s"] = 1
    monitor3 = SafetyMonitor(None, cfg_timeout, sim=False)
    time.sleep(1.1)
    abort3 = monitor3.check()
    if abort3 is None or "timeout" not in abort3.reason:
        print("FAIL: expected mission timeout abort")
        return 1
    print(f"OK timeout abort: {abort3.reason}")

    print("Safety bench test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
