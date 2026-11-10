from full_analysis.choreo_data_model import ChoreoFrame, ScoredFrame
from video_analysis.video_frame_model import Frame

# adjust these after tests

# fixed thresholds - things that are not relative to the base frame value
TIMESTAMP_WINDOW_THRESHOLD = 0.2  # seconds
TIMESTAMP_TOLERANCE_THRESHOLD = 0.07  # seconds

HIP_HEIGHT_TOLERANCE_THRESHOLD = 0.15  # meters
HIP_HEIGHT_GRACE_THRESHOLD = 0.05  # meters

ANGLE_GRACE_THRESHOLD = 15.0  # degrees
ANGLE_TOLERANCE_THRESHOLD = 45.0  # degrees

# relative thresholds - things that are relative to the base frame value
VELOCITY_GRACE_THRESHOLD_PERCENT = 5.0  # percent (degrees per second)
VELOCITY_TOLERANCE_THRESHOLD_PERCENT = 20.0  # percent (degrees per second)

ACCELERATION_GRACE_THRESHOLD_PERCENT = 10.0  # percent (degrees per second squared)
ACCELERATION_TOLERANCE_THRESHOLD_PERCENT = 30.0  # percent (degrees per second squared)

# weights for the final score calculation
JOINTS_SCORE_WEIGHT = 0.85
GLOBAL_POSITION_SCORE_WEIGHT = 0.15



def _get_fixed_similarity(diff: float, grace: float, tolerance: float) -> float:
    """
    Converts a value difference into a normalized similarity score for fixed thresholds.

    Differences within the grace threshold score 1.0. Differences at or
    above the tolerance score 0.0, with a linear score between those bounds.
    Args:
        diff (float): The difference between two values.
        grace (float): The fixed grace threshold for the difference.
        tolerance (float): The fixed tolerance threshold for the difference.
    Returns:
        float: The normalized similarity score.
    """
    difference = abs(diff)
    if difference <= grace:
        return 1.0
    if difference >= tolerance:
        return 0.0

    return (tolerance - difference) / (tolerance - grace)

def _get_relative_similarity(diff: float, base_value: float, grace_percent: float, tolerance_percent: float) -> float:
    """
    Converts a value difference into a normalized similarity score for relative thresholds.

    Differences within the grace threshold score 1.0. Differences at or
    above the tolerance score 0.0, with a linear score between those bounds.
    Args:
        diff (float): The difference between two values.
        base_value (float): The base value to calculate relative thresholds.
        grace_percent (float): The grace threshold as a percentage of the base value.
        tolerance_percent (float): The tolerance threshold as a percentage of the base value.
    Returns:
        float: The normalized similarity score.
    """
    grace = abs(base_value) * (grace_percent / 100.0)
    tolerance = abs(base_value) * (tolerance_percent / 100.0)
    return _get_fixed_similarity(diff, grace, tolerance)

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
            _get_fixed_similarity(
                base_frame.global_position.hip_y - compare_frame.hip_height,
                HIP_HEIGHT_GRACE_THRESHOLD,
                HIP_HEIGHT_TOLERANCE_THRESHOLD,
            )
        )
    if compare_frame.hip_rotation is not None:
        global_position_scores.append(
            _get_fixed_similarity(
                abs(
                    base_frame.global_position.body_rotation_deg -
                    compare_frame.hip_rotation,
                ),
                ANGLE_GRACE_THRESHOLD,
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
                _get_fixed_similarity(
                    abs(base_joint.angle - compare_joint.angle),
                    ANGLE_GRACE_THRESHOLD,
                    ANGLE_TOLERANCE_THRESHOLD,
                )
                * base_joint.dynamic_weights.angle_weight
            )
        if compare_joint.angular_velocity is not None:
            score += (
                _get_relative_similarity(
                    base_joint.velocity_deg_per_sec
                    - compare_joint.angular_velocity,
                    base_joint.velocity_deg_per_sec,
                    VELOCITY_GRACE_THRESHOLD_PERCENT,
                    VELOCITY_TOLERANCE_THRESHOLD_PERCENT,
                )
                * base_joint.dynamic_weights.kinematic_weight
                * 0.5
            )
        if compare_joint.angular_acceleration is not None:
            score += (
                _get_relative_similarity(
                    base_joint.acceleration_deg_per_sec2
                    - compare_joint.angular_acceleration,
                    base_joint.acceleration_deg_per_sec2,
                    ACCELERATION_GRACE_THRESHOLD_PERCENT,
                    ACCELERATION_TOLERANCE_THRESHOLD_PERCENT,
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
