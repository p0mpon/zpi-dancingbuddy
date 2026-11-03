import numpy as np

from full_analysis.choreo_data_model import AudioContext, ChoreoFrame, DynamicWeights, GlobalPosition, JointData
from video_analysis.video_frame_model import Frame

# type alias for audio data
AudioData = tuple[np.ndarray, tuple[float, np.ndarray]]

# threshold for joint visibility
JOINT_VISIBILITY_THRESHOLD = 0.5
# thresholds for detecting holds, slow and fast movements
STATIC_DELTA_THRESHOLD_DEG = 5.0
SLOW_DELTA_THRESHOLD_DEG = 15.0
FAST_DELTA_THRESHOLD_DEG = 30.0
HOLD_DURATION_SEC = 0.5
SLOW_VELOCITY_THRESHOLD_DEG_PER_SEC = 30.0
FAST_VELOCITY_THRESHOLD_DEG_PER_SEC = 120.0
FAST_ACCELERATION_THRESHOLD_DEG_PER_SEC2 = 300.0
# tolerance for matching beat and onset times to frame timestamps
AUDIO_MATCH_TOLERANCE_SEC = 0.1
# multipliers for frame weights based on audio and hold detection
AUDIO_WEIGHT_MULTIPLIER = 1.5
HOLD_WEIGHT_MULTIPLIER = 1.2
# multipiers for dynamic weights based on speed of movement
STATIC_ANGLE_WEIGHT_MULTIPLIER = 0.9
STATIC_KINEMATIC_WEIGHT_MULTIPLIER = 0.1
SLOW_ANGLE_WEIGHT_MULTIPLIER = 0.5
SLOW_KINEMATIC_WEIGHT_MULTIPLIER = 0.5
FAST_ANGLE_WEIGHT_MULTIPLIER = 0.2
FAST_KINEMATIC_WEIGHT_MULTIPLIER = 0.8


def _select_frames(video_frames: list[Frame]) -> list[tuple[Frame, bool]]:
    """
    Selects frames based on the processed video data.
    Returns a list of tuples containing the selected frame and a boolean indicating that the frame is a held pose.
    Args:
        video_frames (list[Frame]): List of processed video frames.
    Returns:
        list[tuple[Frame, bool]]: List of tuples containing the selected frame and a boolean indicating that the frame is a held pose.
    """
    if not video_frames:
        return []

    # list of tuples with frames and whether they are held poses
    selected: list[tuple[Frame, bool]] = [(video_frames[0], False)]
    previous_selected_frame = video_frames[0]

    for frame in video_frames[1:]:
        previous_joints = previous_selected_frame.joints
        current_joints = frame.joints
        names = set(previous_joints) | set(current_joints)

        max_delta = max(
            (
                abs(
                    (current_joints[name].angle or 0.0)
                    - (previous_joints[name].angle or 0.0)
                )
                for name in names
            ),
            default=0.0,
        )
        
        max_velocity = max(
            (abs(joint.angular_velocity or 0.0) for joint in current_joints.values()),
            default=0.0,
        )
        max_acceleration = max(
            (abs(joint.angular_acceleration or 0.0) for joint in current_joints.values()),
            default=0.0,
        )
        held_long_enough = (
            frame.timestamp - previous_selected_frame.timestamp > HOLD_DURATION_SEC
        )

        is_hold = held_long_enough and max_delta < STATIC_DELTA_THRESHOLD_DEG
        is_slow_move = (
            max_velocity < SLOW_VELOCITY_THRESHOLD_DEG_PER_SEC
            and max_delta >= SLOW_DELTA_THRESHOLD_DEG
        )
        is_fast_move = (
            max_velocity >= FAST_VELOCITY_THRESHOLD_DEG_PER_SEC
            and (
                max_delta >= FAST_DELTA_THRESHOLD_DEG
                or max_acceleration >= FAST_ACCELERATION_THRESHOLD_DEG_PER_SEC2
            )
        )

        if is_hold or is_slow_move or is_fast_move:
            selected.append((frame, is_hold))
            previous_selected_frame = frame

    if selected[-1][0] is not video_frames[-1]:
        selected.append((video_frames[-1], False))

    return selected

