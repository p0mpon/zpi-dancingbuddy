from typing import List

import numpy as np
from pydantic import BaseModel

from zpi_app.zpi_app.video_frame_model import Frame, Joint


AudioData = tuple[np.ndarray, tuple[float, np.ndarray]]


class ChoreoMetadata(BaseModel):
    """
    Metadata for the choreo data, including the song id, fps and duration in seconds.
    """
    song_id: int
    fps: int
    duration_sec: float


class DynamicWeights(BaseModel):
    """
    Weights representing the importance of angle or velocity + acceleration of a joint.
    Angle weight is higher for poses that are held for some time,
    while kinematic weight is higher for fast movements.
    """
    angle_weight: float
    kinematic_weight: float


class AudioContext(BaseModel):
    """
    Data about the audio context of a frame, including whether the frame is on a beat or an onset.
    """
    is_beat: bool
    is_onset: bool


class GlobalPosition(BaseModel):
    """
    Represents the global position of the dancer, including:
    - hip_y: the height of the hip in the global coordinate system
    - body_rotation_deg: the rotation of the body in degrees
    """
    hip_y: float
    body_rotation_deg: float


class JointData(BaseModel):
    """
    Represents the data for a single joint, including:
    - angle: the angle of the joint in degrees
    - velocity_deg_per_sec: the velocity of the joint in degrees per second
    - acceleration_deg_per_sec2: the acceleration of the joint in degrees per second squared
    - visibility: the visibility of the joint
    - dynamic_weights: the dynamic weights for the joint
    """
    angle: float
    velocity_deg_per_sec: float
    acceleration_deg_per_sec2: float
    visibility: float
    dynamic_weights: DynamicWeights


class ChoreoFrame(BaseModel):
    """
    Represents a single frame of the choreo, incuding:
    - frame_id: the index of the frame in the original video
    - timestamp_sec: the timestamp of the frame in seconds
    - frame_weight: the weight of the frame based on audio and hold detection
    - audio_context: the audio context of the frame (beat and onset)
    - global_position: the global position of the dancer (hip height and body rotation)
    - joints: the data for each joint
    """
    frame_id: int
    timestamp_sec: float
    frame_weight: float
    audio_context: AudioContext
    global_position: GlobalPosition
    joints: dict[str, JointData]


class ChoreoData(BaseModel):
    """
    Full choreo data object. Includes metadata and a list of frames with all the weights.
    """
    metadata: ChoreoMetadata
    frames: list[ChoreoFrame]


