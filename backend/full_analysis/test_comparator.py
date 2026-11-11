from unittest.mock import patch

import pytest

from full_analysis.choreo_comparator import (
    ANGLE_GRACE_THRESHOLD,
    ANGLE_TOLERANCE_THRESHOLD,
    _compare_frames,
    _get_best_frame_in_window,
    _get_fixed_similarity,
    _get_relative_similarity,
    _get_timestamp_weight,
)
from full_analysis.choreo_data_model import (
    AudioContext,
    ChoreoFrame,
    DynamicWeights,
    GlobalPosition,
    JointData,
)
from video_analysis.video_frame_model import Frame, Joint


def _make_base_frame(
    *,
    timestamp: float = 1.0,
    global_position: GlobalPosition | None = None,
    joints: dict[str, JointData] | None = None,
) -> ChoreoFrame:
    return ChoreoFrame(
        frame_id=1,
        timestamp_sec=timestamp,
        frame_weight=1.0,
        audio_context=AudioContext(is_beat=False, is_onset=False),
        global_position=global_position
        or GlobalPosition(hip_y=1.0, body_rotation_deg=0.0),
        joints=joints
        or {
            "l_knee": JointData(
                angle=90.0,
                velocity_deg_per_sec=100.0,
                acceleration_deg_per_sec2=50.0,
                visibility=1.0,
                dynamic_weights=DynamicWeights(
                    angle_weight=1.0, kinematic_weight=0.0
                ),
            )
        },
    )


def _make_compare_frame(
    *,
    timestamp: float = 1.0,
    hip_height: float | None = 1.0,
    hip_rotation: float | None = 0.0,
    joints: dict[str, Joint] | None = None,
) -> Frame:
    return Frame(
        frame_id=2,
        timestamp=timestamp,
        hip_height=hip_height,
        hip_rotation=hip_rotation,
        joints=joints or {"l_knee": Joint(angle=90.0, visibility=1.0)},
    )


@pytest.mark.parametrize(
    ("diff", "expected"),
    [
        (0.0, 1.0),
        (0.05, 1.0),
        (0.15, 0.0),
        (0.10, 0.5),
        (-0.10, 0.5),
        (0.20, 0.0),
    ],
)
def test_get_fixed_similarity(diff: float, expected: float) -> None:
    assert _get_fixed_similarity(diff, grace=0.05, tolerance=0.15) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("diff", "base_value", "expected"),
    [
        (0.0, 100.0, 1.0),
        (5.0, 100.0, 1.0),
        (12.5, 100.0, 0.5),
        (20.0, 100.0, 0.0),
        (-12.5, 100.0, 0.5),
        (12.5, -100.0, 0.5),
    ],
)
def test_get_relative_similarity(
    diff: float, base_value: float, expected: float
) -> None:
    assert _get_relative_similarity(
        diff,
        base_value=base_value,
        grace_percent=5.0,
        tolerance_percent=20.0,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("timestamp_difference", "expected"),
    [
        (0.0, 1.0),
        (0.07, 1.0),
        (0.2, 0.0),
        (0.135, 0.5),
        (-0.135, 0.5),
        (-0.3, 0.0),
    ],
)
def test_get_timestamp_weight(
    timestamp_difference: float, expected: float
) -> None:
    assert _get_timestamp_weight(timestamp_difference) == pytest.approx(expected)


def test_compare_frames_with_same_data() -> None:
    delay, score, joint_scores = _compare_frames(
        _make_base_frame(), _make_compare_frame()
    )

    assert delay == pytest.approx(0.0)
    assert score == pytest.approx(1.0)
    assert joint_scores["l_knee"] == pytest.approx(1.0)


def test_compare_frames_returns_timestamp_delay_without_changing_score() -> None:
    delay, score, _ = _compare_frames(
        _make_base_frame(timestamp=1.0),
        _make_compare_frame(timestamp=1.25),
    )

    assert delay == pytest.approx(0.25)
    assert score == pytest.approx(1.0)


def test_compare_frames_with_different_joint_data() -> None:
    delay, score, joint_scores = _compare_frames(
        _make_base_frame(),
        _make_compare_frame(
            joints={"l_knee": Joint(angle=120.0, visibility=1.0)}
        ),
    )

    expected_joint_score = (
        (ANGLE_TOLERANCE_THRESHOLD - 30.0)
        / (ANGLE_TOLERANCE_THRESHOLD - ANGLE_GRACE_THRESHOLD)
    )
    assert delay == pytest.approx(0.0)
    assert score == pytest.approx(0.85 * expected_joint_score + 0.15)
    assert joint_scores["l_knee"] == pytest.approx(expected_joint_score)


def test_compare_frames_uses_only_joints_when_base_global_position_is_missing() -> None:
    missing_global_position = GlobalPosition.model_construct(
        hip_y=None, body_rotation_deg=None
    )

    _, score, _ = _compare_frames(
        _make_base_frame(global_position=missing_global_position),
        _make_compare_frame(),
    )

    assert score == pytest.approx(1.0)


