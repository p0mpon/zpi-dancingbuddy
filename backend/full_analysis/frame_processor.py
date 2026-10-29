import numpy as np
from typing import List

from zpi_app.zpi_app.video_frame_model import Frame, Joint


class FrameProcessor:
    """
    Processes video frames to smooth angle data and calculate kinematic properties.
    """
    def __init__(self, 
                 visibility_threshold: float = 0.5,
                 ema_alpha: float = 0.5,
                 default_fps: int = 30):
        # threshold for joint visibility, below which the joint is considered not visible
        self.VISIBILITY_THRESHOLD = visibility_threshold
        # alpha value for EMA smoothing of angles
        self.EMA_ALPHA = ema_alpha
        # default frames per second for video data
        self.DEFAULT_FPS = default_fps

    @staticmethod
    def _number(value: object, default: float = 0.0) -> float:
        """
        Makes a float out of a value, or returns a default if the value is None or not finite.
        """
        return float(value) if value is not None and np.isfinite(value) else default

    def _is_visible(self, joint: Joint) -> bool:
        """
        Check if a joint is visible vased on a threshold.
        If the joint is None, the visibility is set to 0.
        """
        visibility = joint.visibility if joint is not None else None
        return (
            visibility is not None
            and visibility >= self.VISIBILITY_THRESHOLD
        )

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