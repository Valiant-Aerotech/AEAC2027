# Vivi Hardware

Small surveying drone for Task 1. Carried by Vulcan 2. Also used as **onboard-Pi bench** for Task 2 stack (`onboard-pi` branch).

## FC

- **Board:** Holybro Kakute H7 (ArduPilot)
- **Params:** [`mission-planner/001-kakute-h7.md`](mission-planner/001-kakute-h7.md)
- **Gimbal:** pitch-axis camera servo (channel in `config/vion.yaml` → `flight_profiles.vivi.gimbal`)

## Software

| Mission | Entry |
|---------|-------|
| Task 1 survey | `python missions/task1_vivi_survey.py` |
| Task 2 bench (Pi) | `python hardware/vion/rpi/run_mission.py --profile vivi` |

Hand-carry test: [`docs/runbooks/vivi-hand-test.md`](../docs/runbooks/vivi-hand-test.md)
