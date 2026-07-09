# Raspberry Pi fresh install → field flight

Complete bring-up from a **new Raspberry Pi OS SD card** through **outdoor orbit** and **CV target mission** on Vivi.

**One script on the Pi:** `bash hardware/vion/rpi/pi_field_ready.sh`

See also: [vion-bringup.md](vion-bringup.md), [vivi-outdoor-field-day.md](vivi-outdoor-field-day.md), [vivi-orbit-field-test.md](vivi-orbit-field-test.md).

---

## What you need

| Item | Notes |
|------|--------|
| Raspberry Pi 4/5 | Raspberry Pi OS (64-bit recommended), power supply, flashed SD |
| Drone | Kakute FC, GPS (HERE4), Pi UART → FC TELEM, Pi camera, props, batteries |
| Laptop | Windows, Mission Planner, telemetry radio USB, repo cloned |
| Network | Pi on WiFi (same LAN as laptop or phone hotspot) |
| Optional Run 2 | Purple target, pole, spray bottle to wet target after servo fires |

**Two MAVLink links (never share one port):**

| Link | Path | Role |
|------|------|------|
| GCS radio | Laptop COM → Pixhawk | Mission Planner, params, safety verify |
| Pi companion | `/dev/ttyAMA0` @ 57600 → TELEM | Autonomy scripts |
| WiFi monitor | Pi UDP → laptop | `python tools\valiant.py gcs monitor` |

H-Flow is **not required** for outdoor GPS + GUIDED flight.

---

## Part 1 — Flash and first boot (Pi only)

1. Flash **Raspberry Pi OS** to SD (Raspberry Pi Imager).
2. In Imager advanced options (recommended):
   - Set hostname, username, password
   - Configure **WiFi** SSID and password
   - Enable **SSH**
3. Insert SD, power Pi, wait ~2 min for first boot.
4. Find Pi IP:
   - Router admin page, or
   - `ping raspberrypi.local`, or
   - Connect monitor temporarily: `hostname -I`

---

## Part 2 — SSH and base OS packages

From your laptop:

```bash
ssh <user>@<PI_IP>
```

On the Pi:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3-venv python3-picamera2
sudo usermod -aG dialout $USER
```

**Log out and SSH back in** so `dialout` group applies (required for `/dev/ttyAMA0`).

### Enable UART (Pi ↔ flight controller)

```bash
sudo raspi-config
```

→ **Interface Options** → **Serial Port** →

- Login shell over serial: **No**
- Serial port hardware: **Yes**

Reboot:

```bash
sudo reboot
```

After reboot, verify:

```bash
grep enable_uart /boot/firmware/config.txt
# or: grep enable_uart /boot/config.txt
# expect: enable_uart=1
ls -l /dev/ttyAMA0
```

### Wire Pi to Kakute H7

Physical UART wiring (props off, FC unpowered): [hardware/vivi/WIRING.md](../../hardware/vivi/WIRING.md)

| Pi pin | → FC |
|--------|------|
| Pin 8 (TX) | RX |
| Pin 10 (RX) | TX |
| Pin 6 (GND) | GND |

Use a **dedicated** FC UART port — not the GCS telemetry radio port.

---

## Part 3 — Clone repo and first-time bootstrap

```bash
cd ~
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
bash hardware/vion/rpi/pi_field_ready.sh --first-time
```

This script:

- Creates Python venv and installs `pip install -e ".[cv]"`
- Copies calibration yaml from example if missing
- Checks UART, model files, MAVLink device
- Prints next steps

**Equivalent legacy command:** `bash hardware/vion/rpi/first_connect.sh`

---

## Part 4 — Laptop: deploy code and model

On Windows (repo root, venv active):

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\start.ps1
```

Set GCS radio COM in `config/rpas.yaml`:

```yaml
mavlink:
  connection: "COM5"   # your telemetry port
```

Deploy to Pi:

```powershell
.\tools\deploy\deploy_to_pi.ps1 -PiHost <user>@<PI_IP>
```

Copies `src`, `config`, `hardware`, and `models/dry.onnx` / `models/best.onnx` when present on laptop.

