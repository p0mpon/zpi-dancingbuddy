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
    landmarks_2d: Optional[List[Tuple[float, float, float]]] = None

    hip_rotation: Optional[float] = None
    hip_height: Optional[float] = None