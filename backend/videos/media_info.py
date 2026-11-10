"""Facts read from a video file with ffprobe (part of ffmpeg, installed in the Dockerfile).

No DB, no models: give it a path, get a value back.
"""

import subprocess

FFPROBE_TIMEOUT_SECONDS = 10


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
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=True,             # exit code != 0 -> CalledProcessError
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None