import essentia.standard as es
from pathlib import Path

import numpy as np

class MusicLoader:
    def load_track(self, file_name: str, sample_rate: int = 44100, channels: bool = False) -> np.ndarray:
        file_path = str(Path(file_name))
        if channels:
            audio, sr, *_ = es.AudioLoader(filename=file_path)()
            if sr != sample_rate:
                audio = es.Resample(
                    inputSampleRate=sr, outputSampleRate=sample_rate
                )(audio)
            return audio

        return es.MonoLoader(filename=file_path, sampleRate=sample_rate)()