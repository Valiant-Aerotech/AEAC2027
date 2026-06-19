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
| **Pi companion (field)** | Repo on Pi, GPS lock, laptop IP known | `python hardware/vion/rpi/run_field_orbit.py --profile vivi_orbit --gcs-ip <laptop-ip>` |
| **GCS laptop (dev, Pi UART)** | Pi connected by radio/USB relay | `python tools\valiant.py field orbit --gcs-ip <laptop-ip>` |

**Pilot steps (field):** start the script before arming → arm and climb to ~10 m in STABILIZE/ALT_HOLD → switch RC to **GUIDED** → script runs orbit → ends in **LOITER** → switch RC back to manual and fly home.

**What you should see:** Mission Planner **Messages** shows `T2:` lines (`Climbing to 10 m`, `Lap 2/5`, `Loiter - manual control`). UDP monitor shows phase and lap if `--gcs-ip` is set.

**Help:** `python tools\valiant.py sitl orbit --help` (via underlying script) or read [sitl-wsl.md](sitl-wsl.md).

## Pass criteria

| Step | Pass |
|------|------|
| SITL | `python tools\valiant.py sitl orbit --laps 1` completes one lap, returns near center, LOITER |
| Tether | Forward 2 m in GUIDED with props restrained; no runaway drift |
| Field | 5 laps at R=5 m, return to center, LOITER; pilot takes RC back |

Accept ~0.5 m radius error in wind. Mission Planner shows plain `T2:` lines (`Lap 2/5`, `Returning to center`, `Loiter - manual control`).

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
3. Start orbit script **before** arming:

```bash
python hardware/vion/rpi/run_field_orbit.py --profile vivi_orbit --gcs-ip <laptop-ip>
```

4. On GCS laptop: `python tools\valiant.py gcs monitor`
5. Mission Planner on radio: confirm `T2:` Messages during tether test.

## Pilot workflow

```text
STANDBY     Script waiting (disarmed or manual climb OK)
     |
     v  RC switch GUIDED at ~10 m AGL
ALT_HOLD    Hold 10 m if needed
     |
     v
FORWARD     2 m straight
     |
     v
ORBIT       5 m radius, 5 laps (direction from config)
     |
     v
RETURN      Fly to circle center
     |
     v
LOITER      Script stops commanding; pilot flies home manually
```

If mode leaves **GUIDED** during the auto segment, script aborts with `T2: Aborted - left GUIDED` and returns to standby.

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

## Safety

- Open field, spotter, kill switch ready.
- First flights: tether or hold frame; verify GUIDED velocity before full orbit.
- Geofence aborts to LOITER if horizontal drift from trigger point exceeds config.
- No force-arm on field (unlike SITL preflight).
- Pi only sends velocity in GUIDED; avoid stick input during auto segment.

## Abort

| Condition | Action |
|-----------|--------|
| Left GUIDED | Stop stream, standby message |
| Geofence | Stop stream, LOITER |
| Max duration | LOITER |
| GPS fix lost | Standby loop (no start) |

## Related

- SITL box pattern (regression): `python tools\valiant.py sitl pattern`
- Branch workflow: [branches.md](../branches.md)
- GitHub tracking: issue **E10**
