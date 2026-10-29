from pydantic import BaseModel


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