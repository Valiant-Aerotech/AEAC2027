"""ArduPilot GUIDED masks for VisualServo."""

from __future__ import annotations

from pymavlink import mavutil

from valiant.autonomy.auto_nav.visual_servo import (
    GUIDED_MASK_YAW,
    GUIDED_MASK_YAW_RATE,
    VisualServo,
)


def test_guided_yaw_mask_matches_ardupilot_doc():
    assert GUIDED_MASK_YAW == 2503


def test_guided_yaw_rate_mask_matches_ardupilot_doc():
    assert GUIDED_MASK_YAW_RATE == 1479


def test_send_guided_yaw_uses_local_ned_zero_vel():
    sent: list[tuple] = []

    class FakeMav:
        target_system = 1
        target_component = 1

        class mav:
            @staticmethod
            def set_position_target_local_ned_send(*args):
                sent.append(args)

    servo = VisualServo(FakeMav(), {})
    servo.send_guided_yaw(1.57)
    assert len(sent) == 1
    args = sent[0]
    assert args[3] == mavutil.mavlink.MAV_FRAME_LOCAL_NED
    assert args[4] == GUIDED_MASK_YAW
    assert args[8] == 0.0 and args[9] == 0.0 and args[10] == 0.0
    assert abs(args[14] - 1.57) < 1e-6
    assert args[15] == 0.0


def test_send_yaw_rate_includes_zero_velocity():
    sent: list[tuple] = []

    class FakeMav:
        target_system = 1
        target_component = 1

        class mav:
            @staticmethod
            def set_position_target_local_ned_send(*args):
                sent.append(args)

    servo = VisualServo(FakeMav(), {})
    servo.send_yaw_rate(0.35)
    assert len(sent) == 1
    args = sent[0]
    assert args[3] == mavutil.mavlink.MAV_FRAME_LOCAL_NED
    assert args[4] == GUIDED_MASK_YAW_RATE
    assert args[8] == 0.0 and args[9] == 0.0 and args[10] == 0.0
    assert abs(args[15] - 0.35) < 1e-6


def test_send_velocity_ned_uses_local_ned():
    from valiant.autonomy.auto_nav.visual_servo import GUIDED_MASK_VELOCITY

    sent: list[tuple] = []

    class FakeMav:
        target_system = 1
        target_component = 1

        class mav:
            @staticmethod
            def set_position_target_local_ned_send(*args):
                sent.append(args)

    servo = VisualServo(FakeMav(), {})
    servo.send_velocity_ned(0.2, -0.1, 0.05)
    assert len(sent) == 1
    args = sent[0]
    assert args[3] == mavutil.mavlink.MAV_FRAME_LOCAL_NED
    assert args[4] == GUIDED_MASK_VELOCITY
    assert args[8] == 0.2 and args[9] == -0.1 and args[10] == 0.05


def test_resend_last_guided_repeats_ned_velocity():
    from valiant.autonomy.auto_nav.visual_servo import GUIDED_MASK_VELOCITY

    sent: list[tuple] = []

    class FakeMav:
        target_system = 1
        target_component = 1

        class mav:
            @staticmethod
            def set_position_target_local_ned_send(*args):
                sent.append(args)

    servo = VisualServo(FakeMav(), {})
    servo.send_velocity_ned(0.3, 0.0, 0.0)
    servo.resend_last_guided()
    assert len(sent) == 2
    assert sent[0][4] == GUIDED_MASK_VELOCITY
    assert sent[1][4] == GUIDED_MASK_VELOCITY


def test_resend_last_guided_repeats_yaw_hold():
    sent: list[tuple] = []

    class FakeMav:
        target_system = 1
        target_component = 1

        class mav:
            @staticmethod
            def set_position_target_local_ned_send(*args):
                sent.append(args)

    servo = VisualServo(FakeMav(), {})
    servo.send_guided_yaw(0.5)
    servo.resend_last_guided()
    assert len(sent) == 2
    assert sent[0][4] == GUIDED_MASK_YAW
    assert sent[1][4] == GUIDED_MASK_YAW
