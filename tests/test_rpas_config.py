"""RPAS default platform config."""

from valiant.common.config import DEFAULT_DRONE, load_config, load_default_config


def test_default_drone_id():
    cfg = load_default_config()
    assert cfg["drone"] == DEFAULT_DRONE == "rpas"


def test_rpas_inherits_vion_tuning():
    rpas = load_config("rpas")
    vion = load_config("vion")
    assert rpas["sitl"]["takeoff_alt_m"] == vion["sitl"]["takeoff_alt_m"]
    assert rpas["mavlink"]["connection"] == vion["mavlink"]["connection"]


def test_vion_still_loads():
    cfg = load_config("vion")
    assert cfg["drone"] == "vion"
