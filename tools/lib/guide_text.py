"""Printed scenario guide for valiant.py (mirrors START_HERE.md)."""

GUIDE = """
Valiant AEAC2027 - what should I run?
=====================================

ONE-TIME SETUP (new laptop)
  .\\start.ps1
  notepad config\\vion.yaml     # set mavlink.connection (COM port)

NO DRONE - try software on this laptop
  python tools\\valiant.py quickstart
  python tools\\valiant.py diagnose      # if something fails
  python tools\\valiant.py bench cv --camera 0
  python tools\\valiant.py bench metric --camera 0

VIRTUAL DRONE (SITL) - two terminals
  One-time WSL setup:  .\\tools\\setup_wsl.ps1
                       (or: python tools\\valiant.py sitl setup-wsl)
  Terminal 1:          .\\tools\\launch_sitl.ps1
  Terminal 2:          python tools\\valiant.py sitl mission
                       python tools\\valiant.py sitl run config\\sitl_missions\\example_wall.yaml
  Docs:                docs\\runbooks\\sitl-wsl.md

FIRST CONNECT - GCS laptop + drone (props off)
  python tools\\valiant.py bringup phase1
  python tools\\valiant.py gcs spray          # SERVO15 test
  Docs:        docs\\runbooks\\vion-bringup.md

FIRST CONNECT - Raspberry Pi (SSH)
  bash hardware/vion/rpi/first_connect.sh
  python tools\\valiant.py bringup phase1-pi   # on Pi, after sensors wired

COMPETITION FLIGHT - Task 2 autonomous
  Pi:  python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1
  GCS: python tools\\valiant.py gcs monitor

GCS DEV / LEGACY (scrcpy or webcam on laptop)
  python missions\\task2_vion_auto_extinguish.py --sim --source webcam --camera 0
  python missions\\task2_vion_manual_photo.py --camera 0

Full walkthrough: START_HERE.md
Tool reference:   tools\\README.md
"""

QUICKSTART_NEXT = """
Next steps (pick one):
  - Webcam CV test:      python tools\\valiant.py bench cv --camera 0
  - Virtual mission:     .\\tools\\launch_sitl.ps1  then  python tools\\valiant.py sitl mission
  - Drone first connect: python tools\\valiant.py bringup phase1
  - Show this menu:      python tools\\valiant.py guide
"""
