"""GCS HUD / STATUSTEXT helpers."""

from __future__ import annotations

from valiant.autonomy.gcs_hud import GcsHudReporter, format_sitl_status_line, HUD_PREFIX


def test_format_sitl_status_fits_statustext():
    line = format_sitl_status_line(
        state="APPROACHING",
        target_seen=True,
        metric_range_m=1.2,
        wall_range_m=1.5,
        pose_n=3.4,
        pose_e=0.1,
        alt_m=4.8,
        vel_n=0.12,
        motion_rule="follow",
        motion_reason="visual follow",
    )
    assert len(f"{HUD_PREFIX}{line}") <= 50
    assert "APPROACH" in line
    assert "tgt" in line


def test_format_sitl_status_shows_blockers():
    line = format_sitl_status_line(
        state="AIMING",
        target_seen=True,
        metric_range_m=0.9,
        fire_blockers=("not_aimed", "too_far_wall"),
    )
    assert "blk:" in line


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
