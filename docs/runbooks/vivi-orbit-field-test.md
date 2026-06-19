# Vivi GUIDED orbit field test

Outdoor validation for **Vivi + Pi companion**: pilot arms and climbs manually, selects **GUIDED** on RC, companion runs a scripted orbit, then **LOITER** for manual return.

This is **not** the CV orchestrator (`run_mission.py`). No auto-arm, takeoff, spray, or target search.

## How to run

Pick the step that matches where you are. Run from the **repo root** with the venv active (`.\start.ps1` on Windows).

| Where | What you need | Command |
|-------|----------------|---------|
| **Windows + SITL (quick check)** | Terminal 1: `.\tools\launch_sitl.ps1` running | `python tools\valiant.py sitl orbit --laps 1` |
| **Windows + SITL (full 5 laps)** | Same | `python tools\valiant.py sitl orbit` |
| **Windows + SITL (with monitor)** | SITL up; optional third window | `python tools\valiant.py gcs monitor` then run orbit in another terminal |
| **Pi companion (field)** | Repo on Pi, GPS lock, laptop IP known | `python hardware/vion/rpi/run_field_orbit.py --profile vivi_orbit --gcs-ip <laptop-ip> --laps 1` |
| **GCS laptop (dev, Pi UART)** | Pi connected by radio/USB relay | `python tools\valiant.py field orbit --gcs-ip <laptop-ip> --laps 1` |

**Pilot steps (field):** start the script before arming → arm and climb to ~10 m in STABILIZE/ALT_HOLD → flip **mode switch to GUIDED** (channel TBD in Mission Planner) → script runs orbit → ends in **LOITER** → flip switch **off GUIDED** for manual control → fly home.

**Pilot override:** At any time during the auto segment, flip the mode switch **off GUIDED** (STABILIZE / ALT_HOLD / LOITER per your MP mapping). Companion stops velocity commands immediately (`Pilot takeover - companion stopped`) and returns to **STANDBY** (waits for next GUIDED trigger without restarting the script).

**Kill switch:** Hardware kill (RC channel 8 via [`safety.lua`](../../hardware/vion/lua/safety.lua)) commands **LAND immediately** on the flight controller. Companion detects kill PWM or LAND mode and stops streaming (`Emergency stop - companion stopped`). Verify `safety.lua` is loaded before field flight (see below).

### Confirm safety.lua is loaded

| Method | When | Pass |
|--------|------|------|
| **Automated (required before flight)** | Before arming, Pi or GCS | `python tools\valiant.py gcs verify-safety` → `SCR_ENABLE=1` and `safety.lua preflight OK` |
| **Pi session check** | Every `session_start` / preflight | `check_sensors.py --once` includes safety check when MAVLink up |
| **Mission Planner (visual)** | After FC power-on / reboot | Messages tab: `safety: kill monitor loaded (RC8)` |
| **MAVFTP (manual)** | Once per SD card setup | CONFIG → MAVFTP → `scripts/safety.lua` exists |
| **Kill switch functional test** | Props-off bench, before field | Flip kill switch → Messages: `safety: EMERGENCY...` → FC mode **LAND** |

**Setup checklist (one-time):**

1. Mission Planner → CONFIG → Full Parameter List → `SCR_ENABLE = 1` → **Reboot FC**
2. Copy [`hardware/vion/lua/safety.lua`](../../hardware/vion/lua/safety.lua) to SD card `APM/scripts/safety.lua` (MAVFTP or remove SD)
3. Reboot FC; confirm `safety: kill monitor loaded (RC8)` in Messages
4. Run `python tools\valiant.py gcs verify-safety` from GCS laptop (telemetry radio) or Pi UART

Field orbit and `run_mission.py` **block automatically** if `SCR_ENABLE` is off or `safety.lua` is missing (`safety.require_lua_safety: true` in config). SITL skips this check.

