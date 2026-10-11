"""Plain asserts for disconnect growth. No ROS."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "telemetry"))

from telemetry.penalties import PenaltyBook, PenaltyType


def test_one_disconnect_grows_without_using_the_cap() -> None:
    book = PenaltyBook()
    assert book.note_silence(0, 0, armed=True) is None
    first = book.note_silence(30, 0, armed=True)
    assert first is not None
    assert first.points == 5
    assert book.count(PenaltyType.DISCONNECT) == 1
    tick = book.note_silence(45, 0, armed=True)
    assert tick is not None
    assert tick.points == 1
    later = book.note_silence(60, 0, armed=True)
    assert later is not None
    assert later.points == 1
    assert book.count(PenaltyType.DISCONNECT) == 1
    assert book.total_points() == 7


def test_a_new_gap_is_another_occurrence() -> None:
    book = PenaltyBook()
    book.note_silence(30, 0, armed=True)
    book.note_packet(31)
    second = book.note_silence(61, 31, armed=True)
    assert second is not None
    assert second.points == 5
    assert book.count(PenaltyType.DISCONNECT) == 2


if __name__ == "__main__":
    test_one_disconnect_grows_without_using_the_cap()
    test_a_new_gap_is_another_occurrence()
    print("disconnect cases ok")
