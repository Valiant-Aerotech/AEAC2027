"""Rate-limited MAVLink STATUSTEXT for Mission Planner / GCS HUD."""

from __future__ import annotations

from valiant_mav.hud import (
    HUD_PREFIX,
    MAX_STATUSTEXT_LEN,
    GcsHudReporter,
    notify_crew,
)

__all__ = [
    "GcsHudReporter",
    "HUD_PREFIX",
    "MAX_STATUSTEXT_LEN",
    "ORBIT_PHASE_LABELS",
    "STATE_HUD_LABELS",
    "format_orbit_status",
    "format_sitl_status_line",
    "format_state_transition",
    "human_state_label",
    "notify_crew",
]

# Flight-line friendly labels (no sensor numbers). Keys cover both mission
# runners; unknown states fall through to the raw state name.
STATE_HUD_LABELS: dict[str, str] = {
    # Task 1 - timed course and herd survey
    "LAPS": "Flying lap course",
    "TRANSIT": "Transiting to survey area",
    "SWEEPING": "Sweeping survey area",
    "IDENTIFYING": "Reading ear tags",
    "REPORTING": "Writing survey report",
    # Task 2 - tracker attachment, tracking, sampling
    "SEARCHING": "Scanning for target",
    "APPROACHING": "Moving toward target",
    "AIMING": "Lining up on target",
    "ATTACHING": "Attaching tracker",
    "STANDOFF": "Holding 100 m standoff",
    "TRACKING": "Logging animal track",
    "COLLECTING": "Collecting sample",
    "DELIVERING": "Returning sample to pad",
    # Shared
    "RETREAT": "Backing away from target",
    "RETURNING": "Returning to launch",
    "COMPLETE": "Mission complete",
    "ABORTED": "Mission aborted",
}

ORBIT_PHASE_LABELS: dict[str, str] = {
    "STANDBY": "Waiting for GUIDED",
    "ALT_HOLD": "Climbing to altitude",
    "FORWARD": "Flying forward",
    "ORBIT": "Orbiting",
    "RETURN_CENTER": "Returning to center",
    "LOITER": "Loiter - manual control",
    "DONE": "Orbit complete",
    "ABORT": "Aborted - left GUIDED",
}


def format_orbit_status(phase: str, lap: float, laps_target: float) -> str:
    """Human-readable orbit status for GCS Messages."""
    if phase == "ORBIT":
        lap_disp = min(int(lap) + 1, int(laps_target))
        return f"Lap {lap_disp}/{int(laps_target)}"
    return ORBIT_PHASE_LABELS.get(phase, phase.replace("_", " ").title())


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

