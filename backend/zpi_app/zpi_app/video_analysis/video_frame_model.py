from pydantic import BaseModel
from typing import Optional

class Joint(BaseModel):
    angle: Optional[float]
    angular_velocity: Optional[float]
    angular_acceleration: Optional[float]
    visibility: float

class Frame(BaseModel):
    frame_id: int
    timestamp: float
    joints: dict[str, Joint]
    hip_rotation: Optional[float]
    hip_height: Optional[float]