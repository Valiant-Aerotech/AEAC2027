"""Rate-limited MAVLink STATUSTEXT for Mission Planner / GCS HUD."""

from __future__ import annotations

import time

from pymavlink import mavutil

from valiant.common.mavlink import GcsStatustextOptions, send_statustext_for_gcs

HUD_PREFIX = "T2: "
MAX_STATUSTEXT_LEN = 50

# Flight-line friendly labels (no sensor numbers).
STATE_HUD_LABELS: dict[str, str] = {
    "SEARCHING": "Scanning for target",
    "REPOSITION": "Heading to next target",
    "APPROACHING": "Moving toward target",
    "AIMING": "Aiming at target",
    "FIRING": "Spraying target",
    "VERIFYING": "Checking spray",
    "CAPTURING": "Taking photo",
    "UPLOADING": "Uploading photo",
    "COMPLETE": "Mission complete",
    "ABORTED": "Mission aborted",
}


def human_state_label(state: str) -> str:
    """Plain-language mission state for GCS Messages."""
    return STATE_HUD_LABELS.get(state, state.replace("_", " ").title())


def format_state_transition(_prev_state: str, new_state: str) -> str:
    """Announce a state change in one short sentence."""
    return human_state_label(new_state)


def format_sitl_status_line(
    *,
    state: str,
    target_seen: bool = False,
    target_number: int = 1,
    max_targets: int | None = None,
    **_ignored,
) -> str:
    """Periodic mission status for STATUSTEXT (body only, no prefix)."""
    label = human_state_label(state)
    if state == "SEARCHING" and not target_seen:
        label = "Scanning for target"
    elif state == "APPROACHING" and target_seen:
        label = "Moving toward target"
    elif state == "AIMING":
        label = "Aiming at target"
    if max_targets is not None and max_targets > 1:
        prefix = f"Target {target_number}/{max_targets}: "
        line = f"{prefix}{label}"
    else:
        line = label
    return line[: MAX_STATUSTEXT_LEN - len(HUD_PREFIX.encode())]


class GcsHudReporter:
    """Send companion STATUSTEXT (max 50 chars) without flooding the GCS."""

    def __init__(
        self,
        master: mavutil.mavfile,
        *,
        prefix: str = HUD_PREFIX,
        interval_s: float = 3.0,
        options: GcsStatustextOptions | None = None,
    ):
        self._master = master
        self._prefix = prefix
        self._interval_s = max(0.5, interval_s)
        self._options = options or GcsStatustextOptions()
        self._last_sent = 0.0
        self._last_body = ""
        self._mirror: mavutil.mavfile | None = None
        mirror_url = self._options.sitl_mp_mirror
        if mirror_url:
            try:
                self._mirror = mavutil.mavlink_connection(mirror_url)
            except Exception as exc:
                print(f"[GCS] WARN: sitl_mp_mirror connect failed ({mirror_url}): {exc}")

    def close(self) -> None:
        if self._mirror is not None:
            try:
                self._mirror.close()
            except Exception:
                pass
            self._mirror = None

    def send(self, message: str, *, force: bool = False) -> None:
        body = message.strip()
        if not body:
            return
        max_body = MAX_STATUSTEXT_LEN - len(self._prefix.encode("utf-8", errors="ignore"))
        body = body[:max_body]
        now = time.time()
        if not force:
            if body == self._last_body:
                return
            if now - self._last_sent < self._interval_s:
                return
        send_statustext_for_gcs(
            self._master,
            body,
            prefix=self._prefix,
            options=self._options,
            mirror=self._mirror,
        )
        self._last_body = body
        self._last_sent = now