class ChoreoEncoder:
    """
    Encodes video and audio data into a proper choreo format.
    """
    # --- CONSTANTS ---
    # threshold for joint visibility, below which the joint is considered not visible
    VISIBILITY_THRESHOLD = 0.5
    # alpha value for EMA
    EMA_ALPHA = 0.3
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
    # default fps
    DEFAULT_FPS = 30

    @staticmethod
    def _is_visible(joint: Joint) -> bool:
        """
        Check if a joint is visible vased on a threshold.
        If the joint is None, the visibility is set to 0.
        """
        visibility = joint.visibility if joint is not None else None
        return (
            visibility is not None
            and visibility >= ChoreoEncoder.VISIBILITY_THRESHOLD
        )

    @staticmethod
    def _number(value: object, default: float = 0.0) -> float:
        """
        Makes a float out of a value, or returns a default if the value is None or not finite.
        """
        return float(value) if value is not None and np.isfinite(value) else default

    def _preprocess_frames(
        self, video_data: List[Frame]
    ) -> tuple[list[dict[str, object]], float]:
        """
        Smoothes the angles of the joints from video data and calculates the velocity and acceleration of each joint.
        Returns a list of processed frames and the frame interval in seconds (median of all deltas).
        """
        if not video_data:
            return [], float(1 / self.DEFAULT_FPS)

        timestamps = np.asarray([self._number(frame.timestamp) for frame in video_data])
        # time differences between timestamps
        deltas = np.diff(timestamps)
        positive_deltas = deltas[deltas > 0]
        frame_interval = (
            float(np.median(positive_deltas))
            if positive_deltas.size
            else 1 / self.DEFAULT_FPS
        )

        # set up previous angles and velocities for EMA smoothing
        previous_angles: dict[str, float] = {}
        previous_velocities: dict[str, float] = {}
        processed: list[dict[str, object]] = []

        for index, frame in enumerate(video_data):
            dt = (
                float(timestamps[index] - timestamps[index - 1])
                if index > 0 and timestamps[index] > timestamps[index - 1]
                else frame_interval
            )

            joints: dict[str, dict[str, float]] = {}
            for name, joint in frame.joints.items():
                visibility = float(np.clip(self._number(getattr(joint, "visibility", 0.0)), 0.0, 1.0))
                # set default values if the joint is not visible or angle is None
                if not self._is_visible(joint) or getattr(joint, "angle", None) is None:
                    previous_angles.pop(name, None)
                    previous_velocities.pop(name, None)
                    joints[name] = {
                        "angle": 0.0,
                        "velocity": 0.0,
                        "acceleration": 0.0,
                        "visibility": visibility,
                    }
                    continue

                raw_angle = self._number(joint.angle)
                # apply EMA smoothing for angles
                smoothed_angle = (
                    raw_angle
                    if name not in previous_angles
                    else self.EMA_ALPHA * raw_angle
                    + (1 - self.EMA_ALPHA) * previous_angles[name]
                )

                # calculate velocity and acceleration
                velocity = (smoothed_angle - previous_angles.get(name, smoothed_angle)) / dt
                acceleration = (velocity - previous_velocities.get(name, velocity)) / dt

                previous_angles[name] = smoothed_angle
                previous_velocities[name] = velocity

                joints[name] = {
                    "angle": smoothed_angle,
                    "velocity": velocity,
                    "acceleration": acceleration,
                    "visibility": visibility,
                }

            processed.append({"frame": frame, "timestamp": timestamps[index], "joints": joints})

        return processed, frame_interval

    def _select_frames(
        self, processed: list[dict[str, object]]
    ) -> list[tuple[dict[str, object], bool]]:
        """
        Selects frames based on the processed data.
        Returns a list of tuples containing the selected frame and a boolean indicating that the frame is a held pose.
        """
        if not processed:
            return []

        # list of tuples with frames and whether they are held poses
        selected: list[tuple[dict[str, object], bool]] = [(processed[0], False)]
        baseline = processed[0]

        for current in processed[1:]:
            baseline_joints = baseline["joints"]
            current_joints = current["joints"]
            names = set(baseline_joints) | set(current_joints)

            max_delta = max(
                (
                    abs(
                        current_joints.get(name, {"angle": 0.0})["angle"]
                        - baseline_joints.get(name, {"angle": 0.0})["angle"]
                    )
                    for name in names
                ),
                default=0.0,
            )
            
            max_velocity = max(
                (abs(joint["velocity"]) for joint in current_joints.values()),
                default=0.0,
            )
            max_acceleration = max(
                (abs(joint["acceleration"]) for joint in current_joints.values()),
                default=0.0,
            )
            held_long_enough = (
                current["timestamp"] - baseline["timestamp"] > self.HOLD_DURATION_SEC
            )

            is_hold = held_long_enough and max_delta < self.STATIC_DELTA_THRESHOLD_DEG
            is_slow_move = (
                max_velocity < self.SLOW_VELOCITY_THRESHOLD_DEG_PER_SEC
                and max_delta >= self.SLOW_DELTA_THRESHOLD_DEG
            )
            is_fast_move = (
                max_velocity >= self.FAST_VELOCITY_THRESHOLD_DEG_PER_SEC
                and (
                    max_delta >= self.FAST_DELTA_THRESHOLD_DEG
                    or max_acceleration >= self.FAST_ACCELERATION_THRESHOLD_DEG_PER_SEC2
                )
            )

            if is_hold or is_slow_move or is_fast_move:
                selected.append((current, is_hold))
                baseline = current

        if selected[-1][0] is not processed[-1]:
            selected.append((processed[-1], False))

        return selected

    def _audio_context(
        self, timestamp: float, onset_times: np.ndarray, beat_times: np.ndarray
    ) -> AudioContext:
        """
        Checks if the given timestamp is close to any onset or beat times within a tolerance.
        """
        return AudioContext(
            is_onset=bool(
                np.any(np.abs(onset_times - timestamp) <= self.AUDIO_MATCH_TOLERANCE_SEC)
            ),
            is_beat=bool(
                np.any(np.abs(beat_times - timestamp) <= self.AUDIO_MATCH_TOLERANCE_SEC)
            ),
        )

    def encode_to_choreo(
        self,
        audio_data: AudioData,
        video_data: List[Frame],
    ) -> ChoreoData:
        """
        Encodes the given audio and video data into a ChoreoData object.
        The video data (angles) are smoothed using the EMA method.
        """
        onset_times, (_, beat_times) = audio_data

        processed, frame_interval = self._preprocess_frames(video_data)
        selected = self._select_frames(processed)

        fps = round(1 / frame_interval) if frame_interval > 0 else self.DEFAULT_FPS

        output_frames: list[ChoreoFrame] = []

        for data, is_hold in selected:
            frame = data["frame"]
            audio_context = self._audio_context(
                float(data["timestamp"]), np.asarray(onset_times), np.asarray(beat_times)
            )

            frame_weight = 1.0
            if audio_context.is_onset or audio_context.is_beat:
                frame_weight *= self.AUDIO_WEIGHT_MULTIPLIER
            if is_hold:
                frame_weight *= self.HOLD_WEIGHT_MULTIPLIER

            joints: dict[str, JointData] = {}
            for name, values in data["joints"].items():
                speed = abs(values["velocity"])
                if speed < self.SLOW_VELOCITY_THRESHOLD_DEG_PER_SEC:
                    angle_weight, kinematic_weight = 0.9, 0.1
                elif speed < self.FAST_VELOCITY_THRESHOLD_DEG_PER_SEC:
                    angle_weight, kinematic_weight = 0.5, 0.5
                else:
                    angle_weight, kinematic_weight = 0.2, 0.8

                visibility = values["visibility"]

                joints[name] = JointData(
                    angle=values["angle"],
                    velocity_deg_per_sec=values["velocity"],
                    acceleration_deg_per_sec2=values["acceleration"],
                    visibility=visibility,
                    dynamic_weights=DynamicWeights(
                        angle_weight=angle_weight,
                        kinematic_weight=kinematic_weight,
                    ),
                )

            output_frames.append(
                ChoreoFrame(
                    frame_id=frame.frame_id,
                    timestamp_sec=float(data["timestamp"]),
                    frame_weight=frame_weight,
                    audio_context=audio_context,
                    global_position=GlobalPosition(
                        hip_y=self._number(frame.hip_height),
                        body_rotation_deg=self._number(frame.hip_rotation),
                    ),
                    joints=joints,
                )
            )

        duration = (
            float(np.max(beat_times))
            if np.asarray(beat_times).size
            else (float(processed[-1]["timestamp"]) if processed else 0.0)
        )

        return ChoreoData(
            metadata=ChoreoMetadata(song_id=0, fps=fps, duration_sec=duration),
            frames=output_frames,
        )
