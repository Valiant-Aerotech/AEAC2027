"""Tests for companion LAND command."""

from __future__ import annotations

from valiant.common.mavlink import send_land


class _FakeMav:
    def __init__(self):
        self.target_system = 1
        self.target_component = 1
        self._mode = None
        self._mapping = {"LAND": 9}

    def mode_mapping(self):
        return dict(self._mapping)

    def set_mode(self, mode_id: int) -> None:
        self._mode = mode_id


def test_send_land_sets_mode():
    master = _FakeMav()
    send_land(master)
    assert master._mode == 9
