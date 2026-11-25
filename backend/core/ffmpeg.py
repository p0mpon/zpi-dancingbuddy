"""
Thin wrappers around ffprobe / ffmpeg (both installed in the Dockerfile).

Paths in, facts or files out. No Django models, no storage, no DB: this module doesn't know
whether a file is a video or a dance attempt's recording. Used by `videos` and `dance_attempts`.
"""

import json
import os
import subprocess
from dataclasses import dataclass

TARGET_FPS = 30
MAX_SHORT_SIDE = 1080
KEYFRAME_INTERVAL_FRAMES = 15          # 0.5 s at 30 fps
X264_PRESET = 'veryfast'
X264_CRF = 23
AUDIO_BITRATE = '128k'
AUDIO_SAMPLE_RATE = 44100
PROBE_TIMEOUT_SECONDS = 10
NORMALIZE_TIMEOUT_SECONDS = 30 * 60
FRAME_TIMEOUT_SECONDS = 30

# How many of ffmpeg's last stderr lines go into an error message (the rest is the banner and progress).
_STDERR_LINES_KEPT = 5


class FFmpegError(Exception):
    """ffmpeg / ffprobe exited with an error (or isn't installed)."""


class FFmpegTimeout(FFmpegError):
    """ffmpeg took longer than the timeout."""


@dataclass(frozen=True)
class VideoInfo:
    # width / height are the STORED size. Phone rotation is applied by ffmpeg during
    # normalization, so don't use them to tell portrait from landscape.
    width: int
    height: int
    fps: float | None
    duration_seconds: float | None
    video_codec: str
    has_audio: bool


def _parse_fps(value):
    """'30000/1001' -> 29.97, '0/0' (unknown) -> None."""
    try:
        numerator, denominator = value.split('/')
        if float(denominator) == 0:
            return None
        return float(numerator) / float(denominator)
    except (AttributeError, ValueError):
        return None


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def probe_video(path):
    """VideoInfo for the file, or None if it can't be read or has no video stream."""
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',                  # only errors, no banner
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=True,
        )
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None

    streams = data.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if video is None or not video.get('width') or not video.get('height'):
        return None
    return VideoInfo(
        width=int(video['width']),
        height=int(video['height']),
        fps=_parse_fps(video.get('avg_frame_rate')),
        duration_seconds=_parse_float(data.get('format', {}).get('duration')),
        video_codec=video.get('codec_name', ''),
        has_audio=any(s.get('codec_type') == 'audio' for s in streams),
    )


def read_duration_seconds(path):
    """Length of the video in seconds, or None if it can't be read
    (not a video, broken file, or no duration stored in the file)."""
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',                              # print only errors, no banner
                '-show_entries', 'format=duration',         # only the container's duration
                '-of', 'default=noprint_wrappers=1:nokey=1',  # output just "12.345000"
                str(path),
            ],
            capture_output=True,    # put stdout/stderr into result instead of the console
            text=True,              # give strings, not bytes
            timeout=PROBE_TIMEOUT_SECONDS,
            check=True,             # exit code != 0 -> CalledProcessError
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None


def _run_ffmpeg(arguments, *, timeout):
    """Run ffmpeg with `arguments`; raise FFmpegError / FFmpegTimeout instead of returning a bad result."""
    try:
        result = subprocess.run(
            ['ffmpeg', *arguments],
            capture_output=True,
            text=True,
            errors='replace',   # ffmpeg's stderr can contain bytes that aren't valid text
            timeout=timeout,
            check=False,        # the exit code is checked below, to put ffmpeg's message in the error
        )
    except subprocess.TimeoutExpired as error:
        raise FFmpegTimeout(f'ffmpeg took longer than {timeout} s.') from error
    except FileNotFoundError as error:
        raise FFmpegError('ffmpeg is not installed.') from error

    if result.returncode != 0:
        tail = '\n'.join(result.stderr.strip().splitlines()[-_STDERR_LINES_KEPT:])
        raise FFmpegError(f'ffmpeg exited with code {result.returncode}: {tail}')


