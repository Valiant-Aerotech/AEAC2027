"""Printed scenario guide for valiant.py (mirrors START_HERE.md)."""

GUIDE = """
Valiant AEAC2027 - what should I run?
=====================================

ONE-TIME SETUP (new laptop)
  pip install -e ..\\valiant-mav
  .\\start.ps1
  (optional) copy .env.example to .env for competition token — leave AEAC_COMP_LIVE=0

NO DRONE - try software on this laptop
  python tools\\valiant.py quickstart
  python tools\\valiant.py diagnose
  python tools\\valiant.py boundary check
  python -m pytest tests/test_survey_math.py tests/test_boundary.py -q

VIRTUAL DRONE (SITL) - two terminals
  One-time WSL setup:  .\\tools\\setup_wsl.ps1
                       (or: python tools\\valiant.py sitl setup-wsl)
  Prefer MAVProxy path (valiant-mav default tcp:5762):
    WSL:  cd ~/ardupilot && ./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
  Or legacy Windows wrapper (tcp:5760, --no-mavproxy):
    Terminal 1:  .\\tools\\launch_sitl.ps1
  Then:          python tools\\valiant.py sitl pattern
                 python tools\\valiant.py sitl orbit --laps 1
  Docs:          docs\\runbooks\\sitl-wsl.md  and  ../valiant-mav/docs/sitl.md

FIRST CONNECT - GCS laptop + drone (props off)
  python tools\\valiant.py bringup phase1
  python tools\\valiant.py gcs params
  python tools\\valiant.py gcs heartbeat
  Docs: docs\\runbooks\\vion-bringup.md

FIRST CONNECT - Raspberry Pi (SSH)
  bash hardware/vion/rpi/first_connect.sh
  python tools\\valiant.py bringup phase1-pi

FIELD ORBIT (outdoor, no CV)
  Pi:  python hardware/vion/rpi/run_field_orbit.py --profile vivi_orbit --gcs-ip <ip> --laps 1
  Docs: docs\\runbooks\\vivi-orbit-field-test.md

MISSIONS (2027)
  Task 1 survey (dry-run offline):
    python tools\\valiant.py survey --dry-run
    python tools\\valiant.py survey --dry-run --report artifacts\\survey_report.txt --ocr
  Task 2 tagtrack (dry-run offline):
    python tools\\valiant.py tagtrack --dry-run
    python tools\\valiant.py tagtrack --dry-run --log artifacts\\tagtrack_log.csv
  Unit tests:  python -m pytest tests/test_survey_math.py tests/test_survey_runner.py tests/test_tagtrack.py -q

Full walkthrough: START_HERE.md
Tool reference:   tools\\README.md
Competition notes: docs\\conops-2027.md
"""

QUICKSTART_NEXT = """
Next steps (pick one):
  - Survey dry-run:      python tools\\valiant.py survey --dry-run
  - Tagtrack dry-run:    python tools\\valiant.py tagtrack --dry-run
  - SITL pattern:        start sim_vehicle or launch_sitl.ps1, then sitl pattern
  - Drone first connect: python tools\\valiant.py bringup phase1
  - Show this menu:      python tools\\valiant.py guide
"""