**What you should see:** Mission Planner **Messages** shows `T2:` lines (`Climbing to 10 m`, `Lap 2/5`, `Loiter - manual control`). UDP monitor shows phase and lap if `--gcs-ip` is set.

**Terminal altitude lines:** every ~2 s during alt hold and orbit you should see `[Orbit] alt=10.2m target=10.0m phase=ORBIT pos=(2.10,4.85) vn=0.35 ve=0.12 t=42s lap=0.8/1 ...`. **`pos=(x,y)` must change** during ORBIT; if it stays fixed, pose polling is broken. Do not proceed to forward until alt is within ~0.35 m of target.

**Help:** `python tools\valiant.py sitl orbit --help` (via underlying script) or read [sitl-wsl.md](sitl-wsl.md).

## Pass criteria

| Step | Pass |
|------|------|
| SITL | `python tools\valiant.py sitl orbit --laps 1` completes one lap, returns near center, LOITER |
| Tether | Forward 2 m in GUIDED with props restrained; no runaway drift |
| Field | 5 laps at R=5 m, return to center, LOITER; pilot takes RC back |

Accept ~0.5 m radius error in wind. Mission Planner shows plain `T2:` lines (`Lap 2/5`, `Returning to center`, `Loiter - manual control`).

## SITL-first rule

All new autonomous navigation scripts (orbit, pattern, mission legs) must pass in **SITL** before Pi field flight. Use `python tools\valiant.py sitl orbit --laps 1` as the smoke test for this script.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| Reverse / backward motion when orbit starts | Old tangent sign bug | Pull latest `main`; re-run SITL `--laps 1` |
| Steady descent ~0.15 m/s, no circle | Wrong tangent + center collapse | Same; verify MP vertical speed near 0 during orbit |
| Climbs to 17 m instead of 10 m | Takeoff overshoot before alt hold | Watch terminal `alt=Xm target=10m`; script waits to settle before forward |
| Straight line then sharp right turn | Orbit entry tangent matches forward leg | Normal at entry; path should curve within ~5 s (boosted radial hold) |
| `lap=0.0/1` forever, frozen `pos=(x,y)` | Stale LOCAL NED in orbit loop | Pull latest; terminal should show **changing** `pos=(x,y)` every ~2 s during ORBIT |
| `Returning to center` with lap=0 | Orbit timed out before lap complete | Script loiters instead (`return_on_timeout: false`); fix pose polling first |
| Duplicate `Flying forward` / `Loiter` in terminal | Double `say()` on phase change | One line per phase after dedupe fix; MP may still duplicate if `mp_use_autopilot_sysid` |
| `Geofence - switching to loiter` early in SITL | Radius too tight vs orbit path | `sitl_orbit` profile uses 20 m geofence; field uses 12 m |
| No `T2:` in Mission Planner | STATUSTEXT / sysid config | `python tools\valiant.py gcs verify-statustext` |
| Exits at 10 m with `Disarmed - companion stopped` | Pilot-override poll false disarm (empty MAVLink buffer) | Pull latest; `sync_from_vehicle` seeds armed state after takeoff |
| `Safety Lua preflight failed` at startup | SCR_ENABLE off or safety.lua missing | See **Confirm safety.lua is loaded** above; `gcs verify-safety` |
| Overshoot to 16 m after takeoff | SITL takeoff tuning | Script shows `Descending to 10 m` and holds before forward leg |

## Validate in SITL first

**Terminal 1:** `.\tools\launch_sitl.ps1`

**Terminal 2:**

```powershell
python tools\valiant.py sitl orbit
python tools\valiant.py sitl orbit --laps 1
```

Optional monitor: `python tools\valiant.py gcs monitor` (phase + lap columns).

See [sitl-wsl.md](sitl-wsl.md) orbit section.

## Pi setup

