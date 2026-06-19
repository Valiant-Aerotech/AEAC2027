# Drone Fleet

## RPAS (default platform)

- **Name:** Remotely Piloted Aircraft System
- **Role:** Generic Task 2 software platform (scripts, SITL, GCS tools default here)
- **Config:** `config/rpas.yaml` (inherits airframe tuning from `config/vion.yaml`)
- **Calibration:** `config/rpas_calibration.yaml` (from `rpas_calibration.yaml.example`)

Fleet-specific hardware folders (`hardware/vion/`, etc.) stay named for each aircraft.

## Vulcan 2

- **Role:** Heavy lifter
- **Payload:** Carries Vivi (surveying drone)
- **Software:** `hardware/vulcan2/` - FC parameters and Lua scripts only
- **Python missions:** None yet

## Vion

- **Role:** Fire suppression
- **Hardware:** Pixhawk 6C, Raspberry Pi companion, Holybro H-Flow (DroneCAN), AI camera + ArduCam ToF on Pi, water trigger on AUX 7 / SERVO15
- **Payload:** Up to ~900g (proved 3 laps in 2025-2026)
- **Software:** Full Task 2 autonomy on onboard RPi; GCS laptop for calibration, monitor, manual fallback
- **Missions:**
  - `hardware/vion/rpi/run_mission.py` - primary autonomous (onboard)
  - `missions/task2_vion_auto_extinguish.py` - GCS dev / legacy fallback
  - `missions/task2_vion_manual_photo.py` - manual fallback
- **Config:** `config/vion.yaml` (airframe tuning base inherited by `config/rpas.yaml`)
- **Calibration:** legacy `config/vion_calibration.yaml` still merged if present; prefer `config/rpas_calibration.yaml` on new Pis

## Vivi

- **Role:** Small surveying drone for Task 1
- **Carrier:** Deployed from Vulcan 2
- **Software:** Task 1 building survey and target localization report
- **Mission:** `missions/task1_vivi_survey.py`
- **Config:** `config/vivi.yaml`
