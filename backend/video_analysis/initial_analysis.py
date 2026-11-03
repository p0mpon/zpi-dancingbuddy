import cv2
import mediapipe as mp
import numpy as np
from typing import Dict, List, Optional, Callable, Tuple
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from scipy.signal import savgol_filter
from video_analysis.video_frame_model import Frame, Joint

JOINT_CONFIG = {
    'r_elbow': (12, 14, 16),
    'l_elbow': (11, 13, 15),
    'r_shoulder': (24, 12, 14),
    'l_shoulder': (23, 11, 13),
    'r_hip': (12, 24, 26),
    'l_hip': (11, 23, 25),
    'r_knee': (24, 26, 28),
    'l_knee': (23, 25, 27),
    'r_ankle': (26, 28, 32),
    'l_ankle': (25, 27, 31),
    'r_torso': (11, 12, 24),
    'l_torso': (12, 11, 23)
}


def calculate_3d_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)

    if norm_ba == 0.0 or norm_bc == 0.0:
        return 0.0

    cosine_angle = np.dot(ba, bc) / (norm_ba * norm_bc)
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    return float(np.degrees(angle))


def extract_pose_features(
        world_landmarks: np.ndarray,
        vis_landmarks: np.ndarray,
        joints_config: Dict[str, tuple]
) -> Tuple[Dict[str, Joint], float, float]:
    joints_data: Dict[str, Joint] = {}
    hip_y_norm = 0.0

    for joint_name, (index_a, index_b, index_c) in joints_config.items():
        # Cleanly extract X, Y, Z coordinates for angle calculation
        position_a = world_landmarks[index_a, :3]
        position_b = world_landmarks[index_b, :3]
        position_c = world_landmarks[index_c, :3]

        angle = calculate_3d_angle(position_a, position_b, position_c)

        # Visibility is stored at index 3
        visibility = float(min(world_landmarks[index_a, 3], world_landmarks[index_b, 3], world_landmarks[index_c, 3]))

        joints_data[joint_name] = Joint(
            angle=round(angle, 2),
            visibility=round(visibility, 4)
        )

    hip_r_2d = vis_landmarks[24]
    hip_l_2d = vis_landmarks[23]
    mid_hip_y_2d = (hip_r_2d[1] + hip_l_2d[1]) / 2.0

    ankles_y = [vis_landmarks[27, 1], vis_landmarks[28, 1]]
    body_height_2d = max(ankles_y) - vis_landmarks[0, 1]

    if body_height_2d > 0.1:
        hip_y_norm = float(mid_hip_y_2d / body_height_2d)

    dx = world_landmarks[23, 0] - world_landmarks[24, 0]
    dz = world_landmarks[23, 2] - world_landmarks[24, 2]
    hip_rot = float(np.degrees(np.arctan2(dz, dx)))

    return joints_data, hip_y_norm, hip_rot


def smooth_coordinates(
        coords: np.ndarray,
        window_length: int = 11,
        polyorder: int = 3
) -> np.ndarray:
    if len(coords) < window_length:
        window_length = len(coords)
        if window_length % 2 == 0:
            window_length -= 1

    if window_length <= polyorder or len(coords) == 0:
        return coords

    smoothed = coords.copy()
    smoothed[:, :, :3] = savgol_filter(coords[:, :, :3], window_length, polyorder, axis=0)

    return smoothed


def calculate_kinematics_and_height(
        frames: List[Frame],
        smoothed_hip_y: List[float],
        dt: float,
        playback_speed: float
):
    effective_dt = dt * playback_speed
    valid_hip_y = [y for y in smoothed_hip_y if y > 0.0]
    floor_baseline_y = float(np.percentile(valid_hip_y, 90)) if valid_hip_y else 0.0

    for i, frame in enumerate(frames):
        y_value = smoothed_hip_y[i]
        if y_value > 0.0:
            proportional_height = max(0.0, floor_baseline_y - y_value)
            frame.hip_height = round(proportional_height, 4)

        for joint_name, joint_obj in frame.joints.items():
            if i > 0 and joint_obj.angle is not None and frames[i - 1].joints[joint_name].angle is not None:
                prev_angle = frames[i - 1].joints[joint_name].angle
                vel = (joint_obj.angle - prev_angle) / effective_dt
                joint_obj.angular_velocity = round(vel, 2)
            else:
                joint_obj.angular_velocity = 0.0

            if i > 1 and joint_obj.angular_velocity is not None:
                prev_vel = frames[i - 1].joints[joint_name].angular_velocity or 0.0
                acc = (joint_obj.angular_velocity - prev_vel) / effective_dt
                joint_obj.angular_acceleration = round(acc, 2)
            else:
                joint_obj.angular_acceleration = 0.0


