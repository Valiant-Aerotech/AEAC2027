local EMERGENCY_BUTTON_RC = 8
local SWITCH_LOW_THRESHOLD = 1300
local POLL_MS = 100
local ALTITUDE_THRESHOLD_M = 1.0
local LAND = 9

if not _G._valiant_safety_announced then
    _G._valiant_safety_announced = true
    gcs:send_text(6, "safety: kill monitor loaded (RC8)")
end

local function handle_emergency_disarm()
    local pwm = rc and rc.get_pwm and rc:get_pwm(EMERGENCY_BUTTON_RC) or 1500

    if pwm > SWITCH_LOW_THRESHOLD then
        gcs:send_text(4, "safety: EMERGENCY FLIP SWITCH ACTIVATED (HIGH -> LOW)!")
      
        if arming:is_armed() then
            if vehicle:get_mode() ~= LAND then
                gcs:send_text(4, string.format("safety: High alt. Setting mode to LAND."))
                vehicle:set_mode(LAND)
            end
            
            if not vehicle:get_likely_flying() then
                gcs:send_text(4, string.format("safety: Low alt or already landing. Initiating disarm."))
                arming:disarm()
            end
        end
    end
    
    return handle_emergency_disarm, POLL_MS
end

return handle_emergency_disarm, POLL_MS