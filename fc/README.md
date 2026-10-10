`safety.lua` runs on ArduPilot only. PX4 will not load it.

A missing RC channel must not look like a kill. If the channel cannot be read, the script does nothing.

`arm.lua` and `throttle_two.lua` stay on the `legacy` branch and must not be loaded. There is no deploy script and no copy into PX4 ROMFS.
