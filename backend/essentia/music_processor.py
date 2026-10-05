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
    Arrays returned contain hop frame values.
    """
    #na razie do każdej metody są dodane antystereo guardy, jeszcze zobaczymy, czy jest sens ogarniania osobnej analizy dla stereo, czy wszystko będziemy robić w mono

    def __init__(self, sample_rate, frame_size, hop_size):
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

    def onset_detection(self, audio, method):
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
        return onsets_in_seconds * (self.sample_rate / self.hop_size)

    def superflux_detection(self, audio):
        """Detects song onsets using Superflux algorithm."""
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        superflux = es.SuperFluxExtractor(frameSize=self.frame_size, hopSize=self.hop_size, sampleRate=self.sample_rate)
        onsets_in_seconds, novelty_curve = superflux(audio)

        return onsets_in_seconds * (self.sample_rate / self.hop_size)

    def beat_detection(self, audio, method):
        """
        Computes the BPM value for a given track and provides an array of song beats.
        """
        if method not in ['multifeature', 'degara']:
            raise ValueError(f"Invalid method '{method}'.")

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        rhythm_extractor = es.RhythmExtractor2013(method=method)
        bpm, beats, beats_confidence, _, beats_intervals = rhythm_extractor(audio)
        beats_frames = beats * (self.sample_rate / self.hop_size)
        return bpm, beats_frames

    def song_segmentation(self, audio):
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
        return song_segmenter(features.T)

    def play_and_visualize(self, audio, segments=None, beats=None, onsets=None):
        segments = segments if segments is not None else []
        beats = beats if beats is not None else []
        onsets = onsets if onsets is not None else []

        samples = len(audio)
        hop_frames = samples / self.hop_size
        x_axis_frames = np.linspace(0, hop_frames, num=samples)

        step = max(1, len(audio) // 10000)

        fig, ax = plt.subplots(figsize=(14, 4))

        ax.plot(
            x_axis_frames[::step],
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

        frames_per_sec = self.sample_rate / self.hop_size
        window_frames = 10 * frames_per_sec
        duration_sec = samples / self.sample_rate

        ax.set_xlim(0, window_frames)
        ax.set_ylim(np.min(audio) * 1.1, np.max(audio) * 1.1)
        ax.set_xlabel('Frames')
        ax.set_ylabel('Amplitude')
        ax.set_title('Scrolling Audio Visualizer (Frame-Based)')
        ax.legend(loc='upper right')

        start_time = time.time()
        sd.play(audio, self.sample_rate)

        def update():
            elapsed_seconds = time.time() - start_time
            if elapsed_seconds <= duration_sec:
                current_frame = elapsed_seconds * frames_per_sec
                playhead.set_xdata([current_frame, current_frame])

                left = max(0.0, current_frame - (window_frames * 0.3))
                right = left + window_frames

                if right > hop_frames:
                    right = hop_frames
                    left = max(0.0, right - window_frames)

                ax.set_xlim(left, right)

            return (playhead,)

        _ = animation.FuncAnimation(
            fig, update, interval=30, blit=False, cache_frame_data=False
        )

        plt.tight_layout()
        plt.show()
        sd.stop()

    def write_sound_markers(self, audio, onsets):
        onsets_in_seconds = np.array(onsets) * (self.hop_size / self.sample_rate)
        marker = es.AudioOnsetsMarker(onsets=onsets_in_seconds, type='beep', sampleRate=self.sample_rate)
        return marker(audio)