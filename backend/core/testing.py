"""
Helpers shared by the tests of `core`, `videos` and `dance_attempts`. Not a test module itself
(the name doesn't start with "test", so Django's test discovery skips it).
"""

import subprocess


def make_clip(path, *, width=320, height=240, fps=25, seconds=1.0, audio=True,
              video_codec='libx264', audio_codec='aac', pix_fmt='yuv420p', metadata=None):
    """Write a tiny real video to `path` using ffmpeg's built-in test sources (no files needed).

    The container comes from the extension (.mp4, .mov, .webm). Odd sizes need pix_fmt='yuv444p'. `metadata` is a dict written
    as container tags, e.g. {'title': 'x'}. Keep `seconds` small: the tests run this often.
    """
    command = [
        'ffmpeg', '-nostdin', '-y', '-v', 'error',
        '-f', 'lavfi', '-i', f'testsrc=size={width}x{height}:rate={fps}',
    ]
    if audio:
        command += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100']
    command += ['-t', str(seconds), '-c:v', video_codec, '-pix_fmt', pix_fmt]
    if audio:
        command += ['-c:a', audio_codec]
    for key, value in (metadata or {}).items():
        command += ['-metadata', f'{key}={value}']
    command.append(str(path))
    subprocess.run(command, check=True, capture_output=True)
    return path
