"""RPAS default platform config."""

from valiant.common.config import DEFAULT_DRONE, load_config, load_default_config


def test_default_drone_id():
    cfg = load_default_config()
    assert cfg["drone"] == DEFAULT_DRONE == "rpas"


def test_rpas_inherits_vion_tuning():
    rpas = load_config("rpas")
    vion = load_config("vion")
    assert rpas["sitl"]["takeoff_alt_m"] == vion["sitl"]["takeoff_alt_m"]
    assert rpas["mavlink"]["connection"] == "COM5"
    assert rpas["mavlink"]["rpi_connection"] == vion["mavlink"]["rpi_connection"]


def test_rpas_merges_calibration_when_present():
    from valiant.common.config import config_dir, load_calibration

    cfg = load_config("rpas")
    cal_files = [p for p in (
        config_dir() / "vion_calibration.yaml",
        config_dir() / "rpas_calibration.yaml",
    ) if p.is_file()]
    if not cal_files:
        assert load_calibration("rpas") == {}
        return
    assert cfg.get("calibration")


def test_vion_still_loads():
    cfg = load_config("vion")
    assert cfg["drone"] == "vion"