Re-run deploy whenever laptop code changes before a field day.

---

## Part 5 — Flight controller (Mission Planner, once)

Power FC with props **off**. Connect telemetry radio to laptop.

### 5.1 Connect and GPS

1. Mission Planner → Connect @ **57600**
2. Confirm heartbeat, battery, GPS status
3. Outdoors: wait for **3D fix** and reasonable HDOP before flight tests

### 5.2 Pi TELEM port (separate from GCS radio)

On the SERIAL port wired to the Pi only ([002-pi-telem-params.md](../../hardware/vion/mission-planner/002-pi-telem-params.md)):

| Parameter | Value |
|-----------|-------|
| `SERIALx_PROTOCOL` | `2` (MAVLink2) |
| `SERIALx_BAUD` | `57` (57600) |

Reboot FC after saving.

Quick reference: `.\tools\bringup\print_fc_params.ps1`

### 5.3 Safety.lua (required before flight)

1. `SCR_ENABLE = 1` → reboot FC
2. Copy [`hardware/vion/lua/safety.lua`](../../hardware/vion/lua/safety.lua) to SD `APM/scripts/safety.lua`
3. Reboot FC → Messages: `safety: kill monitor loaded (RC8)`
4. Laptop: `python tools\valiant.py gcs verify-safety`

### 5.4 Mode switch

Map one RC mode position to **GUIDED** (note which switch position in your runbook).

### 5.5 Optional Run 2

Props off: `python tools\valiant.py gcs spray` — SERVO15 should move (no water line needed for field test).

---

## Part 6 — Every session: Pi preflight

FC powered, props off for bench; props on only when ready to fly.

```bash
cd ~/AEAC2027
bash hardware/vion/rpi/pi_field_ready.sh --check
```

**Pass criteria:**

- `[OK] RGB frame captured`
- `[OK] MAVLink heartbeat received`
- safety.lua preflight OK (when FC powered)

**Camera only (FC off):**

```bash
bash hardware/vion/rpi/pi_field_ready.sh --check --skip-mavlink
```

**Equivalent legacy command:** `bash hardware/vion/rpi/session_start.sh`

---

