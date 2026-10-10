# Start Here

**Never run this repo before?** Read this page only. Everything else is reference.

## Step 1 - One-time setup (new laptop)

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
pip install -e ..\valiant-mav
.\start.ps1
```

`start.ps1` creates the Python virtual environment, installs this package, and runs a quick health check.

**Flight library first:** clone [`valiant-mav`](https://github.com/Valiant-Aerotech/valiant-mav) as a sibling of this repo (`../valiant-mav`) and `pip install -e` it before `start.ps1` if the install complains about the dependency.

Skip radio config until you connect hardware. Defaults in `config/defaults.yaml` cover laptop / SITL work.

---

## Step 2 - Pick what you are doing today

| I want to… | Run this | Needs |
|------------|----------|-------|
| **Smoke-test the install** (no drone) | `python tools\valiant.py quickstart` | — |
| **Survey math unit tests** | `python -m pytest tests/test_survey_math.py -q` | — |
| **Survey dry-run** (timers + report, no FC) | `python tools\valiant.py survey --dry-run` | — |
| **Tagtrack dry-run** | `python tools\valiant.py tagtrack --dry-run` | — |
| **Virtual drone motion** (SITL) | See [Virtual drone (SITL)](#virtual-drone-sitl) | WSL + ArduPilot |
| **First connect GCS + drone** | `python tools\valiant.py bringup phase1` | Radio + powered Pixhawk |
| **First connect Raspberry Pi** | `bash hardware/vion/rpi/first_connect.sh` | SSH to Pi |
| **Field GUIDED orbit** | `python tools\valiant.py field orbit --gcs-ip <ip> --laps 1` | [vivi-orbit-field-test.md](docs/runbooks/vivi-orbit-field-test.md) |
| **Watch telemetry on GCS** | `python tools\valiant.py gcs monitor` | Link up |

**Forgot the command?**

```powershell
python tools\valiant.py guide
```

---

## Virtual drone (SITL)

### One-time WSL setup (fresh Windows PC)

From an **Administrator** PowerShell (only needed the first time if WSL is not installed):

```powershell
.\tools\setup_wsl.ps1
```

Equivalent: `python tools\valiant.py sitl setup-wsl`

Details: [docs/runbooks/sitl-wsl.md](docs/runbooks/sitl-wsl.md)

**Something failed?** Run `python tools\valiant.py diagnose`.

### Preferred path (valiant-mav + MAVProxy)

**Terminal 1** — ArduPilot with console/map (default companion port **tcp:5762**):

```bash
cd ~/ardupilot && ./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
```

**Terminal 2** — motion checks:

```powershell
python tools\valiant.py sitl pattern
python tools\valiant.py sitl orbit --laps 1
```

### Legacy Windows wrapper (tcp:5760, no MAVProxy)

```powershell
.\tools\launch_sitl.ps1
```

Wait until you see `SERIAL0 on TCP port 5760`, then run `sitl pattern` / `sitl orbit` as above.

**Optional - Mission Planner map:** TCP `127.0.0.1:5762` when using the MAVProxy path. Quick STATUSTEXT check: `python tools\valiant.py gcs verify-statustext`.

SITL overlays: `config/sitl_missions/orbit.yaml`, `pattern_box.yaml`. Docs: [sitl-overview.md](docs/runbooks/sitl-overview.md).

---

## Missions (2027)

| Task | CLI | Notes |
|------|-----|-------|
| Task 1 survey | `python tools\valiant.py survey --dry-run` | Scoring clocks/clusters/report under `src/valiant/missions/survey/` |
| Task 2 tag & track | `python tools\valiant.py tagtrack --dry-run` | Standoff + Appendix D CSV under `missions/tagtrack/` |

Live MAVLink loops use the same commands without `--dry-run` once SITL or hardware is up. Competition traffic stays loopback until `AEAC_COMP_LIVE=1`.

---

## First connect (hardware)

| Machine | Run first |
|---------|-----------|
| GCS laptop | `python tools\valiant.py bringup phase1` |
| Raspberry Pi (SSH) | `bash hardware/vion/rpi/first_connect.sh` |

More: [docs/runbooks/pi-fresh-install.md](docs/runbooks/pi-fresh-install.md) · [vion-bringup.md](docs/runbooks/vion-bringup.md)

---

## Rules of the road

- Companion **never** terminates the aircraft. FC fence owns FTS (`FENCE_ACTION=2`).
- GUIDED **hold**, not LOITER, for software holds.
- Scoring math lives in `missions/` — not in `perception/` or `comms/`.
- `reference/` is inert 2026 study code. Do not revive it into `src/`.

Competition map: [docs/conops-2027.md](docs/conops-2027.md)
