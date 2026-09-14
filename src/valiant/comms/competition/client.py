"""1 Hz competition telemetry client.

CONOPS 5.2.3: send whenever armed, never faster than ~1 Hz, never while
disarmed. Appendix E: no wireless outside the flight window, so the default
transport is loopback. Swap in a live transport when a token exists
(docs/conops-2027.md).

Transport faults warn and reconnect. They never terminate the aircraft and
never crash the mission loop.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from valiant.comms.competition.packet import TelemetryPacket
from valiant.comms.competition.penalties import PenaltyBook, PenaltyEvent
from valiant.comms.competition.traffic import TrafficAircraft, parse_traffic
from valiant.core.errors import clip_crew_message
from valiant.core.secrets import CompetitionSecrets, competition_secrets

TARGET_HZ = 1.0
TARGET_PERIOD_S = 1.0 / TARGET_HZ


class Transport(Protocol):
    def send(self, packet: TelemetryPacket) -> None: ...

    def poll_traffic(self) -> list[dict]: ...


class LoopbackTransport:
    """In-memory sink. Legal to run outside the flight window."""

    def __init__(self):
        self.sent: list[TelemetryPacket] = []
        self.traffic_feed: list[dict] = []
        self.fail_next = 0

    def send(self, packet: TelemetryPacket) -> None:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ConnectionError("loopback injected failure")
        self.sent.append(packet)

    def poll_traffic(self) -> list[dict]:
        return list(self.traffic_feed)


class HttpTransport:
    """POST packets to the competition server. Only constructed when LIVE=1.

    Uses the stdlib so a missing pip package cannot take down the mission
    loop. Failures raise and the client reconnects; they never terminate.
    """

    def __init__(self, url: str, token: str, *, timeout_s: float = 2.0):
        self.url = url.rstrip("/")
        self._token = token
        self.timeout_s = timeout_s

    def __repr__(self) -> str:
        return f"HttpTransport(url={self.url!r})"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def send(self, packet: TelemetryPacket) -> None:
        import json as _json
        import urllib.error
        import urllib.request

        body = _json.dumps(packet.as_dict()).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}/telemetry",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                resp.read()
        except urllib.error.URLError as exc:
            raise ConnectionError(str(exc.reason if hasattr(exc, "reason") else exc)) from exc

    def poll_traffic(self) -> list[dict]:
        import json as _json
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            f"{self.url}/traffic",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = _json.loads(resp.read().decode("utf-8") or "[]")
        except urllib.error.URLError as exc:
            raise ConnectionError(str(exc.reason if hasattr(exc, "reason") else exc)) from exc
        if isinstance(payload, dict):
            payload = payload.get("traffic", payload.get("aircraft", []))
        if not isinstance(payload, list):
            return []
        return payload


@dataclass
class ClientStatus:
    streaming: bool = False
    armed_seconds: float = 0.0
    packets_sent: int = 0
    last_error: str | None = None
    last_penalty: PenaltyEvent | None = None


@dataclass
class CompetitionClient:
    uav_id: str
    transport: Transport = field(default_factory=LoopbackTransport)
    penalties: PenaltyBook = field(default_factory=PenaltyBook)
    log_path: Path | None = None
    hud: object | None = None
    period_s: float = TARGET_PERIOD_S
    _last_send_mono: float | None = None
    _last_send_wall: float | None = None
    _armed_since: float | None = None
    _saw_packet_before_arm: bool = False
    status: ClientStatus = field(default_factory=ClientStatus)
    traffic: tuple[TrafficAircraft, ...] = ()

    def telemetry_ready(self) -> bool:
        """True after at least one packet has gone out. Arm after this."""
        return self.status.packets_sent > 0

    def _say(self, message: str) -> None:
        text = clip_crew_message(message)
        print(f"[Comp] {text}")
        hud = self.hud
        if hud is not None and hasattr(hud, "send"):
            hud.send(text, force=True)

    def _log(self, packet: TelemetryPacket) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(packet.as_dict()) + "\n")

    def _record(self, event: PenaltyEvent | None) -> None:
        if event is None:
            return
        self.status.last_penalty = event
        self._say(f"{event.kind.value} -{event.points}")

    def tick(
        self,
        packet: TelemetryPacket,
        *,
        now: float | None = None,
        wall: float | None = None,
    ) -> bool:
        """Attempt one send. Returns True if a packet went out.

        Safe to call faster than 1 Hz: extra calls are no-ops until the period
        elapses. Call with ``packet.armed=False`` to idle without transmitting.
        """
        mono = time.monotonic() if now is None else now
        wall_now = time.time() if wall is None else wall

        if packet.armed:
            if self._armed_since is None:
                self._armed_since = mono
                if not self._saw_packet_before_arm and self.status.packets_sent == 0:
                    self._record(self.penalties.startup_armed(mono))
            self.status.armed_seconds = mono - self._armed_since
        else:
            self._armed_since = None
            self.status.armed_seconds = 0.0
            self.status.streaming = False
            return False

        if self._last_send_mono is not None and mono - self._last_send_mono < self.period_s * 0.85:
            return False

        if not packet.gps_valid():
            self._record(self.penalties.invalid_gps(mono))
            self.penalties.note_silence(mono, self._last_send_mono, armed=True)
            return False

        if self._last_send_mono is not None:
            self._record(self.penalties.rate(mono, mono - self._last_send_mono))
        latency = abs(wall_now - packet.timestamp)
        self._record(self.penalties.timestamp_latency(mono, latency))

        try:
            self.transport.send(packet)
        except Exception as exc:
            self.status.last_error = str(exc)
            self.status.streaming = False
            self._say("Telemetry reconnecting")
            self.penalties.note_silence(mono, self._last_send_mono, armed=True)
            return False

        self._log(packet)
        self.penalties.note_packet(mono)
        self._last_send_mono = mono
        self._last_send_wall = wall_now
        self.status.packets_sent += 1
        self.status.streaming = True
        self.status.last_error = None
        self._saw_packet_before_arm = True
        try:
            self.traffic = parse_traffic(self.transport.poll_traffic())
        except Exception as exc:
            self.status.last_error = f"traffic: {exc}"
        return True


def make_client(*, hud=None, log_path: Path | None = None, secrets: CompetitionSecrets | None = None):
    """Build a client. Loopback unless LIVE=1 *and* a token is present.

    Pasting a token into `.env` is not enough to transmit. That is deliberate:
    a laptop with a token sitting on the bench must not start a 1 Hz radio
    session outside the flight window.
    """
    cfg = secrets if secrets is not None else competition_secrets()
    if cfg.live and cfg.token:
        transport: Transport = HttpTransport(cfg.url, cfg.token)
        print(f"[Comp] live transport {cfg.url} (token set, LIVE=1)")
    else:
        transport = LoopbackTransport()
        if cfg.live and not cfg.token:
            print("[Comp] LIVE=1 but no token - using loopback")
        else:
            print("[Comp] loopback transport (set AEAC_COMP_LIVE=1 to send)")
    return CompetitionClient(
        uav_id=cfg.uav_id,
        transport=transport,
        hud=hud,
        log_path=log_path,
    )
