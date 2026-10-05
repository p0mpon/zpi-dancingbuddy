import essentia.standard as es
from pathlib import Path

class MusicLoader:
    def __init__(self, input_dir, output_dir):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_track(self, file_name, sample_rate: int = 44100, channels: bool = False):
        file_path = str(self.input_dir / file_name)
        if channels:
            audio, sr, *_ = es.AudioLoader(filename=file_path)()
            if sr != sample_rate:
                audio = es.Resample(
                    inputSampleRate=sr, outputSampleRate=sample_rate
                )(audio)
            return audio

        return es.MonoLoader(filename=file_path, sampleRate=sample_rate)()

    def save_track(self, audio_data, file_name: str, sample_rate: int = 44100, bitrate: int = 320):
        file_path = str(self.output_dir / file_name)

        if audio_data.ndim == 1:
            es.MonoWriter(filename=file_path, sampleRate=sample_rate, bitrate=bitrate)(audio_data)
        else:
            es.AudioOutput(filename=file_path, sampleRate=sample_rate, bitrate=bitrate)(audio_data)