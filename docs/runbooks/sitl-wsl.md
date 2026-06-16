# SITL on WSL2 (Windows)

Software-in-the-loop testing with **ArduPilot SITL** + AEAC orchestrator. No physical drone required.

Inspired by [Stanley](https://github.com/Matchstic/stanley) patterns; we use **pymavlink** + WSL `sim_vehicle.py` (not dronekit-sitl).

## One-time WSL setup

1. Install WSL2 Ubuntu
2. Clone and build ArduPilot ([dev setup](https://ardupilot.org/dev/docs/building-setup-linux.html)):

```bash
sudo apt update
sudo apt install -y git python3-pip python3-dev
git clone https://github.com/ArduPilot/ardupilot.git ~/ardupilot
cd ~/ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
./waf configure --board sitl
./waf copter
```

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
./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
```

In the SITL console after startup:

```
mode guided
arm throttle
```

(Or use Mission Planner connected to SITL UDP if configured.)

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

## Modes

| Flag | MAVLink | Motion | Use |
|------|---------|--------|-----|
| `--sim` | optional | Off | Fast state-machine smoke |
| `--sitl` | tcp:127.0.0.1:5760 | On | Full closed loop |
| (default) | hardware | On | Field |

## Visual feedback

- **OpenCV window:** omit `--headless` on orchestrator (draw_overlay shows state + bbox)
- **Text monitor:** `.\tools\run_monitor.ps1` (localhost UDP when `-MonitorHost 127.0.0.1`)

## Integration tests

With SITL running:

```powershell
.\tools\run_sitl_tests.ps1
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No heartbeat on tcp:5760 | Wait for SITL to finish boot; check WSL2 localhost forwarding |
| Vehicle does not move | Must be GUIDED + armed in SITL |
| CV never detects | Use `-Scenario` synthetic JSON or purple test video |
