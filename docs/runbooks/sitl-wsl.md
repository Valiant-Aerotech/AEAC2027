# SITL on WSL2 (Windows)

Software-in-the-loop testing with **ArduPilot SITL** + AEAC orchestrator. No physical drone required.

Inspired by [Stanley](https://github.com/Matchstic/stanley) patterns; we use **pymavlink** + WSL `sim_vehicle.py` (not dronekit-sitl).

## One-time WSL setup

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

(`empy==3.3.4` is required by ArduPilot's waf build — install in **WSL** via `python3-empy`, not the Windows `.venv`.)

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

If you see `No such file or directory` for the `.sh` path, update `launch_sitl.ps1` (uses `wslpath`) or run directly in WSL:

```bash
cd ~/ardupilot
./Tools/autotest/sim_vehicle.py -v ArduCopter --no-mavproxy
```

The ArduCopter window shows `SERIAL0 on TCP port 5760` — that is normal. AEAC connects directly; MAVProxy is **not** required.

Arm and set GUIDED from **Windows** (Terminal 2, or before mission):

```powershell
$env:PYTHONPATH="src"
python tools\sitl_arm_guided.py
```

(`run_sitl_mission.ps1` calls this automatically.)

Optional: install MAVProxy in WSL if you want ArduPilot's map/console UI:

```bash
python3 -m pip install --user --break-system-packages MAVProxy
./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
```

## Run mission against SITL

**No physical drone required** — SITL is a software flight controller on your laptop.

**Terminal 2** (from repo root):

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\tools\run_sitl_mission.ps1 -Profile sitl
```

Or with recorded video:

```powershell
.\tools\run_sitl_mission.ps1 -Profile sitl -Video recordings\purple_bench.mp4
```

### Physics-linked SITL (ArduPilot gravity + real motion)

Targets sit on a **wall** 5 m ahead; three OpenCV windows:

| Window | Shows |
|--------|--------|
| Valiant Mission View | Camera + velocity arrows |
| SITL Top-Down | Drone, heading, wall line, targets (map) |
| SITL Wall View | Side profile: drone altitude vs wall + target |

```powershell
.\tools\run_sitl_mission.ps1 -Physics
```

One MAVLink session: orchestrator arms, **takeoff to 3 m**, then runs the mission (no separate arm script). If the first connect fails, it retries automatically.

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
- **Text monitor:** `run_sitl_mission.ps1` opens one automatically, or run `.\tools\run_monitor.ps1` (UDP port 14560 on localhost)

## Integration tests

With SITL running:

```powershell
.\tools\run_sitl_tests.ps1
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `externally-managed-environment` / pip blocked | In **WSL**: `sudo apt install -y python3-empy` (do not use Windows pip) |
| `No module named pip` | In **WSL**: `sudo apt install -y python3-empy` |
| `you need to install empy` | In **WSL**: `sudo apt install -y python3-empy` |
| `mavproxy.py` not found | Expected — use `launch_sitl.ps1` (`--no-mavproxy`). Or install MAVProxy in WSL if you want map/console |
| No heartbeat on tcp:5760 | Wait for SITL to finish boot; check WSL2 localhost forwarding |
| Vehicle does not move | Must be GUIDED + armed in SITL |
| CV never detects | Use `-Scenario` synthetic JSON or purple test video |
