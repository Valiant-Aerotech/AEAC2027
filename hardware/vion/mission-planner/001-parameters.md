## GPS Configuration (First Time)
https://docs.cubepilot.org/user-guides/here-4/here-4-manual
- `CAN_D1_PROTOCOL` : `1`
- `CAN_D2_PROTOCOL` : `1`
- `CAN_P1_DRIVER` : `1`
- `CAN_P2_DRIVER` : `1`
- `GPS_TYPE` : `9`
- `NTF_LED_TYPES` : `231`

## RC Configuration
- `RC_Options` : `1056`
- `RSSI_TYPE` : `3`
- `SERIAL2_PROTOCOL` : `23`

## Motor Configuration
Motor Orientation (9-12), pins (1-4)
- `MOT_PWM_TYP` : `6` (As we're using a DShot 600)
- `BRD_IO_DSHOT` : `1`
- `BRD_SAFETY_DEFLT` = `0`
- `ESC_CALIBRATION` = `3`

## Battery Monitor
Restart shit until it works
- `BATT_MONITOR` : `4`
- `BATT_AMP_OFFSET` : `0.63`
- `BATT_AMP_PERVLT` : `37.23`
- `BATT_VOLT_MULT` : `18.4615`

## Scripting
- `SCR_ENABLE` : `1`

## Holybro H-Flow (indoor optical flow + downward lidar)

Mount rigidly facing down, clear of props. Connect to Pixhawk CAN bus (same as HERE4).

Per Holybro / ArduPilot docs (verify against your firmware version):

- `FLOW_TYPE` : `6` (DroneCAN)
- `RNGFND1_TYPE` : `24` (DroneCAN rangefinder)
- Set `FLOW_POS_X/Y/Z` for mount offset from CG
- Set `RNGFND1_POS_X/Y/Z` to match flow sensor bore-sight

Indoor flight profile uses `GUIDED_NOGPS` on the Pi companion. Monitor `opt_qua` in Mission Planner during bench hover.

Target range for extinguish comes from ArduCam ToF on the Pi, not H-Flow lidar.