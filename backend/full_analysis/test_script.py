import json
from pathlib import Path

import numpy as np

from full_analysis.choreo_encoder import AudioData, ChoreoEncoder
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

    # Choreo encoding
    encoder = ChoreoEncoder()
    return encoder.encode_to_choreo(audio_data=audio, video_data=video_data)