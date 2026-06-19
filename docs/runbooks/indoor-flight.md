# Indoor flight (Vion)

Indoor Task 2 uses target-relative visual servo with no GPS. Pixhawk holds attitude via EKF; Holybro H-Flow provides optical flow and downward lidar for hover stability.

**First-time setup:** [vion-bringup.md](vion-bringup.md)
## Config

```yaml
flight:
  profile: indoor
  require_gps: false
  mode: GUIDED_NOGPS
  arm_check_gps: false

metric_recon:
  rangefinder: depth_at_target

camera:
  source: rpi_local
```

Or CLI:

```bash
python hardware/vion/rpi/run_mission.py --profile indoor
```

## Pixhawk setup (Mission Planner)

1. Enable DroneCAN for Holybro H-Flow on CAN bus with HERE4
2. Set optical flow and rangefinder params (see `hardware/vion/mission-planner/001-parameters.md`)
3. Bench test hover over venue-like flooring; watch `opt_qua` in Mission Planner
4. Disable or relax GPS-dependent geofence for indoor runs

## Sensor division

| Sensor | Provides |
|--------|----------|
| H-Flow downward ToF | Drone altitude (EKF Z) |
| H-Flow optical flow | Lateral drift control in GUIDED_NOGPS |
| ArduCam ToF at target pixel | Range to purple target (approach, 2 m gate, fire) |

## GCS monitor

GCS link loss does not abort the mission. Pi continues autonomously.

```powershell
python tools\valiant.py gcs monitor
```

## Validation

Before indoor flight:

1. `python tools\valiant.py calibrate validate` passes 10% depth gate at 1/2/3 m
2. Tethered MAVLink velocity test with `--sim` on Pi
3. Phase 2.2-2.3 from `docs/runbooks/field-test-plan.md` indoors