## Part 7 — Every session: laptop GCS

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\start.ps1
python tools\valiant.py gcs monitor
python tools\valiant.py gcs verify-safety
```

Note your laptop **WiFi IP** (`ipconfig` → IPv4 on WiFi adapter). Pi uses this for `--gcs-ip`.

---

## Part 8 — Run 1: Outdoor orbit (auto-nav test)

**Goal:** Manual takeoff → flip **GUIDED** → 1 lap → **LOITER** → manual home. No CV, no spray.

### Pi (start BEFORE arming)

```bash
cd ~/AEAC2027
bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <LAPTOP_IP> --laps 1
```

Terminal should show: `Standby: arm, climb to ~10 m, select GUIDED on RC`

### Pilot sequence

1. Start script on Pi — **do not arm yet**
2. Arm in **STABILIZE** or **ALT_HOLD**; climb to **~10 m AGL** over open area
3. Confirm GPS lock holds in Mission Planner
4. Flip **mode switch → GUIDED**
5. Watch Messages / GCS monitor:
   - `T2: Climbing to 10 m`
   - `Flying forward`
   - `Lap 1/1`
   - `Returning to center`
   - **`Loiter - manual control`**
6. Flip switch **off GUIDED** → fly home manually and land

### Abort / safety

| Action | Result |
|--------|--------|
| Flip off GUIDED during auto | Companion stops velocity (`Pilot takeover`) |
| Kill switch (RC8) | FC **LAND** immediately; companion stops |

### Pass criteria (first field day)

- ~5 m radius circle ([`field_orbit.radius_m`](../../config/vion.yaml))
- Returns near start
- Ends in **LOITER**
- Use `--laps 1` only on first day

Detail: [vivi-orbit-field-test.md](vivi-orbit-field-test.md)

---

## Part 9 — Run 2: Target on pole (CV mission)

**After** Run 1 debrief and code deploy. Requires YOLO model on Pi.

### Prep

1. Mount **purple dry target** (5–30 cm) on pole/post, ~1–3 m height
2. Spray bottle ready — wet target within **8 s** of FIRING (HSV blue verify)
3. Confirm `models/dry.onnx` or `models/best.onnx` on Pi

### Pi (start BEFORE arming)

```bash
bash hardware/vion/rpi/pi_field_ready.sh --mission --gcs-ip <LAPTOP_IP> --max-targets 1
```

Uses profile `vivi_outdoor_mission` (GUIDED, spray SERVO, GUIDED standby, retreat, LOITER).

**Do not use `--profile vivi` alone** — that disables spray.

### Pilot sequence

1. Start script → waits: `Standby: arm, climb to ~8 m, select GUIDED`
2. Arm, climb toward pole in manual modes
3. Flip **GUIDED** at ~8 m (no autonomous motion until purple seen)
4. Fly toward pole until target is in camera view
5. Watch states: `SEARCHING` → `APPROACHING` → `AIMING` → `FIRING` → `VERIFYING` → `CAPTURING` → `UPLOADING` → `RETREAT` → `COMPLETE`
6. When **FIRING** (SERVO15 pulses): wet the target with spray bottle
7. Drone backs away and climbs slightly → **LOITER**
8. Flip off GUIDED, fly home
9. Photo on Pi: `task2_photos/Task_2_<team>_target_1.jpg`

Detail: [vivi-outdoor-field-day.md](vivi-outdoor-field-day.md)

---

## pi_field_ready.sh reference

| Command | When |
|---------|------|
| `pi_field_ready.sh --first-time` | Once after fresh OS + clone |
| `pi_field_ready.sh` or `--check` | Every session preflight |
| `pi_field_ready.sh --orbit --gcs-ip <IP> --laps 1` | Run 1 field orbit |
| `pi_field_ready.sh --mission --gcs-ip <IP> --max-targets 1` | Run 2 CV mission |
| `pi_field_ready.sh --check --skip-mavlink` | Camera test, FC off |
| `pi_field_ready.sh --orbit ... --skip-check` | Skip preflight (dev only) |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| Permission denied `/dev/ttyAMA0` | Not in `dialout` | `sudo usermod -aG dialout $USER`, re-login |
| No MAVLink heartbeat | UART off or wrong FC params | `enable_uart=1`, `SERIALx_PROTOCOL=2`, `BAUD=57` on Pi port only |
| Script blocked at start | safety.lua missing | `gcs verify-safety`, load script on SD |
| No motion in GUIDED | Wrong mode or disarmed | Pilot must select GUIDED; arm and climb first |
| Orbit does nothing | GPS no fix | Wait outdoors for 3D lock |
| Stuck SEARCHING (Run 2) | No model / wrong color | Deploy `dry.onnx`; check purple target lighting |
| VERIFYING timeout | Target not wet in time | Spray bottle within 8 s of FIRING |
| No LOITER at end | Stale Pi code | Re-run `deploy_to_pi.ps1` |
| GCS monitor empty | Wrong `--gcs-ip` or firewall | Use laptop WiFi IP; allow UDP 14560 |

---

## Day-of timeline

| Time | Activity |
|------|----------|
| T-0 | Site setup, MP connect, GPS lock, verify-safety |
| T+10 | Pi `pi_field_ready.sh --check` |
| **Run 1** | Orbit `--laps 1`, debrief |
| **Run 2 prep** | Mount pole target, deploy check |
| **Run 2** | Mission `--max-targets 1`, debrief photos |
| End | Download photos from Pi (`scp`), note tune values |

---

## Pre-field checklist (home)

- [ ] `python -m pytest tests/ -q` passes on laptop
- [ ] `models/dry.onnx` or `best.onnx` on laptop; deploy to Pi
- [ ] `config/rpas.yaml` COM port correct
- [ ] Pi: picamera2, UART, repo, `pi_field_ready.sh --first-time` done
- [ ] FC: safety.lua, GUIDED on mode switch, Pi TELEM params
- [ ] Optional SITL: `python tools\valiant.py sitl orbit --laps 1`
