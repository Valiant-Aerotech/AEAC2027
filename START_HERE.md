# Start Here

**Never run this repo before?** Read this page only. Everything else is reference.

## Step 1 - One-time setup (new laptop)

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
.\start.ps1
```

`start.ps1` creates the Python virtual environment, installs packages, and runs a quick health check.

**Edit config once:** open `config\rpas.yaml` and set `mavlink.connection` to your telemetry COM port (e.g. `COM5`). For laptop-only work, you can skip this until you connect a radio.

---

## Step 2 - Pick what you are doing today

| I want to… | Run this | Needs |
|------------|----------|-------|
| **Smoke-test the install** (no drone) | `python tools\valiant.py quickstart` | Webcam optional |
| **Test target detection on webcam** | `python tools\valiant.py bench cv --camera 0` | USB webcam + purple target |
| **Run full virtual mission** (no hardware) | See [Virtual drone (SITL)](#virtual-drone-sitl) below | WSL + ArduPilot (one-time) |
| **First connect GCS + drone** | `python tools\valiant.py bringup phase1` | Radio + powered Pixhawk |
| **First connect Raspberry Pi** | `bash hardware/vion/rpi/first_connect.sh` | SSH to Pi |
| **Fly Task 2 autonomously** | On Pi: `python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1` | Full bringup done |
| **Watch telemetry on GCS** | `python tools\valiant.py gcs monitor` | Pi sending UDP to laptop |

**Forgot the command?** Run:

```powershell
python tools\valiant.py guide
```

---

## Virtual drone (SITL)

### One-time WSL setup (fresh Windows PC)

From an **Administrator** PowerShell (only needed the first time if WSL is not installed):

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
.\tools\setup_wsl.ps1
```

Same command after a reboot if Windows asked you to restart. Open **Ubuntu** once from the Start menu to create your Linux username/password, then run `.\tools\setup_wsl.ps1` again to finish the ArduPilot build.

If setup fails after a long prereqs step (`install-prereqs-ubuntu.sh end`), prereqs usually succeeded and only the SITL compile failed. **Re-run the same command** - it skips completed steps and retries the build.

Equivalent: `python tools\valiant.py sitl setup-wsl`

**You do not need the repo inside Ubuntu.** Clone to **any** Windows folder (e.g. `C:\Users\...\AEAC2027` or `D:\dev\AEAC2027`). Scripts find the repo from their own location - you can also run the full path `...\AEAC2027\tools\setup_wsl.ps1` from any PowerShell cwd. Only ArduPilot is cloned inside Linux (`~/ardupilot`, public GitHub, no auth).

If the script says Ubuntu not detected but you have an Ubuntu tab: open the **Ubuntu app once** from Start menu (finish username/password), then run `.\tools\setup_wsl.ps1` again from **PowerShell** in the Windows repo folder.

Details: [docs/runbooks/sitl-wsl.md](docs/runbooks/sitl-wsl.md)

**Something failed?** Run `python tools\valiant.py diagnose` for a structured checklist (venv, WSL, arducopter, logs).

### Run a virtual mission (after WSL setup)

**Terminal 1** - start ArduPilot in WSL (leave running):

```powershell
.\tools\launch_sitl.ps1
```

Wait until you see `SERIAL0 on TCP port 5760`.

**Optional - Mission Planner map:** connect **TCP** `127.0.0.1:5762` (leave 5760 for the Valiant mission). Do not start a second SITL from MP Simulation tab. You should see plain `T2:` state lines in **Messages** during the mission. Quick test: `python tools\valiant.py gcs verify-statustext` (with SITL running). Details: [docs/runbooks/sitl-wsl.md](docs/runbooks/sitl-wsl.md#mission-planner-as-gcs-viewer-optional).

**Optional - GUIDED box pattern (no CV):** after SITL is up, `python tools\valiant.py sitl pattern` flies forward/turn legs and ends in LOITER. Good for MAVLink motion check before a full fire mission.

**Terminal 2** - run the Task 2 mission + dashboard:

```powershell
python tools\valiant.py sitl mission
```

### Custom SITL mission (YAML)

Copy [`config/sitl_missions/example_wall.yaml`](config/sitl_missions/example_wall.yaml), edit geofence, wall distance, speeds, and targets, then:

```powershell
python tools\valiant.py sitl run config\sitl_missions\example_wall.yaml
```

Details and troubleshooting: [docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md).

---

## Command cheat sheet

All dev tools go through **one CLI**:

```powershell
python tools\valiant.py --help
python tools\valiant.py guide          # scenario picker (this page, in terminal)
python tools\valiant.py quickstart     # env + CONOPS + safety checks
python tools\valiant.py env check
python tools\valiant.py conops check
python tools\valiant.py bench cv --camera 0
python tools\valiant.py bench metric --camera 0
python tools\valiant.py gcs monitor
python tools\valiant.py gcs verify-statustext
python tools\valiant.py sitl mission
python tools\valiant.py sitl pattern
python tools\valiant.py sitl run config\sitl_missions\example_wall.yaml
python tools\valiant.py bringup phase1
```

Do **not** run the other `tools\*.py` files directly - use `valiant.py` subcommands. See [tools/README.md](tools/README.md).

---

## Common mistakes

| Problem | Fix |
|---------|-----|
| `start.ps1` parse error on `}` | Pull latest; scripts must be ASCII-only (no em-dash characters) |
| Need a feature branch | `git checkout -b feature/topic` from updated `main`; PR into `main` when done |
| `No module named valiant` | Run from repo root; use `python tools\valiant.py`, not `python valiant.py` |
| Forgot to activate venv | Use `.\start.ps1` or `.venv\Scripts\Activate.ps1` |
| MAVLink heartbeat fails | Set `mavlink.connection` in `config\rpas.yaml`; or use `--skip-mavlink` with `bringup phase1` on laptop-only |
| SITL mission can't connect | Start `launch_sitl.ps1` first; wait for port 5760 |
| Wrong mission entry point | **Pi flight** = `hardware/vion/rpi/run_mission.py`. **GCS dev** = `missions/task2_vion_auto_extinguish.py` or SITL above |
| scrcpy / phone camera | GCS legacy path only; competition runs on **Pi camera** |

---

## Where to read next

| Topic | Doc |
|-------|-----|
| Full onboarding | [ONBOARDING.md](ONBOARDING.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Drone + Pi bringup | [docs/runbooks/vion-bringup.md](docs/runbooks/vion-bringup.md) |
| Before hardware day | [docs/runbooks/whats-left-before-hardware.md](docs/runbooks/whats-left-before-hardware.md) |
| Field test phases | [docs/runbooks/field-test-plan.md](docs/runbooks/field-test-plan.md) |
