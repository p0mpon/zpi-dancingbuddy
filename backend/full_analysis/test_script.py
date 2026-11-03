import json
from random import random
import numpy as np
from pathlib import Path

from full_analysis.choreo_comparator import compare_choreos
from full_analysis.choreo_encoder import AudioData, ChoreoEncoder
from full_analysis.frame_processor import FrameProcessor
from zpi_app.zpi_app.video_frame_model import Frame, Joint


def audio_json_to_audio_data(audio_json: dict[str, list[float]]) -> AudioData:
    onset_times = np.asarray(audio_json["onsets"], dtype=float)
    beat_times = np.asarray(audio_json["beats"], dtype=float)

    beat_intervals = np.diff(beat_times)
    bpm = 60.0 / float(np.mean(beat_intervals)) if beat_intervals.size else 0.0

    return onset_times, (bpm, beat_times)


def video_json_to_frames(video_json: list[dict]) -> list[Frame]:
    return [
        Frame(
            frame_id=frame["frame_id"],
            timestamp=frame["timestamp"],
            joints={
                str(joint_id): Joint(**joint)
                for joint_id, joint in enumerate(frame["joints"])
            },
            hip_rotation=frame["hip_rotation"],
            hip_height=frame["hip_height"],
        )
        for frame in video_json
    ]


def processed_video_to_frames(
    processed_frames: list[dict[str, object]],
) -> list[Frame]:
    return [
        Frame(
            frame_id=processed_frame["frame"].frame_id,
            timestamp=float(processed_frame["timestamp"]), # you can add some sort of delay here to see how the final score changes :D
            joints={
                name: Joint(
                    angle=values["angle"],
                    angular_velocity=values["velocity"],
                    angular_acceleration=values["acceleration"],
                    visibility=values["visibility"],
                )
                for name, values in processed_frame["joints"].items()
            },
            hip_rotation=processed_frame["frame"].hip_rotation,
            hip_height=processed_frame["frame"].hip_height,
        )
        for processed_frame in processed_frames
    ]


def skibidi():
    data_dir = Path(__file__).resolve().parent

    # Audio data
    with (data_dir / "sample_audio" / "test_audio3.json").open() as f:
        audio_json = json.load(f)
    audio = audio_json_to_audio_data(audio_json)
        
    # Video data
    with (data_dir / "sample_video" / "test_video3.json").open() as f:
        video_json = json.load(f)
    video_data = video_json_to_frames(video_json)

    # Process the video data
    processor = FrameProcessor()
    processed_video_frames, frame_interval = processor._preprocess_frames(video_data)

    # Choreo encoding
    encoder = ChoreoEncoder()
    return encoder.encode_to_choreo(
        audio_data=audio, 
        processed_frames=processed_video_frames, 
        frame_interval=frame_interval)

def test_comparator():
    data_dir = Path(__file__).resolve().parent
    with (data_dir / "sample_video" / "test_video3.json").open() as f:
        video_json = json.load(f)
    video_data = video_json_to_frames(video_json)
    processor = FrameProcessor()
    processed_video_frames, _ = processor._preprocess_frames(video_data)
    compare_choreo = processed_video_to_frames(processed_video_frames)

    base_choreo = skibidi()

    scored_frames, general_score = compare_choreos(base_choreo, compare_choreo)

    return scored_frames, general_score