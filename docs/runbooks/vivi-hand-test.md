# Hand-carry bench test (props off) — Pi runs perception, GCS monitors only.
#
# Pi (SSH):
#   cd ~/AEAC2027 && source .venv/bin/activate
#   python hardware/vion/rpi/run_mission.py --profile vivi --hand-test --max-targets 1 --gcs-ip <laptop-ip>
#
# GCS:
#   .\tools\run_monitor.ps1
#
# Procedure:
# 1. Props OFF. Power FC + Pi. Mission Planner connected via telemetry radio.
# 2. Start monitor on GCS, then run_mission on Pi with --hand-test.
# 3. Hold the airframe and move it by hand toward/away from a purple target.
# 4. Pass criteria:
#    - Monitor shows target_seen=Y when aimed at target
#    - state advances SEARCHING -> APPROACHING (and toward AIMING when close)
#    - dist_m or dist band updates as you move
#    - Mission Planner HUD shows T2: statustext from Pi
#    - No velocity commands sent (hand_test=Y on monitor)
#
# Next step after pass: tethered test WITHOUT --hand-test (still props off, hold frame).
