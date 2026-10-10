# SITL on WSL (Windows)

ArduPilot SITL runs inside Ubuntu (WSL). Companion Python stays on Windows and
talks MAVLink over TCP.

## One-time setup

From an **Administrator** PowerShell in the repo:

```powershell
.\tools\setup_wsl.ps1
```

Or: `python tools\valiant.py sitl setup-wsl`

Open **Ubuntu** once from Start to create your Linux user if prompted, then
re-run the script. ArduPilot clones to `~/ardupilot` inside Linux (public
GitHub — no org auth).

Troubleshoot: `python tools\valiant.py diagnose`.

## Daily: preferred MAVProxy path

In Ubuntu:

```bash
cd ~/ardupilot && ./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
```

On Windows (companion / mission tools):

```powershell
python tools\valiant.py sitl pattern
python tools\valiant.py sitl orbit --laps 1
```

Default companion URL for valiant-mav: **tcp:127.0.0.1:5762**.

### Mission Planner as map viewer

Connect Mission Planner **TCP** to `127.0.0.1:5762`. Do not start a second
SITL from the Simulation tab. Verify STATUSTEXT with
`python tools\valiant.py gcs verify-statustext`.

## Daily: legacy launch_sitl.ps1 (tcp:5760)

```powershell
.\tools\launch_sitl.ps1
```

Wait for `SERIAL0 on TCP port 5760`, then run `sitl pattern` / `sitl orbit`.
This path uses `--no-mavproxy`; Mission Planner should use **5762** only if a
proxy is added separately — prefer the `sim_vehicle --console --map` path.

## Guided box pattern / orbit

```powershell
python tools\valiant.py sitl pattern          # box legs → GUIDED hold
python tools\valiant.py sitl orbit --laps 1   # field geometry → GUIDED hold
```

These validate motion before any survey/tagtrack loop. They do **not** run
legacy fire/extinguish code.

## Survey / tagtrack without FC

```powershell
python tools\valiant.py survey --dry-run
python tools\valiant.py tagtrack --dry-run
```

Scoring clocks, clusters, reports, and track CSV are exercised offline.

## Pytest SITL markers

```powershell
python -m pytest tests/sitl -m sitl -q
```

Default `pytest` excludes `-m sitl` (see `pyproject.toml`).

More context: [sitl-overview.md](sitl-overview.md) · sibling `../valiant-mav/docs/sitl.md`.
