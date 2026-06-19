"""GCS HUD / STATUSTEXT helpers."""

from __future__ import annotations

from valiant.autonomy.gcs_hud import (
    GcsHudReporter,
    format_sitl_status_line,
    format_state_transition,
    human_state_label,
    HUD_PREFIX,
)


def test_format_sitl_status_human_readable():
    line = format_sitl_status_line(
        state="APPROACHING",
        target_seen=True,
    )
    assert len(f"{HUD_PREFIX}{line}") <= 50
    assert line == "Moving toward target"


def test_format_sitl_status_multi_target():
    line = format_sitl_status_line(
        state="AIMING",
        target_seen=True,
        target_number=2,
        max_targets=3,
    )
    assert "Target 2/3" in line
    assert "Aiming" in line


def test_human_state_labels():
    assert human_state_label("SEARCHING") == "Scanning for target"
    assert format_state_transition("SEARCHING", "APPROACHING") == "Moving toward target"


def test_gcs_hud_reporter_rate_limits():
    sent: list[str] = []

    class FakeMav:
        class mav:
            @staticmethod
            def statustext_send(severity, text):
                sent.append(text.decode())

    reporter = GcsHudReporter(FakeMav(), interval_s=10.0)
    reporter.send("hello")
    reporter.send("hello")
    reporter.send("other")
    assert len(sent) == 1
    reporter.send("other", force=True)
    assert len(sent) == 2
