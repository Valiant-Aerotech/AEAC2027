"""MAVLink STATUSTEXT encoding and SITL GCS relay options."""

from __future__ import annotations

from pymavlink import mavutil

from valiant.common.mavlink import (
    GcsStatustextOptions,
    encode_statustext,
    gcs_statustext_options_from_cfg,
    send_statustext_for_gcs,
)


def test_encode_statustext_pads_to_50_bytes():
    raw = encode_statustext("hello", "T2: ")
    assert len(raw) == 50
    assert raw.startswith(b"T2: hello")
    assert raw.endswith(b"\0")


def test_encode_statustext_truncates_long_message():
    raw = encode_statustext("x" * 80, "T2: ")
    assert len(raw) == 50
    assert raw.count(b"x") < 80


def test_gcs_statustext_options_sitl_defaults():
    opts = gcs_statustext_options_from_cfg({"gcs_monitor": {}}, sitl=True)
    assert opts.sitl is True
    assert opts.mp_use_autopilot_sysid is True
    assert opts.severity == mavutil.mavlink.MAV_SEVERITY_NOTICE


def test_send_statustext_for_gcs_mp_sysid_duplicate():
    sent: list[tuple[int, int, bytes]] = []

    class FakeMav:
        target_system = 1

        class mav:
            srcSystem = 255
            srcComponent = 191

            @staticmethod
            def statustext_send(severity, text):
                sent.append((FakeMav.mav.srcSystem, FakeMav.mav.srcComponent, text))

    opts = GcsStatustextOptions(sitl=True, mp_use_autopilot_sysid=True)
    send_statustext_for_gcs(FakeMav(), "ping", prefix="T2: ", options=opts)
    assert len(sent) == 2
    assert sent[0][0] == 255
    assert sent[1][0] == 1
    assert sent[1][1] == mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER
