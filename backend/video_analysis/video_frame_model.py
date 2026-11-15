from pydantic import BaseModel
from typing import Optional, List, Tuple, Dict


class Joint(BaseModel):
    angle: Optional[float] = None
    angular_velocity: Optional[float] = None
    angular_acceleration: Optional[float] = None
    visibility: float


class Frame(BaseModel):
    frame_id: int
    timestamp: float
    joints: Dict[str, Joint]

    hip_rotation: Optional[float] = None
    hip_height: Optional[float] = None


class RawFrame(BaseModel):
    """
    Raw frame data as received from the MediaPipe model.
    """
    timestamp: float
    world_landmarks: list[list[float]]
    vis_landmarks: list[list[float]]