"""SITL Phase 3 software acceptance - mirrors field-test-plan Phase 3 pass criteria."""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path

import pytest

from valiant.autonomy.conops import task2_photo_filename
from valiant.autonomy.flight.profile import apply_flight_profile
from valiant.autonomy.orchestrator import AutoExtinguisher, STATE_COMPLETE
from valiant.common.config import load_config

pytestmark = pytest.mark.sitl


def test_sitl_phase3_single_target_cycle(sitl_master):
    """SEARCHING -> COMPLETE with CONOPS photo name + local upload copy."""
    cfg = apply_flight_profile(load_config("vion"), "sitl")

    with tempfile.TemporaryDirectory() as tmp:
        photo_dir = Path(tmp) / "task2_photos"
        cfg = dict(cfg)
        cfg.setdefault("team", {})["photo_save_dir"] = str(photo_dir)
        cfg.setdefault("upload", {})["method"] = "local_copy"

        ext = AutoExtinguisher(
            cfg,
            master=sitl_master,
            connection_string="tcp:127.0.0.1:5760",
            baudrate=57600,
            sitl_mode=True,
            headless=True,
            max_targets=1,
            gcs_ip="127.0.0.1",
            skip_sitl_preflight=True,
            assume_sitl_airborne=True,
        )

        reached = threading.Event()
        expected_name = task2_photo_filename(cfg, 1)

        def watch():
            deadline = time.time() + 150
            while time.time() < deadline:
                if ext.state == STATE_COMPLETE:
                    reached.set()
                    break
                time.sleep(0.1)

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()

        loop_thread = threading.Thread(target=ext.loop, daemon=True)
        loop_thread.start()

        assert reached.wait(timeout=140), f"state stuck at {ext.state}"
        assert ext.targets_completed >= 1

        photo_path = photo_dir / expected_name
        assert photo_path.is_file(), f"missing photo {expected_name}"
        uploaded = photo_dir / "uploaded" / expected_name
        assert uploaded.is_file(), "missing local upload copy"

        ext.request_stop()
        loop_thread.join(timeout=5)
        ext.metric_recon.stop()
        ext.trigger.cleanup()
        ext.gimbal.cleanup()
        ext.camera.cleanup()
