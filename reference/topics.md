# Lookup by job

Start here if you are about to touch **lua**, **FC safety**, or **SITL automation**.
This folder is inert study material. Live code is under `src/` and `hardware/`.
Lessons (symptom / cause / what we changed) live in [`docs/lessons-learned.md`](../docs/lessons-learned.md) — do not duplicate them here.

The 2026 module catalog (orchestrator, spray, CV, clearance, building survey) is in [`notes.md`](notes.md).

---

## Lua / kill switch / payload servo

| What | Where |
|------|--------|
| Study copies of the 2026 FC scripts | [`lua/`](lua/) — start with [`lua/NOTES.md`](lua/NOTES.md) |
| Live kill switch (the fixed one) | `hardware/vion/lua/safety.lua` |
| Lesson | [A missing RC channel looked like a kill switch](../docs/lessons-learned.md) |

`safety.lua` runs on the flight controller. It has to work with the Pi unplugged. A missing RC channel is not a command: the old code defaulted unread RC8 to PWM 1500, which sat above the 1300 trigger, so "no signal" and "switch thrown" were the same state.

`payload.lua` is the 2026 water-servo stepper (RC10 cycles SERVO14 through PWM states). Same pattern for a 2027 tracker release or sample gripper: one interface, channel in the script, irreversible action behind a switch.

`arm.lua` auto-arms the vehicle from Lua. Read it as a warning. Do not put that on a field aircraft.

`throttle_two.lua` still contains the fail-dangerous `or 1500` default on the kill channel. That is the bug in the flesh; `safety.lua` is the fix.

---

## Safety / FTS / fence / companion abort

| What | Where |
|------|--------|
| 2026 every-tick override + Lua gate that *blocked* start | [`orchestrator.py`](orchestrator.py) (`assert_safety_lua`, `SafetyMonitor`, `_complete_handoff_loiter`) |
| Live companion safety (advisory) | `src/valiant/core/safety/` (`monitor.py`, `pilot_override.py`, `boundary.py`) |
| Live FC param readback (never writes, never blocks arm) | `src/valiant/core/flight/fc_safety.py` |
| Live hard boundary constants | `src/valiant/core/safety/boundary.py` |
| Lesson | Companion never terminates; FC `FENCE_ACTION = 2` does. See fc_safety module docstring and CONOPS 4.5. |

The 2026 orchestrator refused to start if `SCR_ENABLE` was off or `safety.lua` was missing. That stranded us on the flight line. 2027 prints a warning and the pilot decides. Termination is the autopilot inclusion fence loaded from `config/aeac2027_boundary.poly`.

---

## SITL automation / end-of-script hold

| What | Where |
|------|--------|
| 2026 smoking gun | [`orchestrator.py`](orchestrator.py) `_complete_handoff_loiter` — `motion.set_loiter(message="Loiter - manual control")` |
| Live hold (GUIDED zero velocity) | `src/valiant/core/motion/hold.py` |
| SITL RC parked at mid-stick | `neutralize_sitl_rc()` in `hold.py`, called on SITL connect from `src/valiant/core/mavlink.py` |
| Offline regression | `tests/test_motion_hold.py` |
| Live SITL regression | `tests/sitl/test_sitl_hold.py` |
| Launch | `tools/sitl/launch_sitl.sh`, `tools/sitl/sitl_orbit_flight.py` |
| Lesson | [The SITL aircraft drops out of the sky when a script finishes](../docs/lessons-learned.md) |

LOITER is a *pilot* mode. With `--no-mavproxy`, channel 3 reads minimum, LOITER reads that as full-down throttle, and the aircraft descends. An autonomous script must end in GUIDED zero-velocity (`hold_position`), and only call `hand_back_to_pilot` when a transmitter is present.

---

## Companion crash with no hold

| What | Where |
|------|--------|
| Live typed errors + `crew_message` | `src/valiant/core/errors.py` |
| Uncaught exception → STATUSTEXT + GUIDED hold | `hold_after_fault` in `src/valiant/core/motion/hold.py`; wired from `field_orbit.py` / `waypoints.py` |
| Lesson | [An uncaught Python exception left the aircraft with no hold](../docs/lessons-learned.md) |

---

## If it is not in this folder

The full 2026 tree is `git show aeac2026-final:<path>`. After this snapshot you should not need that for lua, safety, or SITL.
