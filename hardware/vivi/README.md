# Vivi Hardware

Small surveying drone for Task 1. Carried by Vulcan 2. Also used as **Vivi bench** for Task 2 stack on the Pi companion.

## FC

- **Board:** Holybro Kakute H7 (ArduPilot)
- **Wiring (Pi UART):** [WIRING.md](WIRING.md)
- **Params:** [mission-planner/001-kakute-h7.md](mission-planner/001-kakute-h7.md)
- **Gimbal:** pitch-axis camera servo (channel in `config/vion.yaml` → `flight_profiles.vivi.gimbal`)

## Field day (outdoor GPS)

| Run | Command |
|-----|---------|
| Setup + preflight | [docs/runbooks/pi-fresh-install.md](../../docs/runbooks/pi-fresh-install.md) |
| Run 1 — orbit | `bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <ip> --laps 1` |
| Run 2 — CV mission | `bash hardware/vion/rpi/pi_field_ready.sh --mission --gcs-ip <ip> --max-targets 1` |

Full day guide: [docs/runbooks/vivi-outdoor-field-day.md](../../docs/runbooks/vivi-outdoor-field-day.md)

## Software

| Mission | Entry |
|---------|-------|
| Task 1 survey | `python missions/task1_vivi_survey.py` |
| Task 2 bench (Pi) | `python hardware/vion/rpi/run_mission.py --profile vivi` |
| Task 2 outdoor (field) | `pi_field_ready.sh --mission` (profile `vivi_outdoor_mission`) |

Hand-carry test: [docs/runbooks/vivi-hand-test.md](../../docs/runbooks/vivi-hand-test.md)
