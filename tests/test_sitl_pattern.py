"""Unit tests for SITL pattern leg definitions."""

from __future__ import annotations

from valiant.autonomy.sitl_pattern import DEFAULT_PATTERN


def test_default_pattern_has_seven_legs():
    assert len(DEFAULT_PATTERN) == 7


def test_default_pattern_sequence():
    kinds = [leg.kind for leg in DEFAULT_PATTERN]
    assert kinds == ["forward", "turn", "forward", "turn", "forward", "turn", "forward"]
    assert DEFAULT_PATTERN[0].value == 10.0
    assert DEFAULT_PATTERN[1].value == 90.0
    assert DEFAULT_PATTERN[3].value == -180.0
    assert DEFAULT_PATTERN[6].value == 10.0
