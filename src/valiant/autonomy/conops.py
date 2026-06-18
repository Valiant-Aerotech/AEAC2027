"""CONOPS helpers - photo naming, config sync, validation."""

from __future__ import annotations

import re
from typing import Any

from valiant.autonomy.packets import CVPacket


def task2_settings(cfg: dict) -> dict[str, Any]:
    return cfg.get("conops", {}).get("task2", {})


def team_name(cfg: dict) -> str:
    return cfg.get("team", {}).get("name", "ValiantAerotech")


def task2_photo_filename(cfg: dict, target_number: int) -> str:
    """CONOPS photo name: Task_2_{team}_target_{n}.jpg"""
    template = task2_settings(cfg).get(
        "photo_filename_template",
        "Task_2_{team}_target_{n}.jpg",
    )
    safe_team = re.sub(r"[^\w\-]+", "_", team_name(cfg)).strip("_")
    return template.format(team=safe_team, n=target_number)


def task1_report_filename(cfg: dict) -> str:
    template = cfg.get("conops", {}).get("task1", {}).get(
        "report_filename_template",
        "Task_1_{team}_targets.txt",
    )
    safe_team = re.sub(r"[^\w\-]+", "_", team_name(cfg)).strip("_")
    return template.format(team=safe_team)


def apply_conops_to_runtime(cfg: dict) -> dict:
    """Copy CONOPS task2 limits into operational config sections."""
    t2 = task2_settings(cfg)
    if not t2:
        return cfg

    metric = cfg.setdefault("metric_recon", {})
    if "min_approach_distance_m" in t2:
        metric["min_approach_distance_m"] = t2["min_approach_distance_m"]
    if "target_diameter_max_m" in t2:
        metric["target_diameter_m"] = t2["target_diameter_max_m"]
    if "target_diameter_min_m" in t2:
        metric["target_diameter_min_m"] = t2["target_diameter_min_m"]
    if "target_diameter_max_m" in t2:
        metric["target_diameter_max_m"] = t2["target_diameter_max_m"]

    return cfg


def max_targets_for_window(cfg: dict) -> int | None:
    value = task2_settings(cfg).get("max_targets_per_window")
    if value is None:
        return None
    return int(value)


def require_shot_confirmation(cfg: dict) -> bool:
    return bool(task2_settings(cfg).get("require_shot_confirmation", True))


def shot_confirm_timeout_s(cfg: dict) -> float:
    return float(task2_settings(cfg).get("shot_confirm_timeout_s", 8.0))


def post_spray_settle_s(cfg: dict) -> float:
    return float(task2_settings(cfg).get("post_spray_settle_s", 1.5))


def task1_allowed_colours(cfg: dict) -> set[str]:
    colours = cfg.get("conops", {}).get("task1", {}).get("allowed_colours")
    if colours:
        return {str(c).strip().lower() for c in colours}
    task1_cfg = cfg.get("task1", {}).get("allowed_colours")
    if task1_cfg:
        return {str(c).strip().lower() for c in task1_cfg}
    return {"black", "white", "red", "yellow", "blue", "green"}


def has_shot_confirmation(cv_packet: CVPacket | None) -> bool:
    return cv_packet is not None and len(cv_packet.shot) > 0


def validate_conops_config(cfg: dict) -> list[str]:
    """Return warnings when runtime config diverges from CONOPS."""
    warnings: list[str] = []
    t2 = task2_settings(cfg)
    if not t2:
        return warnings

    metric = cfg.get("metric_recon", {})
    conops_min = t2.get("min_approach_distance_m")
    runtime_min = metric.get("min_approach_distance_m")
    if conops_min is not None and runtime_min is not None and conops_min != runtime_min:
        warnings.append(
            f"metric_recon.min_approach_distance_m ({runtime_min}) "
            f"differs from conops.task2 ({conops_min})"
        )

    conops_max_d = t2.get("target_diameter_max_m")
    runtime_d = metric.get("target_diameter_m")
    if conops_max_d is not None and runtime_d is not None and conops_max_d != runtime_d:
        warnings.append(
            f"metric_recon.target_diameter_m ({runtime_d}) "
            f"differs from conops.task2.target_diameter_max_m ({conops_max_d})"
        )

    return warnings
