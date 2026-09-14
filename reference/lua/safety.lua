-- STUDY COPY. Inert. Live flight script: hardware/vion/lua/safety.lua
-- Learn: RC8 kill must fail to "no kill"; missing PWM is not a command. See NOTES.md.

-- Independent kill switch, running on the flight controller itself.
--
-- Watches RC channel 8. When the switch goes high the aircraft is put into
-- LAND, and once it is no longer flying it is disarmed. This runs on the FC,
-- so it works with the companion computer powered off, crashed or unplugged -
-- which is the point. It is the last line of defence and must not depend on
-- anything we wrote in Python.
--
-- Bench-test the polarity before every field day: arm on the bench with props
-- off, flip the switch, confirm "kill switch ARMED" appears in the Mission
-- Planner Messages tab, and confirm it does NOT appear at rest.

local KILL_SWITCH_CHANNEL = 8

-- Trigger when the channel goes above this. A two-position switch reads about
-- 1000 low and 2000 high, so 1300 puts the threshold safely above the low
-- position. If your transmitter is reversed, reverse the channel on the
-- transmitter rather than editing this file - the FC parameters and this
-- script should agree with the label on the switch.
local TRIGGER_ABOVE_PWM = 1300

local POLL_MS = 100
local MODE_LAND = 9

if not _G._valiant_safety_announced then
    _G._valiant_safety_announced = true
    gcs:send_text(6, "safety: kill monitor loaded (RC8)")
end

local announced_trigger = false

local function read_kill_pwm()
    -- Returns nil when the channel cannot be read, and the caller treats that
    -- as "not triggered".
    --
    -- The previous version of this file defaulted to 1500 here, which is above
    -- TRIGGER_ABOVE_PWM. An unconfigured or unreadable RC8 therefore looked
    -- exactly like someone holding the kill switch, so the script would put a
    -- healthy aircraft into LAND and disarm it. A kill switch must fail to
    -- "no kill": a missing input is not a command.
    if not rc or not rc.get_pwm then
        return nil
    end
    local ok, pwm = pcall(function()
        return rc:get_pwm(KILL_SWITCH_CHANNEL)
    end)
    if not ok or pwm == nil or pwm < 800 then
        -- Below 800 means no signal at all rather than a low switch position.
        return nil
    end
    return pwm
end

local function handle_emergency_disarm()
    local pwm = read_kill_pwm()

    if pwm == nil then
        return handle_emergency_disarm, POLL_MS
    end

    if pwm <= TRIGGER_ABOVE_PWM then
        announced_trigger = false
        return handle_emergency_disarm, POLL_MS
    end

    if not announced_trigger then
        announced_trigger = true
        gcs:send_text(4, "safety: kill switch ARMED - landing now")
    end

    if arming:is_armed() then
        if vehicle:get_mode() ~= MODE_LAND then
            vehicle:set_mode(MODE_LAND)
        end
        if not vehicle:get_likely_flying() then
            gcs:send_text(4, "safety: on the ground - disarming")
            arming:disarm()
        end
    end

    return handle_emergency_disarm, POLL_MS
end

return handle_emergency_disarm, POLL_MS
