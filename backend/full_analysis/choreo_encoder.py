import numpy as np
from typing import List

from full_analysis.choreo_data_model import AudioContext, ChoreoData, ChoreoFrame, ChoreoMetadata, DynamicWeights, GlobalPosition, JointData
from zpi_app.zpi_app.video_frame_model import Frame, Joint


AudioData = tuple[np.ndarray, tuple[float, np.ndarray]]

class ChoreoEncoder:
    """
    Encodes video and audio data into a proper choreo format.
    """
    def __init__(self,
                 static_delta_threshold_deg: float = 5.0,
                 slow_delta_threshold_deg: float = 15.0,
                 fast_delta_threshold_deg: float = 30.0,
                 hold_duration_sec: float = 0.5,
                 slow_velocity_threshold_deg_per_sec: float = 30.0,
                 fast_velocity_threshold_deg_per_sec: float = 120.0,
                 fast_acceleration_threshold_deg_per_sec2: float = 300.0,
                 audio_match_tolerance_sec: float = 0.1,
                 audio_weight_multiplier: float = 1.5,
                 hold_weight_multiplier: float = 1.2,
                 static_angle_weight_multiplier: float = 0.9,
                 static_kinematic_weight_multiplier: float = 0.1,
                 slow_angle_weight_multiplier: float = 0.5,
                 slow_kinematic_weight_multiplier: float = 0.5,
                 fast_angle_weight_multiplier: float = 0.2,
                 fast_kinematic_weight_multiplier: float = 0.8,
                 default_fps: int = 30):
        # thresholds for detecting holds, slow and fast movements
        self.STATIC_DELTA_THRESHOLD_DEG = static_delta_threshold_deg
        self.SLOW_DELTA_THRESHOLD_DEG = slow_delta_threshold_deg
        self.FAST_DELTA_THRESHOLD_DEG = fast_delta_threshold_deg
        self.HOLD_DURATION_SEC = hold_duration_sec
        self.SLOW_VELOCITY_THRESHOLD_DEG_PER_SEC = slow_velocity_threshold_deg_per_sec
        self.FAST_VELOCITY_THRESHOLD_DEG_PER_SEC = fast_velocity_threshold_deg_per_sec
        self.FAST_ACCELERATION_THRESHOLD_DEG_PER_SEC2 = fast_acceleration_threshold_deg_per_sec2
        # tolerance for matching beat and onset times to frame timestamps
        self.AUDIO_MATCH_TOLERANCE_SEC = audio_match_tolerance_sec
        # multipliers for frame weights based on audio and hold detection
        self.AUDIO_WEIGHT_MULTIPLIER = audio_weight_multiplier
        self.HOLD_WEIGHT_MULTIPLIER = hold_weight_multiplier
        # multipiers for dynamic weights based on speed of movement
        self.STATIC_ANGLE_WEIGHT_MULTIPLIER = static_angle_weight_multiplier
        self.STATIC_KINEMATIC_WEIGHT_MULTIPLIER = static_kinematic_weight_multiplier
        self.SLOW_ANGLE_WEIGHT_MULTIPLIER = slow_angle_weight_multiplier
        self.SLOW_KINEMATIC_WEIGHT_MULTIPLIER = slow_kinematic_weight_multiplier
        self.FAST_ANGLE_WEIGHT_MULTIPLIER = fast_angle_weight_multiplier
        self.FAST_KINEMATIC_WEIGHT_MULTIPLIER = fast_kinematic_weight_multiplier
        # default fps
        self.DEFAULT_FPS = default_fps

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
        processed_frames: list[dict[str, object]],
        frame_interval: float,
    ) -> ChoreoData:
        """
        Encodes the given audio and video data into a ChoreoData object.
        The video data (angles) are smoothed using the EMA method.
        """
        onset_times, (_, beat_times) = audio_data

        selected = self._select_frames(processed_frames)

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
                    angle_weight, kinematic_weight = self.STATIC_ANGLE_WEIGHT_MULTIPLIER, self.STATIC_KINEMATIC_WEIGHT_MULTIPLIER
                elif speed < self.FAST_VELOCITY_THRESHOLD_DEG_PER_SEC:
                    angle_weight, kinematic_weight = self.SLOW_ANGLE_WEIGHT_MULTIPLIER, self.SLOW_KINEMATIC_WEIGHT_MULTIPLIER
                else:
                    angle_weight, kinematic_weight = self.FAST_ANGLE_WEIGHT_MULTIPLIER, self.FAST_KINEMATIC_WEIGHT_MULTIPLIER

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
                        hip_y=frame.hip_height,
                        body_rotation_deg=frame.hip_rotation,
                    ),
                    joints=joints,
                )
            )

        duration = (
            float(np.max(beat_times))
            if np.asarray(beat_times).size
            else (float(processed_frames[-1]["timestamp"]) if processed_frames else 0.0)
        )

        return ChoreoData(
            metadata=ChoreoMetadata(song_id=0, fps=fps, duration_sec=duration),
            frames=output_frames,
        )
