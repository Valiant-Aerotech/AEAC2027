"""Read back flight-controller safety parameters. Warn-only, never writes.

The flight controller owns safety configuration and Mission Planner is how it
gets configured. This module exists to answer one question on the flight line:
*is the aircraft in front of us actually set up the way we think it is?*

Three rules, and they are the whole design:

1. **Never write.** Not one ``param_set``. If a parameter is wrong, a human
   fixes it in Mission Planner and reboots. Silent reconfiguration from a
   companion computer means the aircraft that passed the FRR is not the
   aircraft that took off.
2. **Never block arming.** This prints warnings and returns a report. The
   pilot decides whether to fly. Software that refuses to arm is software that
   can strand us on the flight line during a scored window, and CONOPS 6.2
   scores "ease of setup" - a companion that can veto a takeoff is not easy to
   set up.
3. **Warn loudly.** Silence on a real problem is worse than noise.

What we check and why
---------------------
``LAND_SPEED`` is the one that matters most. CONOPS 4.5 requires a flight
termination system, which we satisfy with ``FENCE_ACTION = 2`` (Always Land).
ArduPilot's default ``LAND_SPEED`` is 50 cm/s, so a termination at the 100 m
ceiling would take over three minutes of drifting descent. That is not a
termination. At 200 cm/s it is about 50 seconds, which a judge will accept as
immediate. Same reasoning for the rest: each entry says what breaks if it is
wrong, because a warning nobody understands gets ignored.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pymavlink import mavutil

from valiant.core.mavlink_io import mavlink_io


@dataclass(frozen=True)
class ParamSpec:
    """One parameter we expect, and what goes wrong if it is not set."""

    name: str
    # Returns None if acceptable, else a short description of what was found.
    check: object
    why: str
    fix: str
    # Advisory parameters warn on mismatch; critical ones are called out first.
    critical: bool = True


@dataclass(frozen=True)
class Finding:
    name: str
    value: float | None
    problem: str | None
    spec: ParamSpec

    @property
    def ok(self) -> bool:
        return self.value is not None and self.problem is None

    @property
    def unread(self) -> bool:
        return self.value is None


@dataclass(frozen=True)
class PreflightReport:
    """The result of a readback. Advisory: nothing here stops a flight."""

    findings: tuple[Finding, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def problems(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.problem is not None)

    @property
    def unread(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.unread)

    @property
    def clean(self) -> bool:
        """Everything read back as expected. Not a gate, just a summary."""
        return not self.problems and not self.unread


def _expect(value: float, expected: float) -> str | None:
    if abs(value - expected) > 0.5:
        return f"is {value:.0f}, expected {expected:.0f}"
    return None


def _at_least(value: float, minimum: float) -> str | None:
    if value < minimum - 0.5:
        return f"is {value:.0f}, expected at least {minimum:.0f}"
    return None


def _has_bits(value: float, bits: int, labels: str) -> str | None:
    if int(value) & bits != bits:
        return f"is {int(value)}, missing {labels} (need bit value {bits})"
    return None


def _nonzero(value: float) -> str | None:
    if abs(value) < 0.5:
        return "is disabled (0)"
    return None


# Ordered roughly by how badly the flight goes if it is wrong.
PARAM_SPECS: tuple[ParamSpec, ...] = (
    ParamSpec(
        name="LAND_SPEED",
        check=lambda v: _at_least(v, 200.0),
        why=(
            "Descent rate used by the fence Always Land action, which is our "
            "CONOPS 4.5 flight termination system. At the 50 cm/s default a "
            "termination from 100 m takes over three minutes."
        ),
        fix="Mission Planner, Full Parameter List, LAND_SPEED = 200, Write.",
    ),
    ParamSpec(
        name="FENCE_ACTION",
        # 2 = Always Land. 1 (RTL or Land) flies the aircraft home instead of
        # terminating, which is not what CONOPS 4.5 asks for.
        check=lambda v: _expect(v, 2.0),
        why=(
            "What the autopilot does on a fence breach. Only 2 (Always Land) "
            "terminates. 1 (RTL or Land) flies home, which is a breach "
            "response, not a termination."
        ),
        fix="Mission Planner, Full Parameter List, FENCE_ACTION = 2, Write.",
    ),
    ParamSpec(
        name="FENCE_ENABLE",
        check=_nonzero,
        why="With the fence disabled, nothing enforces the competition boundary.",
        fix="Mission Planner, Full Parameter List, FENCE_ENABLE = 1, Write.",
    ),
    ParamSpec(
        name="FENCE_TYPE",
        # Bitmask: 1 = max altitude, 2 = circle, 4 = polygon.
        check=lambda v: _has_bits(v, 5, "max-altitude (1) and polygon (4)"),
        why=(
            "Which fences are active. We need the polygon for the Appendix C "
            "boundary and the altitude fence for the 100 m ceiling."
        ),
        fix="Mission Planner, Full Parameter List, FENCE_TYPE = 5, Write.",
    ),
    ParamSpec(
        name="FENCE_ALT_MAX",
        check=lambda v: _expect(v, 100.0),
        why="The CONOPS 4.2 and CARs ceiling, 100 m AGL.",
        fix="Mission Planner, Full Parameter List, FENCE_ALT_MAX = 100, Write.",
    ),
    ParamSpec(
        name="FENCE_TOTAL",
        # Six Appendix C vertices; ArduPilot may store a closing point.
        check=lambda v: _at_least(v, 6.0),
        why=(
            "How many fence points the autopilot is holding. Below six, the "
            "Appendix C polygon was never written - the boundary in Mission "
            "Planner's map is not the boundary being enforced."
        ),
        fix=(
            "python tools/valiant.py boundary export, then load the .poly in "
            "Mission Planner (Plan, FENCE, Load Polygon, Fence Inclusion, Write)."
        ),
    ),
    ParamSpec(
        name="FS_THR_ENABLE",
        check=_nonzero,
        why="Without the throttle failsafe, losing the transmitter does nothing.",
        fix="Mission Planner, Full Parameter List, FS_THR_ENABLE = 1 (RTL), Write.",
    ),
    ParamSpec(
        name="SCR_ENABLE",
        check=_nonzero,
        why="Lua scripting, which runs the RC8 kill switch in hardware/lua/safety.lua.",
        fix="Mission Planner, Full Parameter List, SCR_ENABLE = 1, reboot the FC.",
    ),
    ParamSpec(
        name="FS_GCS_ENABLE",
        check=_nonzero,
        why=(
            "Ground station failsafe. The companion talks to the crew over this "
            "link, so losing it means nobody can see what the aircraft is doing."
        ),
        fix="Mission Planner, Full Parameter List, FS_GCS_ENABLE = 1, Write.",
        critical=False,
    ),
)


def fetch_param_value(
    master: mavutil.mavfile,
    name: str,
    *,
    timeout_s: float = 5.0,
) -> float | None:
    """Read one FC parameter by name. Returns None if it does not answer."""
    target_sys = getattr(master, "target_system", 0)
    target_comp = getattr(master, "target_component", 0)
    param_id = name.encode("utf-8")[:16]
    with mavlink_io(master):
        master.mav.param_request_read_send(target_sys, target_comp, param_id, -1)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if msg is None or msg.get_srcSystem() != target_sys:
            continue
        raw_id = msg.param_id
        if isinstance(raw_id, bytes):
            pid = raw_id.decode("utf-8", errors="ignore").rstrip("\x00")
        else:
            pid = str(raw_id).rstrip("\x00")
        if pid == name:
            return float(msg.param_value)
    return None


def read_safety_params(
    master: mavutil.mavfile,
    *,
    specs: tuple[ParamSpec, ...] = PARAM_SPECS,
    timeout_s: float = 3.0,
) -> PreflightReport:
    """Read every safety parameter and compare it with what we expect.

    Reads only. A parameter that does not answer becomes an unread finding
    rather than an error, because a slow link is not a safety problem.
    """
    findings = []
    for spec in specs:
        value = fetch_param_value(master, spec.name, timeout_s=timeout_s)
        problem = None if value is None else spec.check(value)
        findings.append(Finding(name=spec.name, value=value, problem=problem, spec=spec))
    return PreflightReport(findings=tuple(findings))


def format_report(report: PreflightReport) -> str:
    """Render the readback for a terminal. Warnings carry their own fix."""
    lines = ["Flight controller safety readback (advisory - nothing is written)"]

    for finding in report.findings:
        if finding.unread:
            lines.append(f"  ?    {finding.name:<16} no response from the flight controller")
        elif finding.ok:
            lines.append(f"  ok   {finding.name:<16} {finding.value:.0f}")
        else:
            lines.append(f"  WARN {finding.name:<16} {finding.problem}")

    problems = report.problems
    if problems:
        lines.append("")
        lines.append(f"{len(problems)} parameter(s) are not what we expect:")
        for finding in problems:
            lines.append(f"\n  {finding.name}: {finding.problem}")
            lines.append(f"    Why it matters: {finding.spec.why}")
            lines.append(f"    Fix: {finding.spec.fix}")

    if report.unread:
        names = ", ".join(f.name for f in report.unread)
        lines.append(f"\nCould not read: {names}. Check the MAVLink link to the FC.")

    if report.clean:
        lines.append("\nAll safety parameters read back as expected.")
    else:
        lines.append("\nThis is advisory only. The pilot decides whether to fly.")

    lines.extend(report.notes)
    return "\n".join(lines)


def preflight_readback(
    master: mavutil.mavfile,
    *,
    sitl: bool = False,
    timeout_s: float = 3.0,
    hud=None,
) -> PreflightReport:
    """Run the readback and print it. Always returns; never raises, never writes.

    SITL is skipped: the simulator's parameters are whatever the last test left
    behind, so warning about them trains the crew to ignore warnings.
    """
    if sitl:
        report = PreflightReport(notes=("Parameter readback skipped in SITL.",))
        print(f"[Preflight] {report.notes[0]}")
        return report

    report = read_safety_params(master, timeout_s=timeout_s)
    print(format_report(report))
    if hud is not None:
        critical = next((f for f in report.problems if f.spec.critical), None)
        if critical is not None:
            print(f"[Crew] {critical.name} mismatch")
            hud.send(f"{critical.name} mismatch", force=True)
        elif report.unread:
            print("[Crew] FC params unread")
            hud.send("FC params unread", force=True)
    return report


__all__ = [
    "PARAM_SPECS",
    "Finding",
    "ParamSpec",
    "PreflightReport",
    "fetch_param_value",
    "format_report",
    "preflight_readback",
    "read_safety_params",
]
