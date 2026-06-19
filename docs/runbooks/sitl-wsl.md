# SITL on WSL2 (Windows)

> **Start here:** [sitl-overview.md](sitl-overview.md) - what is simulated, code map, profiles.  
> This page is WSL install + troubleshooting detail.

Software-in-the-loop testing with **ArduPilot SITL** + AEAC orchestrator. No physical drone required.

Inspired by [Stanley](https://github.com/Matchstic/stanley) patterns; we use **pymavlink** + WSL `sim_vehicle.py` (not dronekit-sitl).

## One-time WSL setup (fresh Windows PC)

**One command** from repo root (use **Administrator** PowerShell if WSL is not installed yet):

```powershell
.\tools\setup_wsl.ps1
```

Or: `python tools\valiant.py sitl setup-wsl`

**Keep the AEAC2027 repo on Windows** (e.g. `C:\Users\...\AEAC2027`). Do not clone it in Ubuntu unless you want to - PowerShell runs the WSL setup using the Windows path. Only **ArduPilot** is cloned inside WSL (`~/ardupilot` via public HTTPS, no GitHub auth).

If setup says Ubuntu not detected but Ubuntu is installed: open the **Ubuntu** app from Start menu once (complete Linux user setup), then re-run from PowerShell.

What it does:

1. Installs WSL2 + Ubuntu if missing (may require **reboot**)
2. Inside Ubuntu: apt packages, clone `~/ardupilot`, build ArduCopter SITL

After reboot: open **Ubuntu** once (create Linux user), then run the **same command again** to finish the build.

First ArduPilot build often takes **15-30 minutes**. Re-runs are fast (skipped if already built).

### If setup fails after prereqs

If PowerShell prints `WSL setup failed` right after `install-prereqs-ubuntu.sh end`, the ArduPilot **prereqs step finished**; the **SITL waf build** (step 4) failed. Re-run from Windows:

```powershell
.\tools\setup_wsl.ps1
```

Steps 1-3 are skipped when markers exist; only the compile runs again.

Manual recovery in **Ubuntu**:

```bash
source ~/venv-ardupilot/bin/activate
cd ~/ardupilot
./waf configure --board sitl
./waf copter -j4
```

Success: `~/ardupilot/build/sitl/bin/arducopter` exists. Build log: `~/.valiant_sitl_build.log`.

## Manual WSL setup (optional detail)

If you prefer step-by-step or the script fails, use these steps:

1. Install WSL2 Ubuntu
2. Clone and build ArduPilot ([dev setup](https://ardupilot.org/dev/docs/building-setup-linux.html)):

```bash
sudo apt update
sudo apt install -y git python3-pip python3-dev python3-empy
git clone https://github.com/ArduPilot/ardupilot.git ~/ardupilot
cd ~/ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
./waf configure --board sitl
./waf copter
```

(`empy==3.3.4` is required by ArduPilot's waf build - install in **WSL** via `python3-empy`, not the Windows `.venv`.)

3. Verify from **Windows** (after SITL running):

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
$env:PYTHONPATH="src"
python -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('tcp:127.0.0.1:5760'); m.wait_heartbeat(); print('SITL OK')"
```

## Run SITL

**From repo root** (not `tools/`):

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\tools\launch_sitl.ps1
```

Home position is read from [`tests/fixtures/sitl_home.json`](../../tests/fixtures/sitl_home.json) (default: Newfoundland coordinates).

If you see `No such file or directory` for the `.sh` path, pull latest (scripts map Windows paths to `/mnt/c/...` automatically) or run directly in WSL:

```bash
cd ~/ardupilot
./Tools/autotest/sim_vehicle.py -v ArduCopter --no-mavproxy
```

The ArduCopter window shows `SERIAL0 on TCP port 5760` - that is normal. AEAC connects directly; MAVProxy is **not** required.

You may also see `Serial port 2 on TCP port 5762` (and sometimes 5763). Use those for **Mission Planner** so Valiant keeps 5760.

### Mission Planner as GCS viewer (optional)

**SITL is ArduPilot**, not a Mission Planner feature. Mission Planner can either **start** its own SITL (Simulation tab) or **connect** to one you already started. This repo uses the second approach: `launch_sitl.ps1` in WSL, Valiant mission on **5760**, Mission Planner on **5762**.

Do **not** start SITL from Mission Planner **and** `launch_sitl.ps1` at the same time (two simulators).

**Typical layout (3 terminals):**

| Terminal | What |
|----------|------|
| 1 | `.\tools\launch_sitl.ps1` - wait for `TCP port 5760` |
| 2 | Mission Planner - connect **TCP**, host `127.0.0.1`, port **5762** |
| 3 | `python tools\valiant.py sitl mission` - autonomy on **5760** |

**Mission Planner steps:**

1. Top-right connection dropdown: **TCP**
2. Click **Connect**
3. Host: `127.0.0.1` (WSL forwards localhost to Windows)
4. Port: **5762** (not 5760 - that is reserved for the orchestrator)

If 5762 fails, try **5763**, or check the ArduCopter console for `Serial port N on TCP port XXXX`.

**What you will see in Mission Planner:**

- Map position, altitude, heading, GUIDED mode
- Arm/disarm state (Valiant arms during mission - avoid fighting it from MP)
- **Messages** tab: plain-language `T2:` status from Valiant (flight-line friendly):
  - `Scanning for target`, `Moving toward target`, `Aiming at target`, `Spraying target`, etc.
  - State changes announce the new phase immediately (no wall/range numbers)
  - Optional multi-target: `Target 2/3: Aiming at target`

SITL sends STATUSTEXT on the **5760** companion link **and** duplicates with the autopilot sysid (comp 191) so Mission Planner on **5762** shows the same lines.

**Verify without a full mission** (SITL running, MP on 5762):

```powershell
python tools\valiant.py gcs verify-statustext
```

Expect `T2: VERIFY statustext` in Messages. If missing, open MAVLink Inspector (Ctrl+F), filter `STATUSTEXT`, and confirm sysid 1 / comp 191. Tune `config/vion.yaml` → `gcs_monitor`:

| Key | Default (SITL) | Purpose |
|-----|----------------|---------|
| `statustext_interval_s` | 3.0 | Periodic status rate |
| `statustext_severity` | `notice` | MP visibility (`info` is quieter) |
| `mp_use_autopilot_sysid` | `true` | Duplicate as FC sysid for MP Messages |
| `debug_statustext` | `false` | Log each send to mission terminal |
| `sitl_mp_mirror` | (unset) | Optional `udpout:...` duplicate if MP still misses lines |

Pattern flight turns use **SET_POSITION_TARGET_LOCAL_NED** mask **2503** (yaw + zero velocity), streamed at 20 Hz. Do not use CONDITION_YAW alone with velocity messages.

**What Mission Planner will not show:**

- Synthetic CV bbox - use the Valiant dashboard window from the mission script
- Full planner debug - use the terminal or `gcs monitor` below

**Alternative HUD:** `python tools\valiant.py gcs monitor` (UDP 14560) shows state, distance, position, velocity, and motion rule in a terminal table. SITL missions auto-send to `127.0.0.1:14560` (a monitor window is opened by `run_sitl_mission.ps1` unless `-NoMonitor`).

Optional: install MAVProxy in WSL if you want ArduPilot's map/console UI inside WSL instead of Mission Planner:

```bash
python3 -m pip install --user --break-system-packages MAVProxy
./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
```

## Run mission against SITL

**No physical drone required** - SITL is a software flight controller on your laptop.

### Guided box pattern (no CV / fire mission)

Familiarization flight: take off in GUIDED, fly a box (10 m → right 90° → 5 m → left 180° → 5 m → left 90° → 10 m), then **LOITER** for manual control.

**Terminal 2:**

```powershell
python tools\valiant.py sitl pattern
```

Or `.\tools\run_sitl_pattern.ps1`. Expect `T2:` lines like `Flying forward 10 m` and `Loiter - manual control` in Mission Planner.

### Daily driver (timeline synthetic - fast iteration)

**Terminal 2** (from repo root):

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\tools\run_sitl_mission.ps1
```

Default `-Profile sitl` uses **scripted bbox timelines** (not physics-linked CV). You still get the full **Valiant SITL** dashboard (FOV + wall side + top-down), a **single-target** suppress → upload → brief hold → COMPLETE flow (override with `-MaxTargets 2`), green extinguished markers, and real MAVLink motion in SITL - without waiting for gimbal/pose-linked perception.

| Label | Mode |
|-------|------|
| `SIM` (top-right of FOV panel) | Timeline synthetic (`sitl` profile) |
| `PHYSICS` | Pose-linked camera (`-Physics`) |

Alternate single-target timeline: `tests/fixtures/sitl_approach.json` via `-Scenario`.

Or with recorded video:

```powershell
.\tools\run_sitl_mission.ps1 -Video recordings\purple_bench.mp4
```

### Cold vs warm start

| Run | Command | Typical startup |
|-----|---------|-----------------|
| **Cold** (first after `launch_sitl.ps1`) | `.\tools\run_sitl_mission.ps1` | EKF wait + arm + takeoff (~30-90 s), then mission |
| **Warm** (SITL still armed/airborne) | `.\tools\run_sitl_mission.ps1 -SkipPreflight` | Mission loop starts immediately |

Arm, GUIDED, and takeoff are handled **inside the orchestrator** (single MAVLink session). No separate arm script is required.

### Physics-linked SITL (geometry validation)

Pose-linked CV: bbox comes from live SITL position + gimbal. Same dashboard and mission flow as `SIM`, but perception is harder (real geometry).

| Window | Shows |
|--------|--------|
| Valiant SITL | Combined grid: FOV (50%) + wall side + top-down |

```powershell
.\tools\run_sitl_mission.ps1 -Physics
```

Already airborne from a prior run? `.\tools\run_sitl_mission.ps1 -Physics -SkipPreflight`

Harder scripted angles (timeline, no physics link):

```powershell
.\tools\run_sitl_mission.ps1 -HardAngles
```

**Mission View overlay:** green arrow = commanded velocity (`cmd`), orange = SITL actual velocity (`sim`).

## Modes

| Flag | MAVLink | Motion | Use |
|------|---------|--------|-----|
| `--sim` | optional | Off | Fast state-machine smoke |
| `--sitl` | tcp:127.0.0.1:5760 | On | Full closed loop |
| (default) | hardware | On | Field |

## Visual feedback

- **OpenCV window:** omit `--headless` on orchestrator (draw_overlay shows state + bbox)
- **Text monitor:** `run_sitl_mission.ps1` opens one automatically, or run `python tools\valiant.py gcs monitor` (UDP port 14560 on localhost)

## Integration tests

With SITL running:

```powershell
.\tools\sitl\run_sitl_tests.ps1
```

Tests include timeline synthetic reaching `APPROACHING` and `COMPLETE` (spray disabled).

## Troubleshooting

**First step for any failure:** `python tools\valiant.py diagnose` (checks venv, WSL, arducopter, log tails).

| Issue | Fix |
|-------|-----|
| `wslpath: C:Users...` / `null-valued expression` on setup | Pull latest; scripts use pure-PS `/mnt/c/...` path mapping (no wslpath) |
| `BASH_SOURCE[0]: unbound variable` in logs | Stale log from old launcher; pull latest, re-run `.\tools\launch_sitl.ps1` |
| `/tmp/common.sh: No such file or directory` | Pull latest (wsl_run sets VALIANT_SITL_SCRIPT_DIR); re-run `.\tools\setup_wsl.ps1` |
| `WSL setup failed` with no build log | Check `~/.valiant_sitl_setup.log` in Ubuntu (`tail -50`). Often sudo password, CRLF on `/mnt/c`, or `.profile` sourcing - fixed in latest `setup_wsl.sh` (pull + re-run) |
| `WSL setup failed` after `install-prereqs-ubuntu.sh end` | Prereqs OK; waf build failed. Re-run `.\tools\setup_wsl.ps1` or manual waf commands in [If setup fails after prereqs](#if-setup-fails-after-prereqs) |
| Build OOM / compiler killed | In Ubuntu: `./waf copter -j2` (lower parallelism) |
| `you need to install empy` during waf | `source ~/venv-ardupilot/bin/activate` then retry build |
| `Unable to locate package python3-future` | Fixed in latest `setup_wsl.sh` (pull repo). Re-run `.\tools\setup_wsl.ps1` |
| `externally-managed-environment` / pip blocked | Script uses `--break-system-packages` on Noble; prefer `sudo apt install python3-empy` |
| `No module named pip` | In **WSL**: `sudo apt install -y python3-empy` |
| `you need to install empy` | In **WSL**: `sudo apt install -y python3-empy` |
| `mavproxy.py` not found | Expected - use `launch_sitl.ps1` (`--no-mavproxy`). Or install MAVProxy in WSL if you want map/console |
| No heartbeat on tcp:5760 | Wait for SITL to finish boot; check WSL2 localhost forwarding |
| First run arm timeout | Wait for EKF/GPS in SITL window; retry once, or use warm `-SkipPreflight` on second run |
| Vehicle does not move | Must be GUIDED + armed; check monitor for `cmd` velocity |
| CV never detects (timeline) | Use default `-Profile sitl` or `-Scenario tests\fixtures\sitl_approach.json` |
| Physics target slow to appear | Gimbal slews after takeoff; use timeline profile for fast tests |