1. Deploy repo to Pi (`tools/deploy/deploy_to_pi.ps1` or rsync).
2. Every session: `bash hardware/vion/rpi/session_start.sh`
3. **Before arming:** `python tools/valiant.py gcs verify-safety --connection /dev/ttyAMA0` (or from GCS laptop via radio)
4. Start orbit script **before** arming:

```bash
python hardware/vion/rpi/run_field_orbit.py --profile vivi_orbit --gcs-ip <laptop-ip>
python hardware/vion/rpi/run_field_orbit.py --profile vivi_orbit --gcs-ip <laptop-ip> --laps 1
```

5. On GCS laptop: `python tools\valiant.py gcs monitor`
6. Mission Planner: confirm `safety.lua` loaded; map flight-mode switch channel (TBD); confirm `T2:` Messages during tether test.

## Pilot workflow

```text
STANDBY     Script waiting (disarmed or manual climb OK)
     |
     v  RC mode switch -> GUIDED at ~10 m AGL
ALT_HOLD    Hold 10 m if needed
     |
     v
FORWARD     2 m straight
     |
     v
ORBIT       5 m radius, N laps (direction from config)
     |
     v
RETURN      Fly to circle center (alt hold logged)
     |
     v
HOVER       2 s zero horizontal vel at target alt
     |
     v
LOITER      Script stops commanding; pilot flies home manually
```

**Anytime:** flip mode switch **off GUIDED** → companion stops, returns to STANDBY.

**Kill switch:** FC LAND immediately; companion stops streaming.

If mode leaves **GUIDED** during the auto segment, companion stops with `Pilot takeover - companion stopped` and returns to STANDBY (re-trigger with GUIDED switch when ready).

## Config

Profile `flight_profiles.vivi_orbit` in [`config/vion.yaml`](../../config/vion.yaml):

| Key | Default |
|-----|---------|
| `field_orbit.trigger_alt_m` | 10.0 |
| `field_orbit.forward_m` | 2.0 |
| `field_orbit.radius_m` | 5.0 |
| `field_orbit.laps` | 5 |
| `field_orbit.direction` | `clockwise` or `counter_clockwise` |
| `field_orbit.orbit_speed_m_s` | 0.40 |
| `field_orbit.geofence_radius_m` | 12.0 |
| `field_orbit.max_duration_s` | 600 |
| `field_orbit.loiter_settle_s` | 2.0 (hover before LOITER handoff) |
| `field_orbit.standby_retrigger` | true (field: wait for next GUIDED after takeover) |
| `field_orbit.pilot.kill_switch_rc_channel` | 8 (matches `safety.lua`) |
| `field_orbit.pilot.guided_mode_channel` | null (TBD — set after MP flight-mode mapping) |

## Safety

- Open field, spotter, kill switch ready.
- **Pre-flight:** confirm [`safety.lua`](../../hardware/vion/lua/safety.lua) loaded on Kakute (kill → LAND).
- Document mode-switch channel in Mission Planner after radio setup (GUIDED position TBD).
- First flights: tether or hold frame; verify GUIDED velocity before full orbit.
- Geofence aborts to LOITER if horizontal drift from trigger point exceeds config.
- No force-arm on field (unlike SITL preflight).
- Pi only sends velocity in GUIDED; pilot can take manual control anytime via mode switch.

## Abort

| Condition | FC action | Companion action |
|-----------|-----------|------------------|
| Mode switch off GUIDED | Pilot manual mode | Stop stream, STANDBY, wait for re-trigger |
| Kill switch (RC ch 8) | **LAND immediately** (`safety.lua`) | Stop stream, do not command LOITER |
| LAND / RTL / disarm | FC emergency mode | Stop stream |
| Geofence | — | Stop stream, LOITER |
| Max duration | — | LOITER |
| GPS fix lost | — | Standby loop (no start) |

## Related

- SITL box pattern (regression): `python tools\valiant.py sitl pattern`
- Branch workflow: [branches.md](../branches.md)
- GitHub tracking: issue **E10**