def _audio_context(timestamp: float, 
                   onset_times: np.ndarray, 
                   beat_times: np.ndarray) -> AudioContext:
    """
    Checks if the given timestamp is close to any onset or beat times within a tolerance.
    Args:
        timestamp (float): The timestamp to check.
        onset_times (np.ndarray): Array of onset times.
        beat_times (np.ndarray): Array of beat times.
    Returns:
        AudioContext: An object containing boolean flags for is_onset and is_beat.
    """
    return AudioContext(
        is_onset=bool(
            np.any(np.abs(onset_times - timestamp) <= AUDIO_MATCH_TOLERANCE_SEC)
        ),
        is_beat=bool(
            np.any(np.abs(beat_times - timestamp) <= AUDIO_MATCH_TOLERANCE_SEC)
        ),
    )

def encode_to_choreo(audio_data: AudioData,
                     video_frames: list[Frame]) -> list[ChoreoFrame]:
    """
    Encodes the given audio and video data into a list of ChoreoFrame objects.
    Args:
        audio_data (AudioData): A tuple containing onset times and beat times.
        video_frames (list[Frame]): List of smoothed ad processed video frames.
    Returns:
        list[ChoreoFrame]: A list of encoded choreo frames with all the weights.
    """
    onset_times, (_, beat_times) = audio_data

    selected = _select_frames(video_frames)

    output_frames: list[ChoreoFrame] = []

    for frame, is_hold in selected:
        audio_context = _audio_context(
            float(frame.timestamp), np.asarray(onset_times), np.asarray(beat_times)
        )

        frame_weight = 1.0
        if audio_context.is_onset or audio_context.is_beat:
            frame_weight *= AUDIO_WEIGHT_MULTIPLIER
        if is_hold:
            frame_weight *= HOLD_WEIGHT_MULTIPLIER

        joints: dict[str, JointData] = {}
        for name, joint_data in frame.joints.items():
            visibility = joint_data.visibility
            if visibility < JOINT_VISIBILITY_THRESHOLD:
                continue
            
            speed = abs(joint_data.angular_velocity or 0.0)
            if speed < SLOW_VELOCITY_THRESHOLD_DEG_PER_SEC:
                angle_weight, kinematic_weight = STATIC_ANGLE_WEIGHT_MULTIPLIER, STATIC_KINEMATIC_WEIGHT_MULTIPLIER
            elif speed < FAST_VELOCITY_THRESHOLD_DEG_PER_SEC:
                angle_weight, kinematic_weight = SLOW_ANGLE_WEIGHT_MULTIPLIER, SLOW_KINEMATIC_WEIGHT_MULTIPLIER
            else:
                angle_weight, kinematic_weight = FAST_ANGLE_WEIGHT_MULTIPLIER, FAST_KINEMATIC_WEIGHT_MULTIPLIER

            joints[name] = JointData(
                angle=joint_data.angle or 0.0,
                velocity_deg_per_sec=joint_data.angular_velocity or 0.0,
                acceleration_deg_per_sec2=joint_data.angular_acceleration or 0.0,
                visibility=visibility,
                dynamic_weights=DynamicWeights(
                    angle_weight=angle_weight,
                    kinematic_weight=kinematic_weight,
                ),
            )

        output_frames.append(
            ChoreoFrame(
                frame_id=frame.frame_id,
                timestamp_sec=float(frame.timestamp),
                frame_weight=frame_weight,
                audio_context=audio_context,
                global_position=GlobalPosition(
                    hip_y=frame.hip_height or 0.0,
                    body_rotation_deg=frame.hip_rotation or 0.0,
                ),
                joints=joints,
            )
        )

    return output_frames
