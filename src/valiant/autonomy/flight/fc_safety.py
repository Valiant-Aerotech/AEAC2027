"""Flight-controller safety.lua preflight checks (hardware field flights)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from pymavlink import mavutil

from valiant.common.mavlink_io import mavlink_io


@dataclass(frozen=True)
class SafetyLuaReport:
    ok: bool
    errors: list[str]
    warnings: list[str]


def fetch_param_value(master: mavutil.mavfile, name: str, *, timeout_s: float = 5.0) -> float | None:
    """Read one FC parameter by name."""
    target_sys = getattr(master, "target_system", 0)
    target_comp = getattr(master, "target_component", 0)
    param_id = name.encode("utf-8")[:16]
    with mavlink_io(master):
        master.mav.param_request_read_send(target_sys, target_comp, param_id, -1)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with mavlink_io(master):
            msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if msg is None or msg.get_srcSystem() != target_sys:
            continue
        raw_id = msg.param_id
        if isinstance(raw_id, bytes):
            pid = raw_id.decode("utf-8", errors="ignore").rstrip("\x00")
        else:
            pid = str(raw_id).rstrip("\x00")
        if pid == name:
            return float(msg.param_value)
    return None


def verify_safety_lua(
    master: mavutil.mavfile,
    cfg: dict,
    *,
    sitl: bool = False,
) -> SafetyLuaReport:
    """Verify SCR_ENABLE and optional safety.lua file on FC SD card."""
    safety_cfg = cfg.get("safety", {})
    if sitl or not safety_cfg.get("require_lua_safety", True):
        return SafetyLuaReport(True, [], ["Lua safety check skipped (SITL or disabled)"])

    errors: list[str] = []
    warnings: list[str] = []
    script_name = str(safety_cfg.get("lua_safety_script", "safety.lua"))

    scr_enable = fetch_param_value(master, "SCR_ENABLE")
    if scr_enable is None:
        errors.append("Could not read SCR_ENABLE — is MAVLink connected to the flight controller?")
    elif scr_enable < 0.5:
        errors.append(
            f"SCR_ENABLE={scr_enable:.0f} (need 1). "
            "Enable scripting in Mission Planner, reboot FC, copy safety.lua to APM/scripts/."
        )
    else:
        print("[Safety] SCR_ENABLE=1 (scripting enabled)")

    if safety_cfg.get("verify_lua_file", True):
        present = _mavftp_script_on_sd(master, script_name, timeout_s=8.0)
        if present is True:
            print(f"[Safety] Found scripts/{script_name} on FC SD card")
        elif present is False:
            errors.append(
                f"scripts/{script_name} not found on FC SD card. "
                f"Copy hardware/vion/lua/{script_name} to APM/scripts/ via Mission Planner MAVFTP."
            )
        else:
            warnings.append(
                f"Could not verify scripts/{script_name} via MAVFTP. "
                "Confirm in Mission Planner CONFIG → MAVFTP, or check Messages for "
                "'safety: kill monitor loaded' after FC reboot."
            )

    return SafetyLuaReport(ok=not errors, errors=errors, warnings=warnings)


def assert_safety_lua(
    master: mavutil.mavfile,
    cfg: dict,
    *,
    sitl: bool = False,
) -> None:
    """Raise RuntimeError if safety.lua preflight fails."""
    report = verify_safety_lua(master, cfg, sitl=sitl)
    for warning in report.warnings:
        print(f"[Safety] WARN: {warning}")
    if report.ok:
        print("[Safety] safety.lua preflight OK")
        return
    for err in report.errors:
        print(f"[Safety] FAIL: {err}")
    raise RuntimeError("Safety Lua preflight failed — fix before flight")


def _mavftp_script_on_sd(
    master: mavutil.mavfile,
    script_name: str,
    *,
    timeout_s: float = 8.0,
) -> bool | None:
    """Return True if scripts/<name> exists on FC, False if missing, None if FTP unavailable."""
    try:
        from pymavlink import mavftp
    except ImportError:
        return None

    target_sys = getattr(master, "target_system", 0)
    target_comp = getattr(master, "target_component", 0)
    try:
        client = mavftp.MAVFTP(master, target_sys, target_comp)
        result = client.cmd_ftp(["list", "scripts"])
        if result.error_code != mavftp.FtpError.Success:
            return None
    except Exception:
        return None

    names = {entry.name for entry in client.list_result}
    if not names:
        return None
    return script_name in names
