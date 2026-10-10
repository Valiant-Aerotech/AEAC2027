"""1 Hz competition telemetry client.

CONOPS 5.2.3: send whenever armed, never faster than ~1 Hz, never while
disarmed. Appendix E: no wireless outside the flight window, so the default
transport is loopback. A live token opens a websocket only when the wall
clock is plausible.

Transport faults warn and reconnect. They never terminate the aircraft and
never crash the mission loop.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlparse

from telemetry.clock import clock_is_plausible, packet_time
from telemetry.packet import TelemetryPacket
from telemetry.penalties import (
    DISCONNECT_STALE_S,
    LATENCY_LIMIT_S,
    SESSION_GAP_S,
    PenaltyBook,
    PenaltyEvent,
)
from telemetry.secrets import CompetitionSecrets, competition_secrets
from telemetry.traffic import TrafficAircraft, parse_traffic

TARGET_PERIOD_S = 0.9
SEND_PERIOD_S = 0.9
SEND_FLOOR_S = 0.5
WRITE_TIMEOUT_S = 0.3
RECONNECT_WAIT_S = 0.2


def clip_crew_message(message: str) -> str:
    if len(message) <= 50:
        return message
    return message[:47] + "..."


def send_due(last_success: float | None, last_attempt: float | None, now: float) -> bool:
    """True when a live write may start.

    The floor blocks a fast penalty. The period is the normal gap after a
    write that actually finished.
    """
    if last_attempt is not None and now - last_attempt < SEND_FLOOR_S:
        return False
    if last_success is not None and now - last_success < SEND_PERIOD_S:
        return False
    return True


def url_is_websocket(url: str) -> bool:
    return url.startswith("ws://") or url.startswith("wss://")


def websocket_url(url: str, token: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}Authorization={quote(token, safe='')}"


def log_host(url: str) -> str:
    return urlparse(url).hostname or "unknown"


def _is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__


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


class LiveSession:
    """One worker owns the websocket, the send clock, and the traffic list."""

    def __init__(self, client: CompetitionClient, connect: Callable[[], object]):
        self._client = client
        self._connect = connect
        self._ws = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._next_connect_mono = 0.0
        self._reconnect_announced = False
        self.connect_calls = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="telemetry-live", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.0)
        self._drop_socket()

    def pump_once(self) -> None:
        try:
            self._read_available()
            self._maybe_send()
        except Exception as exc:
            self._client._fail_live(str(exc))

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.pump_once()
            self._stop.wait(0.05)

    def _drop_socket(self) -> None:
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def _ensure_socket(self) -> None:
        if self._ws is not None:
            return
        now = time.monotonic()
        if now < self._next_connect_mono:
            raise ConnectionError("reconnect wait")
        self.connect_calls += 1
        self._ws = self._connect()
        settimeout = getattr(self._ws, "settimeout", None)
        if settimeout is not None:
            settimeout(WRITE_TIMEOUT_S)
        self._reconnect_announced = False

    def _read_available(self) -> None:
        ws = self._ws
        if ws is None:
            return
        settimeout = getattr(ws, "settimeout", None)
        if settimeout is not None:
            settimeout(0.05)
        try:
            raw = ws.recv()
        except Exception as exc:
            if _is_timeout(exc):
                return
            self._drop_socket()
            self._client._fail_live(str(exc))
            return
        if not raw:
            return
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(message, dict):
            return
        event = message.get("event")
        client = self._client
        with client._lock:
            if event == "telemetry_ack":
                client._acked = True
            elif event == "traffic":
                try:
                    client.traffic = parse_traffic(message)
                except Exception as exc:
                    client.status.last_error = f"traffic: {exc}"
            elif event == "error":
                client._say(str(message.get("message") or "server error"))

    def _maybe_send(self) -> None:
        client = self._client
        mono = time.monotonic()
        wall = client._stamp()
        with client._lock:
            if not send_due(client._last_send_mono, client._last_attempt_mono, mono):
                return
            packet = client._prepare_live(mono, wall)
            if packet is None:
                return
            client._last_attempt_mono = mono
        try:
            self._ensure_socket()
            payload = json.dumps({"action": "telemetry", "data": packet.to_wire()})
            self._ws.send(payload)
        except Exception as exc:
            self._drop_socket()
            self._next_connect_mono = time.monotonic() + RECONNECT_WAIT_S
            client._fail_live(str(exc), mono=mono)
            return
        client._mark_sent(packet, mono, wall)


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
    transport: LoopbackTransport = field(default_factory=LoopbackTransport)
    penalties: PenaltyBook = field(default_factory=PenaltyBook)
    log_path: Path | None = None
    hud: object | None = None
    period_s: float = TARGET_PERIOD_S
    _last_send_mono: float | None = None
    _last_send_wall: float | None = None
    _last_packet_unix: float | None = None
    _last_attempt_mono: float | None = None
    _armed_since: float | None = None
    _saw_packet_before_arm: bool = False
    status: ClientStatus = field(default_factory=lambda: ClientStatus())
    traffic: tuple[TrafficAircraft, ...] = ()
    _clock: Callable[[], float] = time.time
    _latest: TelemetryPacket | None = None
    _last_valid: TelemetryPacket | None = None
    _holding_fix: bool = False
    _acked: bool = False
    _live: LiveSession | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def telemetry_ready(self) -> bool:
        """True once the server has acked a live packet, or a loopback packet was stored.

        Arm after this. A live socket that accepted bytes and never acked stays false.
        """
        with self._lock:
            if self._live is None:
                return self.status.packets_sent > 0
            return self._acked and self.status.packets_sent > 0

    def _stamp(self) -> float:
        return packet_time(self._clock)

    def _say(self, message: str) -> None:
        try:
            text = clip_crew_message(message)
            print(f"[Comp] {text}")
            hud = self.hud
            if hud is not None and hasattr(hud, "send"):
                hud.send(text, force=True)
        except Exception as exc:
            self._hook_error = f"status: {exc}"

    def _log(self, packet: TelemetryPacket) -> None:
        if self.log_path is None:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(packet.as_dict()) + "\n")
        except Exception as exc:
            self._hook_error = f"log: {exc}"

    def _record(self, event: PenaltyEvent | None) -> None:
        if event is None:
            return
        self.status.last_penalty = event
        self._say(f"{event.kind.value} -{event.points}")

    def _note_armed(self, packet: TelemetryPacket, mono: float) -> bool:
        if packet.armed:
            if self._armed_since is None:
                self._armed_since = mono
                if not self._saw_packet_before_arm and self.status.packets_sent == 0:
                    self._record(self.penalties.startup_armed(mono))
            self.status.armed_seconds = mono - self._armed_since
            return True
        self._armed_since = None
        self.status.armed_seconds = 0.0
        self.status.streaming = False
        return False

    def _score_timing(self, packet: TelemetryPacket, mono: float, wall_now: float) -> None:
        age_s = wall_now - packet.timestamp
        if age_s > DISCONNECT_STALE_S:
            self._record(self.penalties.stale_disconnect(mono, age_s))
        elif age_s > LATENCY_LIMIT_S:
            self._record(self.penalties.timestamp_latency(mono, age_s))
        new_session = (
            self._last_packet_unix is not None
            and packet.timestamp - self._last_packet_unix > SESSION_GAP_S
        )
        if new_session:
            self._record(self.penalties.session_startup(mono))
        elif self._last_send_mono is not None:
            self._record(self.penalties.rate(mono, mono - self._last_send_mono))

    def _prepare_live(self, mono: float, wall_now: float) -> TelemetryPacket | None:
        """Pick the packet a live write may send. Caller holds ``_lock``."""
        latest = self._latest
        if latest is None or not self._note_armed(latest, mono):
            return None
        if latest.validation_reject_reason() is None and latest.gps_valid():
            self._last_valid = latest
            self._holding_fix = False
            chosen = latest
        elif self._last_valid is not None:
            if not self._holding_fix:
                self._holding_fix = True
                self._say("Holding last GPS fix")
            chosen = self._last_valid
        else:
            reject = latest.validation_reject_reason()
            if reject is not None:
                self.status.last_error = reject
                self.status.streaming = False
                self.penalties.note_silence(mono, self._last_send_mono, armed=True)
                return None
            self._record(self.penalties.invalid_gps(mono))
            self.penalties.note_silence(mono, self._last_send_mono, armed=True)
            return None
        stamped = replace(chosen, timestamp=wall_now)
        self._score_timing(stamped, mono, wall_now)
        return stamped

    def _mark_sent(self, packet: TelemetryPacket, mono: float, wall_now: float) -> None:
        with self._lock:
            self._hook_error = None
            self._log(packet)
            self.penalties.note_packet(mono)
            finished = time.monotonic()
            self._last_send_mono = finished
            self._last_attempt_mono = finished
            self._last_send_wall = wall_now
            self._last_packet_unix = packet.timestamp
            self.status.packets_sent += 1
            self.status.streaming = True
            self.status.last_error = self._hook_error
            self._saw_packet_before_arm = True
            if self._live is not None:
                self._live._reconnect_announced = False

    def _fail_live(self, message: str, mono: float | None = None) -> None:
        with self._lock:
            self._hook_error = None
            self.status.last_error = message
            self.status.streaming = False
            if not self._reconnect_announced():
                self._say("Telemetry reconnecting")
            if self._hook_error is not None:
                self.status.last_error = self._hook_error
            if mono is not None:
                self.penalties.note_silence(mono, self._last_send_mono, armed=True)

    def _reconnect_announced(self) -> bool:
        live = self._live
        if live is None:
            return False
        if live._reconnect_announced:
            return True
        live._reconnect_announced = True
        return False

    def tick(
        self,
        packet: TelemetryPacket,
        *,
        now: float | None = None,
        wall: float | None = None,
    ) -> bool:
        """Store the latest sample. Loopback still sends before returning.

        A live tick does not touch the socket. Pass a disarmed flight mode to
        idle without transmitting.
        """
        if self._live is not None:
            with self._lock:
                self._latest = packet
            return False
        return self._tick_loopback(packet, now=now, wall=wall)

    def _tick_loopback(
        self,
        packet: TelemetryPacket,
        *,
        now: float | None = None,
        wall: float | None = None,
    ) -> bool:
        self._hook_error = None
        mono = time.monotonic() if now is None else now
        wall_now = time.time() if wall is None else wall

        if not self._note_armed(packet, mono):
            return False

        if self._last_send_mono is not None and mono - self._last_send_mono < self.period_s * 0.85:
            return False

        reject = packet.validation_reject_reason()
        if reject is not None:
            self.status.last_error = reject
            self.status.streaming = False
            self.penalties.note_silence(mono, self._last_send_mono, armed=True)
            return False

        if not packet.gps_valid():
            self._record(self.penalties.invalid_gps(mono))
            self.penalties.note_silence(mono, self._last_send_mono, armed=True)
            return False

        self._score_timing(packet, mono, wall_now)

        try:
            self.transport.send(packet)
        except Exception as exc:
            self.status.last_error = str(exc)
            self.status.streaming = False
            self._say("Telemetry reconnecting")
            if self._hook_error is not None:
                self.status.last_error = self._hook_error
            self.penalties.note_silence(mono, self._last_send_mono, armed=True)
            return False

        self._log(packet)
        self.penalties.note_packet(mono)
        self._last_send_mono = mono
        self._last_send_wall = wall_now
        self._last_packet_unix = packet.timestamp
        self.status.packets_sent += 1
        self.status.streaming = True
        self.status.last_error = self._hook_error
        self._saw_packet_before_arm = True
        try:
            self.traffic = parse_traffic(self.transport.poll_traffic())
        except Exception as exc:
            self.status.last_error = f"traffic: {exc}"
        return True


def _open_websocket(url: str, token: str):
    from websocket import create_connection

    ws = create_connection(websocket_url(url, token), timeout=5)
    ws.settimeout(WRITE_TIMEOUT_S)
    return ws


def make_client(
    *,
    hud=None,
    log_path: Path | None = None,
    secrets: CompetitionSecrets | None = None,
    clock: Callable[[], float] | None = None,
):
    """Build a client. Loopback unless LIVE=1, a token, a websocket URL, and a plausible clock.

    Pasting a token into `.env` is not enough to transmit. That is deliberate:
    a laptop with a token sitting on the bench must not start a 1 Hz radio
    session outside the flight window.
    """
    cfg = secrets if secrets is not None else competition_secrets()
    stamp = clock or time.time
    client = CompetitionClient(
        uav_id=cfg.uav_id,
        hud=hud,
        log_path=log_path,
        _clock=stamp,
    )
    if not (cfg.live and cfg.token):
        if cfg.live and not cfg.token:
            print("[Comp] LIVE=1 but no token - using loopback")
        else:
            print("[Comp] loopback transport (set AEAC_COMP_LIVE=1 to send)")
        return client
    if not clock_is_plausible(stamp):
        print("[Comp] clock before 2026 - using loopback")
        return client
    if not url_is_websocket(cfg.url):
        print("[Comp] live URL is not a websocket - using loopback")
        return client
    try:
        import websocket  # noqa: F401
    except ImportError:
        print("[Comp] websocket-client missing - using loopback")
        return client
    session = LiveSession(client, lambda: _open_websocket(cfg.url, cfg.token))
    client._live = session
    session.start()
    print(f"[Comp] live transport {log_host(cfg.url)} (token set, LIVE=1)")
    return client
