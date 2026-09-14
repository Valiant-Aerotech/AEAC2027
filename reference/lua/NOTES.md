# 2026 Lua scripts (study copies)

Inert. Do not copy these onto an SD card and fly them.

Live kill switch: `hardware/vion/lua/safety.lua` — edit that file for flight, not these.

| File | What it was | Use it for |
|------|-------------|------------|
| `safety.lua` | RC8 kill → LAND, then disarm on the ground | How an FC-side last line of defence is structured *after* the polarity fix |
| `payload.lua` | RC10 cycles SERVO14 through four PWM states | Tracker release / sample gripper: servo behind a switch |
| `arm.lua` | Script arms the vehicle by itself, waits, disarms | **Warning.** Auto-arm from Lua has no business on a field aircraft |
| `throttle_two.lua` | Bench climb test **and** the old kill-switch default | The fail-dangerous `or 1500` is still in this file — that is the bug |
| `stabilize.lua` | RC5 forces STABILIZE; same `or 1500` default | Same polarity lesson on a different channel |

## The kill-switch polarity bug

The pre-fix `safety.lua` (and `throttle_two.lua` still) did:

```lua
local pwm = rc and rc.get_pwm and rc:get_pwm(EMERGENCY_BUTTON_RC) or 1500
if pwm > SWITCH_LOW_THRESHOLD then
    -- LAND and disarm
end
```

`SWITCH_LOW_THRESHOLD` is 1300. Mid-stick 1500 is above that. If RC8 was unconfigured, unreadable, or the `rc` table was missing, the script behaved exactly as if someone was holding the kill switch. A healthy aircraft went into LAND.

A kill switch must fail to **no kill**. Missing input is not a command. The live `safety.lua` returns `nil` below 800 PWM and does nothing. Bench-test polarity with props off before every field day.

Full write-up: [docs/lessons-learned.md](../../docs/lessons-learned.md) — “A missing RC channel looked like a kill switch”.
