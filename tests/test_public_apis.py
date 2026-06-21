"""Public API import smoke tests (orchestrator-facing facades)."""

from __future__ import annotations


def test_cv_public_api():
    from valiant.autonomy.cv import (
        create_target_detector,
        draw_mission_overlay,
        hits_to_bench_dict,
        render_sitl_dashboard,
        resolve_dry_model_path,
    )

    assert callable(create_target_detector)
    assert callable(draw_mission_overlay)
    assert callable(render_sitl_dashboard)
    assert callable(hits_to_bench_dict)
    assert callable(resolve_dry_model_path)


def test_metric_recon_public_api():
    from valiant.autonomy.metric_recon import (
        InlineDepthSource,
        create_metric_reconstructor,
    )

    assert callable(create_metric_reconstructor)
    assert InlineDepthSource is not None


def test_auto_nav_public_api():
    from valiant.autonomy.auto_nav import (
        MotionIntent,
        create_mavlink_driver,
        create_motion_planner,
    )

    assert MotionIntent.APPROACH.value == "approach"
    assert callable(create_motion_planner)
    assert callable(create_mavlink_driver)


def test_spray_public_api():
    from valiant.autonomy.spray import (
        create_water_trigger,
        is_aimed,
        is_body_aligned,
        is_target_aligned,
    )

    assert callable(is_aimed)
    assert callable(is_body_aligned)
    assert callable(is_target_aligned)
    assert callable(create_water_trigger)


def test_metric_packet_servo_px():
    from valiant.autonomy.packets import MetricPacket

    centered = MetricPacket(target_px=(640, 360), pixel_offset=(0.0, 0.0))
    assert centered.servo_px == (640, 360)

    corner = MetricPacket(
        target_px=(200, 360),
        pixel_offset=(0.0, 0.0),
        aim_px=(550, 360),
    )
    assert corner.servo_px == (550, 360)
