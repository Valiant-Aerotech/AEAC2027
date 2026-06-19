# Nav PID tuning

Tune visual servo gains in `config/vion.yaml` under `auto_nav`.

## Key parameters

| Parameter | Effect |
|-----------|--------|
| `kp_x`, `kp_y` | Lateral/vertical correction gain |
| `kd_x`, `kd_y` | Damping (reduce oscillation) |
| `deadband_px` | Ignore small pixel errors near centre |
| `max_vel` | Cap body-frame velocity |
| `approach_speed` | Base forward speed during APPROACHING |
| `approach_slow_start_m` | Begin slowing when closer than this |
| `approach_min_speed_factor` | Minimum speed fraction at fire distance |

## Procedure

1. Run tethered with `--sim` first (no velocity commands)
2. Log mission on Pi in `logs/mission/`
3. Adjust gains; verify AIMING holds target centred
4. Verify distance scaling slows approach before `fire_distance_m` (0.8 m)

Indoor profile: `python hardware/vion/rpi/run_mission.py --profile indoor`

Outdoor profile (field-tuned HSV + nav gains): `--profile outdoor`

GCS dev: `python missions/task2_vion_auto_extinguish.py --sim --source webcam`
