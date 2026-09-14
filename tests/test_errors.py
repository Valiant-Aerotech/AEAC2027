"""Error-handling contract: typed errors, no SystemExit in the library, hold on fault."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from valiant.core.config import load_config
from valiant.core.errors import (
    ConfigError,
    FlightPreconditionError,
    PerceptionDegraded,
    ValiantError,
    clip_crew_message,
)
from valiant.core.flight.fc_safety import preflight_readback
from valiant.perception.detect.subframe_yolo import SubframeYoloDetector


def test_clip_crew_message_fits_statustext():
    assert clip_crew_message("ok") == "ok"
    long = "x" * 80
    clipped = clip_crew_message(long)
    assert len(clipped) <= 46
    assert clipped.endswith("...")


def test_valiant_error_clips_crew_message():
    err = ValiantError("a very long explanation " * 10, crew_message="a very long explanation " * 10)
    assert len(err.crew_message) <= 46


def test_config_error_on_broken_yaml(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("this: [is: not: yaml", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        load_config(bad)
    assert "Invalid YAML" in caught.value.detail
    assert caught.value.crew_message


def test_config_error_on_missing_explicit_file():
    with pytest.raises(ConfigError):
        load_config("config/does_not_exist.yaml")


def test_library_never_raises_systemexit():
    """CLI maps exit codes. A library SystemExit strands the aircraft unheld."""
    root = Path("src/valiant")
    offenders = [
        str(path.as_posix())
        for path in root.rglob("*.py")
        if "raise SystemExit" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_preflight_readback_never_raises():
    report = preflight_readback(MagicMock(), sitl=False, timeout_s=0.02)
    assert report.unread


def test_preflight_readback_sends_one_forced_hud_message():
    class Hud:
        def __init__(self):
            self.sent = []

        def send(self, message, *, force=False):
            self.sent.append((message, force))

    hud = Hud()
    # Dead link: unread, not a value mismatch.
    preflight_readback(MagicMock(), sitl=False, timeout_s=0.02, hud=hud)
    assert hud.sent
    assert hud.sent[0][1] is True


def test_missing_yolo_model_sets_degraded():
    det = SubframeYoloDetector({"cv": {"models": {"primary": "models/no_such_model.onnx"}}})
    frame = __import__("numpy").zeros((480, 640, 3), dtype="uint8")
    assert det.detect_all(frame) == []
    assert det.degraded is not None
    assert "model" in det.degraded.lower()


def test_orbit_run_holds_on_uncaught_exception(monkeypatch):
    from valiant.core.motion.field_orbit import FieldOrbitRunner

    monkeypatch.setattr(
        "valiant.core.motion.field_orbit.request_guided_telemetry_streams",
        lambda _master: None,
    )
    runner = FieldOrbitRunner(MagicMock(), {"field_orbit": {}, "safety": {}}, skip_standby=True)
    runner._execute_mission = MagicMock(side_effect=RuntimeError("boom"))
    runner._motion.finish = MagicMock()
    runner._motion.say = MagicMock()
    runner._motion.stop_stream = MagicMock()
    with pytest.raises(RuntimeError, match="boom"):
        runner.run()
    runner._motion.finish.assert_called()
    message = runner._motion.finish.call_args.kwargs.get("message") or ""
    assert "holding" in message.lower()


def test_flight_precondition_is_a_valiant_error():
    err = FlightPreconditionError("Timed out waiting for mode GUIDED", crew_message="GUIDED timeout")
    assert isinstance(err, ValiantError)
    assert err.crew_message == "GUIDED timeout"


def test_perception_degraded_is_a_valiant_error():
    err = PerceptionDegraded("camera failed", crew_message="Camera failed")
    assert isinstance(err, ValiantError)
