"""Plain asserts for packet validation and the wire payload. No ROS."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "telemetry"))

from telemetry.clock import clock_is_plausible
from telemetry.packet import TelemetryPacket


def sample(**changes) -> TelemetryPacket:
    packet = TelemetryPacket.now(
        "valiant-1",
        lat=50.09807,
        lon=-110.73566,
        alt_agl_m=45.0,
        accuracy_m=1.2,
        battery_pct=90.0,
        flight_mode="armed-automatic",
        link_quality=1,
        clock=lambda: 1_800_000_000.0,
    )
    return replace(packet, **changes) if changes else packet


def test_armed_follows_mode() -> None:
    assert sample().armed is True
    assert sample(flight_mode="armed-pilot").armed is True
    assert sample(flight_mode="idle").armed is False
    assert sample(flight_mode="off").armed is False


def test_rejects_bad_fields() -> None:
    assert sample().validation_reject_reason() is None
    assert sample(flight_mode="AUTO").validation_reject_reason() == "flight mode"
    assert sample(battery_pct=101).validation_reject_reason() == "battery"
    assert sample(battery_pct=-1).validation_reject_reason() == "battery"
    assert sample(link_quality=0.5).validation_reject_reason() == "link status"
    assert sample(link_quality=0).validation_reject_reason() is None
    assert sample(link_quality=1).validation_reject_reason() is None


def test_wire_is_camel_case_and_record_is_not() -> None:
    packet = sample()
    wire = packet.to_wire(unix_time=1_800_000_001.0)
    assert wire["uavId"] == "valiant-1"
    assert wire["unixTime"] == 1_800_000_001.0
    assert wire["latitude"] == packet.lat
    assert wire["longitude"] == packet.lon
    assert wire["altitudeAGL"] == 45.0
    assert wire["horizontalPositionAccuracy"] == 1.2
    assert wire["verticalPositionAccuracy"] == 1.2
    assert wire["batteryPercentage"] == 90.0
    assert wire["mode"] == "armed-automatic"
    assert wire["telemetryLinkStatus"] == 1
    assert wire["rcLinkStatus"] == 1
    assert sample(link_quality=0).to_wire()["rcLinkStatus"] == 0
    record = packet.as_dict()
    assert record["flight_mode"] == "armed-automatic"
    assert "uavId" not in record
    assert TelemetryPacket.from_dict(record).lat == packet.lat


def test_clock_gate() -> None:
    assert clock_is_plausible(lambda: 1_000_000.0) is False
    assert clock_is_plausible(lambda: 1_800_000_000.0) is True


if __name__ == "__main__":
    test_armed_follows_mode()
    test_rejects_bad_fields()
    test_wire_is_camel_case_and_record_is_not()
    test_clock_gate()
    print("packet cases ok")
