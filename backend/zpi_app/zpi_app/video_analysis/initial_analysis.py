import cv2
import mediapipe as mp
import numpy as np
from typing import Dict, List, Optional, Callable
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from zpi_app.zpi_app.video_analysis.video_frame_model import Frame, Joint

DEFAULT_JOINTS = {
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


def default_progress_reporter(current_frame: int, total_frames: int, progress_pct: float):
    print(f"[Processing Video] Frame {current_frame}/{total_frames} ({progress_pct:.1f}%)")


def analyze_dance_video(
        video_path: str,
        model_path: str = "pose_landmarker_full.task",
        target_fps: float = 30.0,
        reference_user_height_m: float = 1.75,
        joints_config: Optional[Dict[str, tuple]] = None,
        progress_callback: Callable[[int, int, float], None] = default_progress_reporter
    ) -> List[Frame]:
    if joints_config is None:
        joints_config = DEFAULT_JOINTS

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video file: {video_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or target_fps
    total_native_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration_sec = total_native_frames / native_fps if native_fps > 0 else 0
    total_target_frames = int(video_duration_sec * target_fps)
    dt = 1.0 / target_fps

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )

    frames: List[Frame] = []
    raw_hip_y_normalized: List[float] = []

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        current_target_frame = 0

        while current_target_frame < total_target_frames:
            target_time_ms = (current_target_frame / target_fps) * 1000.0
            cap.set(cv2.CAP_PROP_POS_MSEC, target_time_ms)

            ret, frame_img = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame_img, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            pose_result = landmarker.detect(mp_image)

            timestamp = round(current_target_frame * dt, 4)
            joints_data: Dict[str, Joint] = {}
            hip_y_norm = 0.0
            hip_rot = 0.0

            if pose_result.pose_world_landmarks and pose_result.pose_landmarks:
                world_landmarks = pose_result.pose_world_landmarks[0]
                vis_landmarks = pose_result.pose_landmarks[0]

                for joint_name, (idx_a, idx_b, idx_c) in joints_config.items():
                    lm_a = world_landmarks[idx_a]
                    lm_b = world_landmarks[idx_b]
                    lm_c = world_landmarks[idx_c]

                    pos_a = np.array([lm_a.x, lm_a.y, lm_a.z])
                    pos_b = np.array([lm_b.x, lm_b.y, lm_b.z])
                    pos_c = np.array([lm_c.x, lm_c.y, lm_c.z])

                    angle = calculate_3d_angle(pos_a, pos_b, pos_c)
                    visibility = float(min(lm_a.visibility, lm_b.visibility, lm_c.visibility))

                    joints_data[joint_name] = Joint(
                        angle=round(angle, 2),
                        angular_velocity=None,
                        angular_acceleration=None,
                        visibility=round(visibility, 4)
                    )

                hip_r_2d = vis_landmarks[24]
                hip_l_2d = vis_landmarks[23]
                mid_hip_y_2d = (hip_r_2d.y + hip_l_2d.y) / 2.0

                ankles_y = [vis_landmarks[27].y, vis_landmarks[28].y]
                body_height_2d = max(ankles_y) - vis_landmarks[0].y

                if body_height_2d > 0.1:
                    hip_y_norm = float(mid_hip_y_2d / body_height_2d)

                # Calculate hip yaw rotation (XZ plane) relative to camera
                dx = world_landmarks[23].x - world_landmarks[24].x
                dz = world_landmarks[23].z - world_landmarks[24].z
                hip_rot = float(np.degrees(np.arctan2(dz, dx)))

            else:
                for joint_name in joints_config.keys():
                    joints_data[joint_name] = Joint(
                        angle=0.0,
                        angular_velocity=None,
                        angular_acceleration=None,
                        visibility=0.0
                    )

            raw_hip_y_normalized.append(hip_y_norm)

            frame_obj = Frame(
                frame_id=current_target_frame,
                timestamp=timestamp,
                hip_height=0.0,
                hip_rotation=round(hip_rot, 2),
                joints=joints_data
            )
            frames.append(frame_obj)

            current_target_frame += 1
            if current_target_frame % 10 == 0:
                progress_pct = (current_target_frame / total_target_frames) * 100.0
                progress_callback(current_target_frame, total_target_frames, progress_pct)

    cap.release()

    # Calculate absolute jump heights against 90th percentile baseline
    valid_hip_y = [y for y in raw_hip_y_normalized if y > 0.0]
    floor_baseline_y = float(np.percentile(valid_hip_y, 90)) if valid_hip_y else 0.0

    for i, frame_obj in enumerate(frames):
        y_val = raw_hip_y_normalized[i]
        if y_val > 0.0:
            height_m = max(0.0, (floor_baseline_y - y_val) * reference_user_height_m)
            frame_obj.hip_height = round(height_m, 3)

        for joint_name, joint_obj in frame_obj.joints.items():
            # First derivative: Angular velocity
            if i > 0:
                prev_angle = frames[i - 1].joints[joint_name].angle
                vel = (joint_obj.angle - prev_angle) / dt
                joint_obj.angular_velocity = round(vel, 2)
            else:
                joint_obj.angular_velocity = 0.0

            # Second derivative: Angular acceleration
            if i > 1:
                prev_vel = frames[i - 1].joints[joint_name].angular_velocity or 0.0
                acc = (joint_obj.angular_velocity - prev_vel) / dt
                joint_obj.angular_acceleration = round(acc, 2)
            else:
                joint_obj.angular_acceleration = 0.0

    return frames


if __name__ == "__main__":
    import os
    import sys
    import time

    os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts"
    test_video_path = "test_video.mp4"
    target_fps = 15.0

    if not os.path.exists(test_video_path):
        print(f"Error: Test video '{test_video_path}' not found in the current directory.")
        sys.exit(1)

    print(f"Starting initial analysis for '{test_video_path}'...")
    start_time = time.time()

    try:
        frames_data = analyze_dance_video(test_video_path, target_fps=target_fps)
        processing_time = time.time() - start_time
        print(f"\nAnalysis complete in {processing_time:.2f}s")
        print(f"Successfully processed {len(frames_data)} frames.")
    except Exception as e:
        print(f"Analysis failed: {e}")
        sys.exit(1)

    print("\nStarting playback. Press 'q' to exit.")
    cap = cv2.VideoCapture(test_video_path)

    SKELETON_CONNECTIONS = [
        (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
        (11, 23), (12, 24), (23, 24),
        (23, 25), (25, 27), (27, 31),
        (24, 26), (26, 28), (28, 32)
    ]

    active_landmarks = set()
    for indices in DEFAULT_JOINTS.values():
        active_landmarks.update(indices)

    base_options = python.BaseOptions(model_asset_path="pose_landmarker_full.task")
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        min_pose_detection_confidence=0.5
    )

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        for data in frames_data:
            target_time_ms = (data.frame_id / target_fps) * 1000.0
            cap.set(cv2.CAP_PROP_POS_MSEC, target_time_ms)

            ret, frame = cap.read()
            if not ret:
                break

            h, w, _ = frame.shape

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            pose_result = landmarker.detect(mp_image)

            if pose_result.pose_landmarks:
                landmarks = pose_result.pose_landmarks[0]

                for start_idx, end_idx in SKELETON_CONNECTIONS:
                    lm_s = landmarks[start_idx]
                    lm_e = landmarks[end_idx]

                    if lm_s.visibility > 0.5 and lm_e.visibility > 0.5:
                        pt_start = (int(lm_s.x * w), int(lm_s.y * h))
                        pt_end = (int(lm_e.x * w), int(lm_e.y * h))
                        cv2.line(frame, pt_start, pt_end, (245, 117, 66), 2)

                for idx in active_landmarks:
                    lm = landmarks[idx]
                    if lm.visibility > 0.5:
                        pt = (int(lm.x * w), int(lm.y * h))
                        cv2.circle(frame, pt, 3, (245, 66, 230), -1)

            cv2.putText(frame, f"Frame: {data.frame_id}", (15, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Jump Height: {data.hip_height:.2f}m", (15, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Hip Rotation: {data.hip_rotation:.1f} deg", (15, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            r_elbow = data.joints.get('r_elbow')
            if r_elbow:
                cv2.putText(frame, f"R Elbow: {r_elbow.angle:.1f} deg", (15, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

                if r_elbow.angular_velocity is not None:
                    cv2.putText(frame, f"R Elbow Vel: {r_elbow.angular_velocity:.1f} deg/s", (15, 150),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

            cv2.imshow("Analysis Telemetry Overlay", frame)

            if cv2.waitKey(int(1000 / target_fps)) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()