def test_compare_frames_uses_only_joints_when_compare_global_position_is_missing() -> None:
    _, score, _ = _compare_frames(
        _make_base_frame(),
        _make_compare_frame(hip_height=None, hip_rotation=None),
    )

    assert score == pytest.approx(0.85)


def test_compare_frames_weights_joint_scores_by_base_visibility() -> None:
    joints = {
        "visible_match": JointData(
            angle=90.0,
            velocity_deg_per_sec=100.0,
            acceleration_deg_per_sec2=50.0,
            visibility=0.25,
            dynamic_weights=DynamicWeights(angle_weight=1.0, kinematic_weight=0.0),
        ),
        "visible_mismatch": JointData(
            angle=90.0,
            velocity_deg_per_sec=100.0,
            acceleration_deg_per_sec2=50.0,
            visibility=0.75,
            dynamic_weights=DynamicWeights(angle_weight=1.0, kinematic_weight=0.0),
        ),
    }

    _, score, joint_scores = _compare_frames(
        _make_base_frame(global_position=GlobalPosition.model_construct(
            hip_y=None, body_rotation_deg=None
        ), joints=joints),
        _make_compare_frame(
            hip_height=None,
            hip_rotation=None,
            joints={
                "visible_match": Joint(angle=90.0, visibility=1.0),
                "visible_mismatch": Joint(angle=135.0, visibility=1.0),
            },
        ),
    )

    assert joint_scores["visible_match"] == pytest.approx(1.0)
    assert joint_scores["visible_mismatch"] == pytest.approx(0.0)
    assert score == pytest.approx(0.25 * 1.0 + 0.75 * 0.0)


def test_get_best_frame_with_matching_timestamp_and_data() -> None:
    base_frame = _make_base_frame()
    other_frame = _make_compare_frame(timestamp=1.1)
    compare_frame = _make_compare_frame(timestamp=base_frame.timestamp_sec)
    compare_frame.frame_id = 3

    with patch(
        "full_analysis.choreo_comparator._compare_frames",
        side_effect=[
            (0.1, 0.8, {"l_knee": 0.8}),
            (0.0, 1.0, {"l_knee": 1.0}),
        ],
    ) as compare_mock:
        result = _get_best_frame_in_window(base_frame, [other_frame, compare_frame])

    assert result.compare_frame_id == compare_frame.frame_id
    assert result.score == pytest.approx(1.0)
    assert result.delay_sec == pytest.approx(0.0)
    assert compare_mock.call_count == 2


def test_get_best_frame_selects_matching_data_with_timestamp_delay() -> None:
    base_frame = _make_base_frame()
    other_frame = _make_compare_frame(timestamp=1.2)
    compare_frame = _make_compare_frame(timestamp=1.5)
    compare_frame.frame_id = 3

    with patch(
        "full_analysis.choreo_comparator._compare_frames",
        side_effect=[
            (0.2, 0.7, {"l_knee": 0.7}),
            (0.5, 1.0, {"l_knee": 1.0}),
        ],
    ) as compare_mock:
        result = _get_best_frame_in_window(base_frame, [other_frame, compare_frame])

    assert result.compare_frame_id == compare_frame.frame_id
    assert result.score == pytest.approx(1.0)
    assert result.delay_sec == pytest.approx(0.5)
    assert compare_mock.call_count == 2


def test_get_best_frame_selects_highest_nonideal_score_without_delay() -> None:
    base_frame = _make_base_frame()
    lower_score_frame = _make_compare_frame(timestamp=1.2)
    best_frame = _make_compare_frame(timestamp=1.0)
    best_frame.frame_id = 3

    with patch(
        "full_analysis.choreo_comparator._compare_frames",
        side_effect=[
            (0.2, 0.6, {"l_knee": 0.6}),
            (0.0, 0.8, {"l_knee": 0.8}),
        ],
    ) as compare_mock:
        result = _get_best_frame_in_window(
            base_frame, [lower_score_frame, best_frame]
        )

    assert result.compare_frame_id == best_frame.frame_id
    assert result.score == pytest.approx(0.8)
    assert result.delay_sec == pytest.approx(0.0)
    assert compare_mock.call_count == 2


def test_get_best_frame_returns_default_for_no_compare_frames() -> None:
    base_frame = _make_base_frame()

    with patch("full_analysis.choreo_comparator._compare_frames") as compare_mock:
        result = _get_best_frame_in_window(base_frame, [])

    assert result.base_frame_id == base_frame.frame_id
    assert result.compare_frame_id == -1
    assert result.timestamp_sec == pytest.approx(base_frame.timestamp_sec)
    assert result.score == pytest.approx(0.0)
    assert result.delay_sec == pytest.approx(0.0)
    assert result.joint_scores == {}
    compare_mock.assert_not_called()
