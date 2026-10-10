"""Crew estimator vs Comp Server Support answers (Waleed, 2026-09-27)."""

from __future__ import annotations

import math

from valiant.comms.competition.client import CompetitionClient, LoopbackTransport
from valiant.comms.competition.packet import TelemetryPacket
from valiant.comms.competition.penalties import PenaltyType


def _packet(**overrides) -> TelemetryPacket:
    base = dict(
        uav_id="vivi",
        timestamp=1_000.0,
        lat=50.1,
        lon=-110.7,
        alt_agl_m=20.0,
        accuracy_m=2.5,
        battery_pct=80.0,
        flight_mode="GUIDED",
        link_quality=1.0,
        armed=True,
    )
    base.update(overrides)
    return TelemetryPacket(**base)


def _client() -> CompetitionClient:
    client = CompetitionClient(uav_id="vivi", transport=LoopbackTransport())
    client.period_s = 0.0
    return client


def _kinds(client: CompetitionClient) -> list[PenaltyType]:
    return [event.kind for event in client.penalties.events]


def test_zero_lat_lon_is_invalid_gps():
    client = _client()
    sent = client.tick(_packet(lat=0.0, lon=0.0), now=0.0, wall=1_000.0)
    assert sent is False
    assert PenaltyType.INVALID_GPS in _kinds(client)
    assert client.status.packets_sent == 0


def test_non_positive_accuracy_is_invalid_gps():
    client = _client()
    client.tick(_packet(accuracy_m=0.0), now=0.0, wall=1_000.0)
    assert PenaltyType.INVALID_GPS in _kinds(client)
    client = _client()
    client.tick(_packet(accuracy_m=-1.0), now=0.0, wall=1_000.0)
    assert PenaltyType.INVALID_GPS in _kinds(client)


def test_large_positive_accuracy_is_valid():
    packet = _packet(accuracy_m=500.0)
    assert packet.gps_valid()
    client = _client()
    assert client.tick(packet, now=0.0, wall=1_000.0) is True
    assert PenaltyType.INVALID_GPS not in _kinds(client)


def test_non_finite_lat_is_rejected_not_invalid_gps():
    packet = _packet(lat=math.nan)
    assert packet.validation_reject_reason() == "non-finite lat"
    client = _client()
    assert client.tick(packet, now=0.0, wall=1_000.0) is False
    assert _kinds(client) == [PenaltyType.STARTUP_ARMED]
    assert client.status.packets_sent == 0


def test_age_20s_is_latency_not_disconnect():
    client = _client()
    assert client.tick(_packet(timestamp=980.0), now=0.0, wall=1_000.0) is True
    assert PenaltyType.TIMESTAMP_LATENCY in _kinds(client)
    assert PenaltyType.DISCONNECT not in _kinds(client)


def test_age_35s_is_disconnect_not_latency():
    client = _client()
    assert client.tick(_packet(timestamp=965.0), now=0.0, wall=1_000.0) is True
    assert PenaltyType.DISCONNECT in _kinds(client)
    assert PenaltyType.TIMESTAMP_LATENCY not in _kinds(client)
    assert client.status.packets_sent == 1


def test_unix_gap_over_30s_is_startup_not_slow_rate():
    client = _client()
    assert client.tick(_packet(timestamp=1_000.0), now=0.0, wall=1_000.0) is True
    assert client.tick(_packet(timestamp=1_040.0), now=5.0, wall=1_040.0) is True
    details = [event.detail for event in client.penalties.events]
    assert "new broadcast session" in details
    assert PenaltyType.SLOW_RATE not in _kinds(client)


def test_stale_packet_does_not_open_a_new_session():
    client = _client()
    assert client.tick(_packet(timestamp=1_000.0), now=0.0, wall=1_000.0) is True
    # 10 s after previous unixTime, but 35 s behind wall.
    assert client.tick(_packet(timestamp=1_010.0), now=2.0, wall=1_045.0) is True
    details = [event.detail for event in client.penalties.events]
    assert "new broadcast session" not in details
    assert PenaltyType.DISCONNECT in _kinds(client)
    assert client.penalties.count(PenaltyType.STARTUP_ARMED) == 1
