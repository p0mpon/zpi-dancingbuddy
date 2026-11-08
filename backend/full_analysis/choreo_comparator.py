from full_analysis.choreo_data_model import ChoreoFrame, ScoredFrame
from video_analysis.video_frame_model import Frame


TIMESTAMP_WINDOW_THRESHOLD = 0.2  # seconds
TIMESTAMP_TOLERANCE_THRESHOLD = 0.07  # seconds

HIP_HEIGHT_TOLERANCE_THRESHOLD = 0.1  # meters
ANGLE_TOLERANCE_THRESHOLD = 45.0  # degrees
# adjust these after tests
VELOCITY_TOLERANCE_THRESHOLD = 10.0  # degrees per second
ACCELERATION_TOLERANCE_THRESHOLD = 50.0  # degrees per second squared

JOINTS_SCORE_WEIGHT = 0.85
GLOBAL_POSITION_SCORE_WEIGHT = 0.15

def _get_angle_diff(a: float, b: float) -> float:
    """
    Returns the shortest circular distance between two angles in degrees.
    Args:
        a (float): The first angle in degrees.
        b (float): The second angle in degrees.
    Returns:
        float: The shortest circular distance between the two angles in degrees.
    """
    diff = abs(a - b) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff

def _get_similarity(diff: float, tolerance: float) -> float:
    """
    Converts a value difference into a normalized similarity score.

    A zero difference scores 1.0. Differences at or above the tolerance
    score 0.0, with a linear score between those bounds.
    Args:
        diff (float): The difference between two values.
        tolerance (float): The tolerance threshold for the difference.
    Returns:
        float: The normalized similarity score.
    """
    return max(0.0, 1.0 - abs(diff) / tolerance)

def _get_timestamp_weight(timestamp_difference: float) -> float:
    """
    Returns the weight for a frame based on its absolute timestamp difference.

    Differences within the tolerance threshold receive full weight.
    Differences between the tolerance and window thresholds are linearly reduced to zero.
    """
    difference = abs(timestamp_difference)
    if difference <= TIMESTAMP_TOLERANCE_THRESHOLD:
        return 1.0
    if difference >= TIMESTAMP_WINDOW_THRESHOLD:
        return 0.0

    remaining_range = TIMESTAMP_WINDOW_THRESHOLD - TIMESTAMP_TOLERANCE_THRESHOLD
    return (
        (TIMESTAMP_WINDOW_THRESHOLD - difference)
        / remaining_range
    )

def _compare_frames(base_frame: ChoreoFrame, compare_frame: Frame) -> tuple[float, float, dict[str, float]]:
    """
    Compares two frames by angle, velocity and acceleration. 
    The frame and joint scores are values between 0 and 1, where 1 is a perfect match.
    The delay is the difference in timestamps between the two frames.
    Args:
        base_frame (ChoreoFrame): The base frame to compare against.
        compare_frame (Frame): The frame to compare with the base frame.
    Returns:
        tuple[float, float, dict[str, float]]: A delay in seconds, a similarity score and a dictionary of individual joint scores.
    """
    timestamp_difference = compare_frame.timestamp - base_frame.timestamp_sec

    global_position_scores: list[float] = []
    if compare_frame.hip_height is not None:
        global_position_scores.append(
            _get_similarity(
                base_frame.global_position.hip_y - compare_frame.hip_height,
                HIP_HEIGHT_TOLERANCE_THRESHOLD,
            )
        )
    if compare_frame.hip_rotation is not None:
        global_position_scores.append(
            _get_similarity(
                _get_angle_diff(
                    base_frame.global_position.body_rotation_deg,
                    compare_frame.hip_rotation,
                ),
                ANGLE_TOLERANCE_THRESHOLD,
            )
        )
    global_position_score = (
        sum(global_position_scores) / len(global_position_scores)
        if global_position_scores
        else 0.0
    )

    joint_scores: dict[str, float] = {}
    joints_visibility_weight = 0.0
    weighted_joints_score = 0.0
    for name, base_joint in base_frame.joints.items():
        compare_joint = compare_frame.joints.get(name)
        if (
            compare_joint is None
            or base_joint.visibility == 0
            or compare_joint.visibility == 0
        ):
            continue

        score = 0.0
        if compare_joint.angle is not None:
            score += (
                _get_similarity(
                    _get_angle_diff(base_joint.angle, compare_joint.angle),
                    ANGLE_TOLERANCE_THRESHOLD,
                )
                * base_joint.dynamic_weights.angle_weight
            )
        if compare_joint.angular_velocity is not None:
            score += (
                _get_similarity(
                    base_joint.velocity_deg_per_sec
                    - compare_joint.angular_velocity,
                    VELOCITY_TOLERANCE_THRESHOLD,
                )
                * base_joint.dynamic_weights.kinematic_weight
                * 0.5
            )
        if compare_joint.angular_acceleration is not None:
            score += (
                _get_similarity(
                    base_joint.acceleration_deg_per_sec2
                    - compare_joint.angular_acceleration,
                    ACCELERATION_TOLERANCE_THRESHOLD,
                )
                * base_joint.dynamic_weights.kinematic_weight
                * 0.5
            )
        joint_scores[name] = score
        weighted_joints_score += score * base_joint.visibility
        joints_visibility_weight += base_joint.visibility

    joints_score = (
        weighted_joints_score / joints_visibility_weight
        if joints_visibility_weight > 0.0
        else 0.0
    )
    global_position_score *= GLOBAL_POSITION_SCORE_WEIGHT
    joints_score *= JOINTS_SCORE_WEIGHT
    
    return timestamp_difference, global_position_score + joints_score, joint_scores


