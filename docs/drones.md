# Drone Fleet

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
- **Config:** `config/vion.yaml`, `config/vion_calibration.yaml`

## Vivi

- **Role:** Small surveying drone for Task 1
- **Carrier:** Deployed from Vulcan 2
- **Software:** Task 1 building survey and target localization report
- **Mission:** `missions/task1_vivi_survey.py`
- **Config:** `config/vivi.yaml`