def default_progress_reporter(current_frame: int, total_frames: int, progress_pct: float):
    print(f"[Processing Video] Frame {current_frame}/{total_frames} ({progress_pct:.1f}%)")


def analyze_dance_video(
        video_path: str,
        model_path: str = "pose_landmarker_full.task",
        target_fps: float = 30.0,
        playback_speed: float = 1.0,
        mirror_video: bool = False,
        joints_config: Optional[Dict[str, tuple]] = None,
        progress_callback: Callable[[int, int, float], None] = default_progress_reporter
) -> List[Frame]:

    if joints_config is None:
        joints_config = JOINT_CONFIG

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise ValueError(f"Failed to open video file: {video_path}")

    native_fps = capture.get(cv2.CAP_PROP_FPS) or target_fps
    total_native_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration_sec = total_native_frames / native_fps if native_fps > 0 else 0
    total_target_frames = int(video_duration_sec * target_fps)
    dt = 1.0 / target_fps

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )

    raw_world_coords = []
    raw_vis_coords = []
    frame_timestamps = []

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        current_target_frame = 0
        current_native_frame = 0
        frame_stride = max(1, round(native_fps / target_fps))

        while True:
            ret, frame_img = capture.read()
            if not ret:
                break


            # Skip frames to match target FPS
            if current_native_frame % frame_stride != 0:
                current_native_frame += 1
                continue

            # Mirror the frame if required
            if mirror_video:
                frame_img = cv2.flip(frame_img, 1)

            # Scale down to 480p
            h, w = frame_img.shape[:2]
            if w > 854:
                scale = 854 / w
                frame_img = cv2.resize(frame_img, (int(w * scale), int(h * scale)))

            rgb_frame = cv2.cvtColor(frame_img, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            timestamp_ms = int(current_native_frame * (1000.0 / native_fps))
            pose_result = landmarker.detect_for_video(mp_image, timestamp_ms)
            timestamp = round(current_target_frame * dt, 4)

            # Store coordinates in highly structured format: shape (33, 4) -> (x, y, z, visibility)
            if pose_result.pose_world_landmarks and pose_result.pose_landmarks:
                wl = np.array([[lm.x, lm.y, lm.z, lm.visibility] for lm in pose_result.pose_world_landmarks[0]])
                vl = np.array([[lm.x, lm.y, lm.z, lm.visibility] for lm in pose_result.pose_landmarks[0]])
            else:
                # To prevent massive spikes in smoothing, inherit previous frame if MediaPipe loses tracking
                if len(raw_world_coords) > 0:
                    wl = raw_world_coords[-1].copy()
                    vl = raw_vis_coords[-1].copy()
                else:
                    wl = np.zeros((33, 4))
                    vl = np.zeros((33, 4))

            raw_world_coords.append(wl)
            raw_vis_coords.append(vl)
            frame_timestamps.append(timestamp)

            current_target_frame += 1
            current_native_frame += 1

            if current_target_frame % 10 == 0:
                progress_pct = min(100.0, (current_native_frame / total_native_frames) * 100.0)
                progress_callback(current_target_frame, total_target_frames, progress_pct)

    capture.release()

    # Apply smoothing
    world_arr = smooth_coordinates(np.array(raw_world_coords))
    vis_arr = smooth_coordinates(np.array(raw_vis_coords))

    frames: List[Frame] = []
    smoothed_hip_y: List[float] = []

    # Calculate Frame data from smoothed landmarks
    for i in range(len(world_arr)):
        joints_data, hip_y_norm, hip_rot = extract_pose_features(
            world_arr[i], vis_arr[i], joints_config
        )

        smoothed_hip_y.append(hip_y_norm)

        frame_obj = Frame(
            frame_id=i,
            timestamp=frame_timestamps[i],
            hip_height=0.0,
            hip_rotation=round(hip_rot, 2),
            joints=joints_data
        )
        frames.append(frame_obj)

    calculate_kinematics_and_height(
        frames, smoothed_hip_y, dt, playback_speed
    )

    return frames