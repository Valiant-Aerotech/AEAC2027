# Lessons learned

Things that cost us time or aircraft. Each entry is a symptom, the cause, and
what changed in the code so it cannot happen again. Add to this file rather
than rediscovering an entry.

---

## The SITL aircraft drops out of the sky when a script finishes

**Symptom.** Every scripted SITL flight ended the same way: the mission
completed, the console printed `Loiter - manual control`, and the simulated
aircraft descended straight to the ground. It looked like a bug in the orbit
or pattern logic, because the drop always came right at the end.

**Cause.** ArduCopter's LOITER is a *pilot-controlled* mode. It holds position
horizontally, but the throttle stick commands climb rate: centre stick holds
altitude, and stick at minimum commands maximum descent. We launch SITL with
`sim_vehicle.py --no-mavproxy`, so nothing drives the simulated RC channels
and channel 3 reads at or below its minimum. Switching to LOITER therefore
handed the aircraft to a throttle stick that was pinned to the floor, and it
obediently descended at `LAND_SPEED`.

The mistake was not the mode, it was treating "hold position" and "give
control back to the pilot" as the same operation. They are not:

| | holds position | needs a human | safe as an autonomous terminal state |
|---|---|---|---|
| GUIDED, zero velocity | yes | no | yes |
| LOITER | yes, horizontally | yes, for altitude | no |
| BRAKE | yes, briefly | no | no, it times out |

**Fix.** `src/valiant/core/motion/hold.py` splits the two:

- `hold_position()` stays in GUIDED and streams a zero-velocity setpoint with
  a proportional term on the latched altitude. This is the default terminal
  state for every scripted segment, via `GuidedMotionRunner.finish()`.
- `hand_back_to_pilot()` commands LOITER, but first checks `RC_CHANNELS` for a
  plausible throttle reading and refuses if there is none. It is reached only
  when `sitl=False`.
- `neutralize_sitl_rc()` runs on every SITL connect, parking channel 3 at
  1500 µs and clearing `SIM_RC_FAIL`, so even a stray LOITER holds altitude.

**Guarded by.** `tests/test_motion_hold.py` runs offline in CI and asserts the
hold never changes mode and that the LOITER guard refuses a link with no RC.
`tests/sitl/test_sitl_hold.py` flies it for real and asserts the aircraft
loses under 2 m in 20 s.

**The general rule.** *An autonomous hold must never depend on a human's stick
position.* This applies to the real aircraft too, not just the simulator: if
the transmitter is off, out of range, or on a failsafe, LOITER is not a hold.

---

## Depth beyond 65 m reads as garbage

**Symptom.** Depth frames from the simulated camera raised
`OverflowError: Python integer 200000 out of bounds for uint16` once survey
altitudes went past 65 m.

**Cause.** Depth is `uint16` millimetres to match the Arducam ToF sensor, which
caps at 65.535 m. The 2026 mission flew indoors at a few metres, so the limit
never came up. The 2027 survey flies to 100 m AGL.

**Fix.** `valiant.sim.cameras` clamps to `DEPTH_MAX_MM`. This is faithful
rather than a workaround: the real sensor has no useful range at survey
altitude either, and saturation correctly means "no depth reading", which
makes `metric_recon` fall back to its apparent-size estimate. Do not size
range gates on ToF depth above about 60 m.
