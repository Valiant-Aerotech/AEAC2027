"""Mapping between gimbal pitch angle and servo PWM.

Pure arithmetic against the pwm_min/pwm_max/pwm_neutral calibration in config.
Lives in core because both the gimbal driver and the simulated camera need it,
and the simulated camera must not be the one that owns it.
"""

from __future__ import annotations


def pwm_to_gimbal_pitch_deg(
    pwm: int,
    *,
    pwm_min: int = 1000,
    pwm_max: int = 2000,
    pwm_neutral: int = 1500,
    pitch_up_deg: float = 25.0,
    pitch_down_deg: float = 60.0,
) -> float:
    """Positive pitch_deg = camera pitched down from body forward axis."""
    if pwm >= pwm_neutral:
        span = max(pwm_max - pwm_neutral, 1)
        return pitch_down_deg * (pwm - pwm_neutral) / span
    span = max(pwm_neutral - pwm_min, 1)
    return -pitch_up_deg * (pwm_neutral - pwm) / span


def gimbal_pitch_deg_to_pwm(
    pitch_deg: float,
    *,
    pwm_min: int = 1000,
    pwm_max: int = 2000,
    pwm_neutral: int = 1500,
    pitch_up_deg: float = 25.0,
    pitch_down_deg: float = 60.0,
) -> int:
    if pitch_deg >= 0:
        span = max(pwm_max - pwm_neutral, 1)
        pwm = pwm_neutral + (pitch_deg / max(pitch_down_deg, 1e-3)) * span
    else:
        span = max(pwm_neutral - pwm_min, 1)
        pwm = pwm_neutral + (pitch_deg / max(pitch_up_deg, 1e-3)) * span
    return int(max(pwm_min, min(pwm_max, round(pwm))))