def _scale_filter():
    """Short side at most MAX_SHORT_SIDE, aspect kept, never upscaled, both sides even.

    factor = min(1, 1080 / short side): 1 for small videos, so nothing is enlarged.
    trunc(x / 2) * 2 makes the size even (yuv420p can't store odd sizes); max(2, ...) keeps it above 0.
    The single quotes protect the commas inside the expressions: a bare comma would end the filter.
    """
    factor = f'min(1,{MAX_SHORT_SIDE}/min(iw,ih))'
    return (
        f"scale=w='max(2,trunc(iw*{factor}/2)*2)':h='max(2,trunc(ih*{factor}/2)*2)'"
    )


def normalize_video(src_path, dst_path, *, has_audio, timeout=NORMALIZE_TIMEOUT_SECONDS):
    """Re-encode src_path into the one format the rest of the app expects, written to dst_path.

    MP4, H.264 + AAC, constant 30 fps, short side <= 1080 px, keyframe every 0.5 s, no metadata.
    `has_audio` is False when the source has no audio track: a silent one is added then.
    """
    arguments = [
        '-nostdin',     # never wait for a key press (there is no terminal in a worker)
        '-y',           # dst_path is a fresh temp file; overwrite instead of asking
        '-i', str(src_path),
    ]
    if not has_audio:
        # A generated silent stereo track, so every stored file has the same stream layout.
        arguments += ['-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate={AUDIO_SAMPLE_RATE}']

    arguments += [
        '-map', '0:v:0',    # only the first video stream (drops cover art, data streams, ...)
        '-map', '0:a:0' if has_audio else '1:a:0',  # only the first audio stream
    ]
    if not has_audio:
        arguments += ['-shortest']  # anullsrc never ends; stop with the video

    arguments += [
        # Order matters: fix the frame rate first, then size. Phone rotation is applied by ffmpeg
        # before -vf (autorotate), so iw / ih in the scale expression are already upright.
        '-vf', f'fps={TARGET_FPS},{_scale_filter()},setsar=1',    # setsar=1: square pixels, no stretched player
        '-c:v', 'libx264',
        '-preset', X264_PRESET,
        '-crf', str(X264_CRF),
        '-pix_fmt', 'yuv420p',      # the pixel format every browser can play
        # Fixed keyframe spacing (a keyframe every 0.5 s, no extra ones at scene cuts):
        # fast seeking and frame stepping in the player.
        '-g', str(KEYFRAME_INTERVAL_FRAMES),
        '-keyint_min', str(KEYFRAME_INTERVAL_FRAMES),
        '-sc_threshold', '0',
        '-c:a', 'aac',
        '-b:a', AUDIO_BITRATE,
        '-ar', str(AUDIO_SAMPLE_RATE),
        '-ac', '2',
        '-map_metadata', '-1',      # phone videos can contain the GPS location: drop all metadata
        '-movflags', '+faststart',  # index at the start of the file: playback starts before it is fully loaded
        str(dst_path),
    ]
    _run_ffmpeg(arguments, timeout=timeout)


def extract_frame(src_path, dst_path, *, at_seconds, timeout=FRAME_TIMEOUT_SECONDS):
    """Write the frame at `at_seconds` of src_path to dst_path as a PNG."""
    _run_ffmpeg(
        [
            '-nostdin', '-y',
            # -ss before -i: seek in the container instead of decoding everything up to that point.
            # Exact enough, because normalized files have a keyframe every 0.5 s.
            '-ss', f'{at_seconds:.3f}',
            '-i', str(src_path),
            '-frames:v', '1',
            '-f', 'image2',
            str(dst_path),
        ],
        timeout=timeout,
    )
    # Seeking past the end is not an ffmpeg error: it just writes nothing.
    if not os.path.isfile(dst_path) or os.path.getsize(dst_path) == 0:
        raise FFmpegError(f'No frame at {at_seconds} s.')
