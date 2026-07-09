# Vivi outdoor hardware day (orbit + target mission)

Two-run field day in an open parking lot: **Run 1** validates GUIDED orbit (no CV). **Run 2** runs the full CV mission pipeline (spray servo, wet verify, photo, **retreat**, LOITER handoff). **Both runs are implemented in the current repo** — deploy to Pi before field.

See also: [vivi-orbit-field-test.md](vivi-orbit-field-test.md), [vion-bringup.md](vion-bringup.md), [field-test-plan.md](field-test-plan.md), [pi-fresh-install.md](pi-fresh-install.md), [hardware/vivi/WIRING.md](../../hardware/vivi/WIRING.md).

## Before hardware day (once, at home)

### Laptop (GCS)

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\start.ps1
python tools\valiant.py env check
python tools\valiant.py conops check
python -m pytest tests/ -q
```

Set telemetry COM in `config/rpas.yaml`. Deploy model to Pi:

```powershell
.\tools\deploy\deploy_to_pi.ps1 -PiHost pi@<PI_IP>
```

Deploy copies `models/best.onnx` and/or `models/dry.onnx` when present locally. Re-run deploy before Run 2 whenever laptop code changes.

### Pi (first SSH)

Full guide: [pi-fresh-install.md](pi-fresh-install.md)

```bash
git clone https://github.com/Valiant-Aerotech/AEAC2027.git && cd AEAC2027
bash hardware/vion/rpi/pi_field_ready.sh --first-time
# After laptop deploy:
bash hardware/vion/rpi/pi_field_ready.sh --check
```

### Flight controller (Mission Planner, once)

- [ ] `SCR_ENABLE=1`, [`safety.lua`](../../hardware/vion/lua/safety.lua) on SD, reboot → Messages: `safety: kill monitor loaded (RC8)`
- [ ] `python tools\valiant.py gcs verify-safety`
- [ ] Map mode switch channel to **GUIDED**
- [ ] GPS lock outdoors (3D fix, reasonable HDOP)
- [ ] SERVO15 spray test props-off (Run 2)
- [ ] Pi TELEM: `SERIALx_PROTOCOL=2`, `SERIALx_BAUD=57` on Pi UART only ([002-pi-telem-params.md](../../hardware/vion/mission-planner/002-pi-telem-params.md), [WIRING.md](../../hardware/vivi/WIRING.md))

### SITL smoke (night before)

```powershell
.\tools\launch_sitl.ps1
python tools\valiant.py sitl orbit --laps 1
```

---

## Run 1 — Orbit (no CV)

**Goal:** Manual takeoff → flip **GUIDED** → N laps → **LOITER** → manual home.

**Pi (start before arming):**

```bash
bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <LAPTOP_IP> --laps 2
```

**Laptop:**

```powershell
python tools\valiant.py gcs monitor
python tools\valiant.py gcs verify-safety
```

### Pilot steps

1. Start orbit script on Pi → terminal shows standby for GUIDED
2. Arm in **STABILIZE/ALT_HOLD**, climb to ~10 m AGL
3. Flip **mode switch → GUIDED**
4. Watch Messages: `T2: Climbing to 10 m` → `Flying forward` → `Lap 1/N` → `Returning to center` → `Loiter - manual control`
5. Flip switch **off GUIDED**, fly home manually
6. **Override anytime:** flip off GUIDED → companion stops velocity
7. **Kill switch:** FC **LAND** immediately; companion stops

### Pass criteria

- Circle ~5 m radius, return near start, end in LOITER
- First field day: `--laps 1` or `2`, not 5

Full detail: [vivi-orbit-field-test.md](vivi-orbit-field-test.md)

> **Note:** `--drone vivi` loads `vion.yaml` + `vivi.yaml`. Orbit script defaults to `--drone vion`; both work with `vivi_orbit` / `vivi_outdoor_mission` profiles.

---

## Run 2 — Single target on pole (CV + auto-nav)

**Goal:** Detect purple dry target → approach → align → **fire servo** (no water line) → **VERIFYING** (HSV wet) → photo → **LOITER** → manual takeover.

**Profile:** `vivi_outdoor_mission` enables GUIDED, GPS, `MAVLINK_SERVO` spray, Pi camera, GUIDED standby, and LOITER on COMPLETE. Do **not** use `--profile vivi` alone (spray disabled).

### Target setup

- Purple competition circle (5–30 cm) on pole, ~1–3 m height
- For VERIFYING: wet target after servo fires (spray bottle) or use pre-wetted blue patch
- `require_shot_confirmation: true` in conops — 8 s timeout if never wet

### Pi command

```bash
bash hardware/vion/rpi/pi_field_ready.sh --mission --gcs-ip <LAPTOP_IP> --max-targets 1
```

### Pilot workflow

With `mission.pilot_standby: true` (default in profile):

1. Start mission script on Pi **before** arming → state `SEARCHING`, terminal waits for GUIDED at ~8 m
2. Arm, climb toward pole in manual modes
3. Flip **GUIDED** at altitude (script proceeds; motion only after target seen)
4. Fly toward pole until purple fills part of camera view
5. Watch GCS: `SEARCHING` → `APPROACHING` → `AIMING` → `FIRING` → `VERIFYING` → `CAPTURING` → `UPLOADING` → `RETREAT` → `COMPLETE`
6. **When FIRING fires SERVO15:** wet the target with spray bottle (or use pre-wetted blue patch for testing)
7. After photo saved: drone backs away (~2.5 m) and climbs slightly (~1 m) → **LOITER** (`Loiter - manual control`); flip off GUIDED and fly home
8. Photo on Pi: `task2_photos/Task_2_<team>_target_1.jpg`

### Without ToF

- Range gates use FOV estimate — approach proof may be approximate
- Tune `auto_nav.kp_x/y`, `deadband_px`, `approach_speed` after first flight

### If VERIFYING fails

- Wet target within 8 s of FIRING
- Tune `hsv_shot` in outdoor profile
- Dev only: `require_shot_confirmation: false` in conops overlay (not competition-accurate)

---

## Day-of timeline

| Time | Activity |
|------|----------|
| T-0 | Site setup, MP connect, GPS lock, verify-safety |
| T+15 | Pi `pi_field_ready.sh --check` |
| **Run 1** | Orbit `--laps 1`, debrief |
| **Run 2 prep** | Mount pole target |
| **Run 2** | Mission `--max-targets 1`, debrief photos + logs |
| End | Download photos from Pi, note tune values |

---

## Pack list

Open field, spotter, kill switch tested, charged batteries, laptop + MP radio, Pi WiFi to laptop IP, phone hotspot optional.

**Run 2 additions:** printed purple target, tape, pole, spray bottle for wetting, optional ArduCam ToF if wired.