def _get_best_frame_in_window(base_frame: ChoreoFrame, compare_frames: list[Frame]) -> ScoredFrame:
    """
    Analyzes a window of frames and returns the best match with the base frame.
    Args:
        base_frame (ChoreoFrame): The base frame to compare against.
        compare_frames (list[Frame]): A list of frames to compare with the base frame.
    Returns:
        ScoredFrame: The best matching frame with its score and joint scores.
    """
    best_frame_id = -1
    best_timestamp = -1.0
    best_timestamp_difference = 0.0
    best_score = float("-inf")
    best_joint_scores: dict[str, float] = {}

    for compare_frame in compare_frames:
        timestamp_difference, score, joint_scores = _compare_frames(
            base_frame, compare_frame
        )
        if score > best_score:
            best_frame_id = compare_frame.frame_id
            best_timestamp = compare_frame.timestamp
            best_timestamp_difference = timestamp_difference
            best_score = score
            best_joint_scores = joint_scores

    if best_score == float("-inf"):
        return ScoredFrame(
            base_frame_id=base_frame.frame_id,
            compare_frame_id=-1,
            timestamp_sec=base_frame.timestamp_sec,
            score=0.0,
            delay_sec=0.0,
            joint_scores={},
        )

    return ScoredFrame(
        base_frame_id=base_frame.frame_id,
        compare_frame_id=best_frame_id,
        timestamp_sec=best_timestamp,
        score=best_score,
        delay_sec=best_timestamp_difference,
        joint_scores=best_joint_scores,
    )

def compare_choreos(base_choreo: list[ChoreoFrame],
                    compare_choreo: list[Frame]) -> tuple[list[ScoredFrame], float]:
    """
    Compares two choreographies and returns a detailed analysis of each frame and a general score.
    Args:
        base_choreo (ChoreoData): The base choreography data to compare against.
        compare_choreo (list[dict[str, object]]): The preprocessed choreography frames to compare with (use frame processor).
    Returns:
        tuple[list[ScoredFrame], float]: A list of scored frames and a general similarity score (between 0 and 1).
    """
    if not base_choreo or not compare_choreo:
        return [], 0.0

    # NOTE FOR LATER: perhaps add bpm to metadata, to then adjust the acceptable delay window
    final_score_sum = 0.0
    scored_frames: list[ScoredFrame] = []
    next_compare_index = 0

    for base_frame in base_choreo:
        window_start = base_frame.timestamp_sec - TIMESTAMP_WINDOW_THRESHOLD
        window_end = base_frame.timestamp_sec + TIMESTAMP_WINDOW_THRESHOLD

        while (
            next_compare_index < len(compare_choreo)
            and compare_choreo[next_compare_index].timestamp < window_start
        ):
            next_compare_index += 1

        window_start_index = next_compare_index
        window_end_index = window_start_index
        while (
            window_end_index < len(compare_choreo)
            and compare_choreo[window_end_index].timestamp <= window_end
        ):
            window_end_index += 1

        compare_frames_in_window = compare_choreo[
            window_start_index:window_end_index
        ]
        scored_frame = _get_best_frame_in_window(
            base_frame, compare_frames_in_window
        )

        scored_frames.append(scored_frame)
        timestamp_weight = _get_timestamp_weight(scored_frame.delay_sec)
        final_score_sum += scored_frame.score * timestamp_weight

    final_score = (
        final_score_sum / len(scored_frames)
        if scored_frames
        else 0.0
    )

    return scored_frames, final_score
