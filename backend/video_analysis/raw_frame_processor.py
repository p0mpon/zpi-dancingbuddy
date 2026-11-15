from typing import Any

import numpy as np

from video_analysis.initial_analysis import (
    JOINT_CONFIG,
    LANDMARK_COUNT,
    LANDMARK_VALUES,
    calculate_kinematics_and_height,
    extract_pose_features,
    smooth_coordinates,
)
from video_analysis.video_frame_model import Frame, RawFrame


DEFAULT_FPS = 30.0


def _validate_landmarks(landmarks: list[list[float]], field_name: str) -> None:
    if len(landmarks) != LANDMARK_COUNT:
        raise ValueError(
            f"{field_name} must contain {LANDMARK_COUNT} landmarks; "
            f"received {len(landmarks)}."
        )

    if any(len(landmark) < LANDMARK_VALUES for landmark in landmarks):
        raise ValueError(
            f"Every {field_name} landmark must contain at least "
            f"{LANDMARK_VALUES} values."
        )


def _parse_raw_frames(raw_frames: list[RawFrame | dict[str, Any]]) -> list[RawFrame]:
    parsed_frames = [
        frame if isinstance(frame, RawFrame) else RawFrame.model_validate(frame)
        for frame in raw_frames
    ]

    for frame in parsed_frames:
        _validate_landmarks(frame.world_landmarks, "world_landmarks")
        _validate_landmarks(frame.vis_landmarks, "vis_landmarks")

    return parsed_frames


def _calculate_frame_dt(frames: list[RawFrame]) -> float:
    timestamps = np.asarray([frame.timestamp for frame in frames], dtype=float)
    if len(timestamps) < 2:
        return 1.0 / DEFAULT_FPS

    intervals = np.diff(timestamps)
    positive_intervals = intervals[intervals > 0.0]
    if len(positive_intervals) == 0:
        return 1.0 / DEFAULT_FPS

    return float(np.median(positive_intervals))


def process_raw_frames(
    raw_frames: list[RawFrame | dict[str, Any]],
    *,
    playback_speed: float = 1.0,
    joints_config: dict[str, tuple[int, int, int]] | None = None,
) -> list[Frame]:
    """
    Convert MediaPipe landmark frames into smoothed, analysed frames.
    """
    if playback_speed <= 0.0:
        raise ValueError("playback_speed must be greater than zero.")

    parsed_frames = _parse_raw_frames(raw_frames)
    if not parsed_frames:
        raise ValueError("raw_frames must contain at least one frame.")

    if joints_config is None:
        joints_config = JOINT_CONFIG

    world_coords = np.asarray(
        [frame.world_landmarks for frame in parsed_frames], dtype=float
    )
    vis_coords = np.asarray(
        [frame.vis_landmarks for frame in parsed_frames], dtype=float
    )

    smoothed_world_coords = smooth_coordinates(world_coords)
    smoothed_vis_coords = smooth_coordinates(vis_coords)

    frames: list[Frame] = []
    smoothed_hip_y: list[float] = []

    for frame_id, raw_frame in enumerate(parsed_frames):
        joints, hip_y_norm, hip_rotation = extract_pose_features(
            smoothed_world_coords[frame_id],
            smoothed_vis_coords[frame_id],
            joints_config,
        )
        smoothed_hip_y.append(hip_y_norm)
        frames.append(
            Frame(
                frame_id=frame_id,
                timestamp=raw_frame.timestamp,
                hip_height=0.0,
                hip_rotation=round(hip_rotation, 2),
                joints=joints,
            )
        )

    calculate_kinematics_and_height(
        frames,
        smoothed_hip_y,
        _calculate_frame_dt(parsed_frames),
        playback_speed,
    )
    return frames