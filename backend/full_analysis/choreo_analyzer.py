from video_analysis.initial_analysis import analyze_dance_video
from audio_analysis.music_loader import MusicLoader
from audio_analysis.music_processor import MusicProcessor
from full_analysis.choreo_encoder import encode_to_choreo
from full_analysis.choreo_data_model import ChoreoFrame


def perform_full_analysis(file_path: str) -> list[ChoreoFrame]:
    # Video analysis
    analyzed_video_frames = analyze_dance_video(file_path)

    # Audio analysis
    music_loader = MusicLoader()
    audio_data = music_loader.load_track(file_path)
    music_processor = MusicProcessor(44100, 2048, 512)
    bpm, beats = music_processor.beat_detection(audio_data, 'multifeature')
    onsets = music_processor.onset_detection(audio_data, 'superflux')

    # Full analysis
    choreo_frames = encode_to_choreo((onsets, (bpm, beats)), analyzed_video_frames)

    return choreo_frames