"""Offline unit tests for Task 2 tagtrack modules (no SITL)."""

from __future__ import annotations

from pathlib import Path

import pytest

from valiant.core.geo import offset_lat_lon
from valiant.missions.tagtrack import (
    HOLD_PWM,
    RELEASE_PWM,
    STANDOFF_M,
    StandoffLatch,
    TagTrackPhase,
    TagTrackRunner,
    parse_track_log,
    write_track_log,
)
from valiant.missions.tagtrack.track_log import TrackSample


def test_standoff_latch_idempotent():
    announces: list[str] = []
    latch = StandoffLatch(
        min_m=STANDOFF_M,
        say=lambda msg, force=True: announces.append(msg),
    )
    animal = (50.1, -110.74)
    near = offset_lat_lon(animal[0], animal[1], 50.0, 0.0)
    far = offset_lat_lon(animal[0], animal[1], 100.0, 0.0)

    assert not latch.update(near[0], near[1], animal[0], animal[1])
    assert announces == []

    assert latch.update(far[0], far[1], animal[0], animal[1])
    assert latch.reached
    assert len(announces) == 1

    assert latch.update(far[0], far[1], animal[0], animal[1])
    assert len(announces) == 1  # idempotent


def test_track_csv_round_trip(tmp_path: Path):
    path = tmp_path / "track.csv"
    samples = [
        TrackSample(
            time_utc="2026-09-21T12:00:00Z",
            lat=50.1,
            lon=-110.74,
            alt_m=12.5,
            animal_id="A1",
        ),
        {"time_utc": "2026-09-21T12:00:01Z", "lat": 50.1001, "lon": -110.7401, "alt_m": 12.6, "animal_id": "A1"},
    ]
    write_track_log(path, samples)
    parsed = parse_track_log(path)
    assert len(parsed) == 2
    assert parsed[0].animal_id == "A1"
    assert abs(parsed[0].lat - 50.1) < 1e-6
    assert abs(parsed[1].alt_m - 12.6) < 1e-6


def test_release_pwm_constants():
    assert HOLD_PWM < RELEASE_PWM
    assert 1000 <= HOLD_PWM <= 2000
    assert 1000 <= RELEASE_PWM <= 2000


def test_dry_runner_phases(tmp_path: Path):
    log = tmp_path / "tagtrack.csv"
    holds: list[str] = []
    runner = TagTrackRunner(
        track_log_path=log,
        animal_id="B2",
        hold_fn=lambda: holds.append("held"),
    )
    phase = runner.run_dry_sequence(animal_id="B2")
    assert phase is TagTrackPhase.COMPLETE
    assert runner._samples_logged >= 1
    parsed = parse_track_log(log)
    assert len(parsed) >= 1
    assert parsed[0].animal_id == "B2"
    assert holds == []


def test_set_tracker_servo_none_master():
    from valiant.missions.tagtrack import set_tracker_servo

    assert set_tracker_servo(None, 10, HOLD_PWM) is False


def test_ocr_disabled_leaves_empty_text():
    from valiant.perception.ocr import read_tag_text
    from valiant.perception.types import Detection

    det = Detection(cx=1, cy=1, label="ear_tag", text="XX")
    out = read_tag_text(None, det, enabled=False)
    assert out.text == ""
    assert out.label == "ear_tag"


def test_ocr_missing_backend_soft():
    """When enabled but no crop/backend, never raises SystemExit."""
    from valiant.perception.ocr import read_tag_text
    from valiant.perception.types import Detection

    det = Detection(cx=1, cy=1, label="ear_tag")
    try:
        out = read_tag_text(None, det, enabled=True)
    except SystemExit:
        raise AssertionError("OCR must not SystemExit")
    assert out.text == ""


def test_ocr_backend_optional():
    """Skip full OCR round-trip unless pytesseract or easyocr is installed."""
    from valiant.perception.ocr import ocr_available, read_tag_text
    from valiant.perception.types import Detection

    if not ocr_available():
        pytest.skip("no OCR backend installed")
    np = pytest.importorskip("numpy")
    crop = np.zeros((32, 64, 3), dtype=np.uint8)
    det = Detection(cx=16, cy=16, label="ear_tag")
    out = read_tag_text(crop, det, enabled=True)
    assert isinstance(out.text, str)
