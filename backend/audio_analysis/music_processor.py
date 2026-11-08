from typing import Tuple, Optional

import essentia
import essentia.standard as es
import numpy as np
import sounddevice as sd
import time
import matplotlib.animation as animation
import matplotlib.pyplot as plt

class MusicProcessor:
    """
    A class containing methods for music analysis.
    Arrays returned contain values in seconds.
    """

    def __init__(self, sample_rate: int, frame_size: int, hop_size: int) -> None:
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.hop_size = hop_size

        self.window = es.Windowing(type='hann')
        self.fft = es.FFT()
        self.c2p = es.CartesianToPolar()
        self.spectrum = es.Spectrum()
        self.spectral_peaks = es.SpectralPeaks(orderBy='magnitude')
        self.mfcc = es.MFCC()
        self.hpcp = es.HPCP()

    def _default_onset_detection(self, audio: np.ndarray, method: str) -> np.ndarray:
        """Detects song onsets using OnsetDetection algorithm."""

        if method not in ['hfc', 'complex', 'complex_phase', 'flux', 'melflux', 'mrms']:
            raise ValueError(f"Invalid method '{method}'.")

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        onset_detector = es.OnsetDetection(method=method)
        onsets = es.Onsets()
        pool = essentia.Pool()

        for frame in es.FrameGenerator(
                audio, frameSize=self.frame_size, hopSize=self.hop_size, startFromZero=True
        ):
            w = self.window(frame)
            magnitude, phase = self.c2p(self.fft(w))
            pool.add('odf', onset_detector(magnitude, phase))

        onsets_in_seconds = onsets(np.array([pool['odf']]), [1])
        return onsets_in_seconds

    def _superflux_detection(self, audio: np.ndarray) -> np.ndarray:
        """Detects song onsets using Superflux algorithm."""
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        superflux = es.SuperFluxExtractor(sampleRate=self.sample_rate)
        onsets_in_seconds = superflux(audio)

        return onsets_in_seconds

    def onset_detection(self, audio: np.ndarray, method: str) -> np.ndarray:
        """
        Detects song onsets using a chosen method.
        Available methods: hfc, complex, complex_phase, flux, melflux, mrms, superflux
        """
        if method not in ['hfc', 'complex', 'complex_phase', 'flux', 'melflux', 'mrms', 'superflux']:
            method = 'hfc'

        if method in ['superflux']:
            return self._superflux_detection(audio)
        else:
            return self._default_onset_detection(audio, method)

    def beat_detection(self, audio: np.ndarray, method: str) -> Tuple[float, np.ndarray]:
        """
        Computes the BPM value for a given track and provides an array of song beats.
        Available methods: multifeature, degara
        """
        if method not in ['multifeature', 'degara']:
            method = 'multifeature'

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        rhythm_extractor = es.RhythmExtractor2013(method=method)
        bpm, beats, _, _, _ = rhythm_extractor(audio)
        return bpm, beats

    def song_segmentation(self, audio: np.ndarray) -> np.ndarray:
        """
        Divides a song into segments using the SBic algorithm.
        """

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        mfccs = []
        hpcps = []

        for frame in es.FrameGenerator(audio, frameSize=self.frame_size, hopSize=self.hop_size, startFromZero=True):
            w = self.window(frame)
            frequencies, magnitudes = self.spectral_peaks(w)
            _, mfcc_coeffs = self.mfcc(self.spectrum(w))
            hpcp_result = self.hpcp(magnitudes, frequencies)

            mfccs.append(mfcc_coeffs)
            hpcps.append(hpcp_result)

        features = np.hstack([np.array(mfccs), np.array(hpcps)])

        song_segmenter = es.SBic()
        segments = song_segmenter(features.T)

        segments_in_seconds = segments * (self.hop_size / self.sample_rate)
        return segments_in_seconds

    def play_and_visualize(self, audio: np.ndarray, segments: Optional[np.ndarray] = None,
                                                    beats: Optional[np.ndarray] = None,
                                                    onsets: Optional[np.ndarray] = None) -> None:
        segments = segments if segments is not None else []
        beats = beats if beats is not None else []
        onsets = onsets if onsets is not None else []

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        samples = len(audio)
        duration = samples / self.sample_rate
        x_axis = np.linspace(0, duration, num=samples)

        step = max(1, len(audio) // 10000)

        fig, ax = plt.subplots(figsize=(14, 4))

        ax.plot(
            x_axis[::step],
            audio[::step],
            color='skyblue',
            alpha=0.7,
            label='Waveform',
        )

        for i, seg in enumerate(segments):
            ax.axvline(
                x=seg,
                color='red',
                linestyle='--',
                alpha=0.8,
                label='Song Segments' if i == 0 else '',
            )

        for i, b in enumerate(beats):
            ax.axvline(
                x=b,
                color='orange',
                linestyle=':',
                alpha=0.5,
                label='Beats' if i == 0 else '',
            )

        for i, o in enumerate(onsets):
            ax.axvline(
                x=o,
                color='purple',
                linestyle=':',
                alpha=0.4,
                label='Onsets' if i == 0 else '',
            )

        (playhead,) = ax.plot(
            [0, 0],
            [np.min(audio), np.max(audio)],
            color='black',
            lw=1.5,
            label='Playhead',
        )

        window_sec = 10
        ax.set_xlim(0, window_sec)
        ax.set_ylim(np.min(audio) * 1.1, np.max(audio) * 1.1)
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Amplitude')
        ax.legend(loc='upper right')

        start_time = time.time()
        sd.play(audio, self.sample_rate)

        def update(frame):
            elapsed_seconds = time.time() - start_time
            if elapsed_seconds <= duration:
                playhead.set_xdata([elapsed_seconds, elapsed_seconds])

                left = max(0.0, elapsed_seconds - (window_sec * 0.3))
                right = left + window_sec

                if right > duration:
                    right = duration
                    left = max(0.0, right - window_sec)

                ax.set_xlim(left, right)

            return (playhead,)

        _ = animation.FuncAnimation(
            fig, update, interval=30, blit=False, cache_frame_data=False
        )

        plt.tight_layout()
        plt.show()
        sd.stop()

    def write_sound_markers(self, audio: np.ndarray, onsets: np.ndarray) -> np.ndarray:
        marker = es.AudioOnsetsMarker(onsets=onsets, type='beep', sampleRate=self.sample_rate)
        return marker(audio)