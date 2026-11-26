"""Tests for core/ffmpeg.py. They run the real ffmpeg / ffprobe on tiny generated clips (core/testing.py)."""

import json
import struct
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from PIL import Image

from core.ffmpeg import (
    FFmpegError,
    FFmpegTimeout,
    extract_frame,
    normalize_video,
    probe_video,
    read_duration_seconds,
)
from core.testing import make_clip


def ffprobe_json(path, *arguments):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-print_format', 'json', *arguments, str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def top_level_boxes(path):
    """Names of the MP4 top-level boxes in file order, e.g. ['ftyp', 'moov', 'mdat']."""
    names = []
    with open(path, 'rb') as file:
        while True:
            header = file.read(8)
            if len(header) < 8:
                return names
            size, name = struct.unpack('>I4s', header)
            names.append(name.decode('ascii'))
            if size == 1:                       # 64-bit size follows the name
                size = struct.unpack('>Q', file.read(8))[0]
                file.seek(size - 16, 1)
            elif size == 0:                     # "until the end of the file"
                return names
            else:
                file.seek(size - 8, 1)


class FFmpegTestCase(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def clip(self, name='in.mp4', **options):
        return make_clip(self.dir / name, **options)

    def normalize(self, source, has_audio=True):
        output = self.dir / 'out.mp4'
        normalize_video(source, output, has_audio=has_audio)
        return output


class ProbeTests(FFmpegTestCase):
    def test_probe_with_audio(self):
        info = probe_video(self.clip(width=320, height=240, fps=25, seconds=1))
        self.assertEqual((info.width, info.height), (320, 240))
        self.assertAlmostEqual(info.fps, 25, places=1)
        self.assertAlmostEqual(info.duration_seconds, 1, delta=0.2)
        self.assertEqual(info.video_codec, 'h264')
        self.assertTrue(info.has_audio)

    def test_probe_without_audio(self):
        self.assertFalse(probe_video(self.clip(audio=False)).has_audio)

    def test_garbage_is_none(self):
        path = self.dir / 'garbage.mp4'
        path.write_bytes(b'this is not a video')
        self.assertIsNone(probe_video(path))

    def test_missing_file_is_none(self):
        self.assertIsNone(probe_video(self.dir / 'nope.mp4'))

    def test_audio_only_is_none(self):
        path = self.dir / 'song.m4a'
        subprocess.run(
            ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440',
             '-t', '1', '-c:a', 'aac', str(path)],
            check=True,
        )
        self.assertIsNone(probe_video(path))


class ReadDurationTests(FFmpegTestCase):
    def test_reads_duration(self):
        self.assertAlmostEqual(read_duration_seconds(self.clip(seconds=1)), 1, delta=0.2)

    def test_unreadable_is_none(self):
        path = self.dir / 'garbage.mp4'
        path.write_bytes(b'not a video')
        self.assertIsNone(read_duration_seconds(path))
        self.assertIsNone(read_duration_seconds(self.dir / 'nope.mp4'))


class NormalizeTests(FFmpegTestCase):
    def test_25_fps_becomes_30(self):
        info = probe_video(self.normalize(self.clip(fps=25, seconds=2)))
        self.assertAlmostEqual(info.fps, 30, places=1)
        self.assertAlmostEqual(info.duration_seconds, 2, delta=0.2)

    def test_60_fps_becomes_30(self):
        info = probe_video(self.normalize(self.clip(fps=60, seconds=2)))
        self.assertAlmostEqual(info.fps, 30, places=1)
        self.assertAlmostEqual(info.duration_seconds, 2, delta=0.2)

    def test_landscape_is_scaled_down(self):
        info = probe_video(self.normalize(self.clip(width=2560, height=1440, seconds=1)))
        self.assertEqual((info.width, info.height), (1920, 1080))

    def test_portrait_is_scaled_down(self):
        info = probe_video(self.normalize(self.clip(width=1440, height=2560, seconds=1)))
        self.assertEqual((info.width, info.height), (1080, 1920))

    def test_small_video_is_not_upscaled(self):
        info = probe_video(self.normalize(self.clip(width=640, height=360, seconds=1)))
        self.assertEqual((info.width, info.height), (640, 360))

    def test_odd_size_becomes_even(self):
        info = probe_video(self.normalize(self.clip(width=641, height=361, seconds=1, pix_fmt='yuv444p')))
        self.assertEqual(info.width % 2, 0)
        self.assertEqual(info.height % 2, 0)
        self.assertLessEqual(info.width, 641)
        self.assertLessEqual(info.height, 361)

    def test_webm_becomes_h264_aac_mp4(self):
        source = self.clip('in.webm', video_codec='libvpx', audio_codec='libvorbis', seconds=1)
        output = self.normalize(source)
        streams = ffprobe_json(output, '-show_streams')['streams']
        self.assertEqual({s['codec_name'] for s in streams}, {'h264', 'aac'})
        self.assertIn('mp4', ffprobe_json(output, '-show_format')['format']['format_name'])

    def test_audio_format(self):
        output = self.normalize(self.clip(seconds=1))
        audio = next(s for s in ffprobe_json(output, '-show_streams')['streams'] if s['codec_type'] == 'audio')
        self.assertEqual(audio['sample_rate'], '44100')
        self.assertEqual(audio['channels'], 2)

    def test_no_audio_gets_a_silent_aac_track(self):
        output = self.normalize(self.clip(audio=False, seconds=1), has_audio=False)
        info = probe_video(output)
        self.assertTrue(info.has_audio)
        streams = ffprobe_json(output, '-show_streams')['streams']
        self.assertIn('aac', {s['codec_name'] for s in streams})
        self.assertAlmostEqual(info.duration_seconds, 1, delta=0.2)    # -shortest stopped the silence at the video's end

    def test_keyframe_every_half_second(self):
        output = self.normalize(self.clip(seconds=2))
        frames = ffprobe_json(
            output, '-select_streams', 'v', '-skip_frame', 'nokey', '-show_entries', 'frame=pts_time',
        )['frames']
        times = [float(frame['pts_time']) for frame in frames]
        self.assertGreaterEqual(len(times), 4)
        for earlier, later in zip(times, times[1:]):
            self.assertAlmostEqual(later - earlier, 0.5, delta=0.05)

    def test_faststart_index_comes_first(self):
        boxes = top_level_boxes(self.normalize(self.clip(seconds=1)))
        self.assertLess(boxes.index('moov'), boxes.index('mdat'))

    def test_metadata_is_dropped(self):
        source = self.clip(seconds=1, metadata={'title': 'Secret title', 'location': '+52.2297+021.0122/'})
        self.assertIn('title', ffprobe_json(source, '-show_format')['format']['tags'])   # the input has it
        output = self.normalize(source)
        tags = ffprobe_json(output, '-show_format')['format'].get('tags', {})
        self.assertNotIn('title', tags)
        self.assertNotIn('location', tags)

    def test_garbage_raises_ffmpeg_error(self):
        path = self.dir / 'garbage.mp4'
        path.write_bytes(b'not a video')
        with self.assertRaises(FFmpegError):
            normalize_video(path, self.dir / 'out.mp4', has_audio=True)

    def test_timeout_raises_ffmpeg_timeout(self):
        source = self.clip(seconds=1)
        with self.assertRaises(FFmpegTimeout):
            normalize_video(source, self.dir / 'out.mp4', has_audio=True, timeout=0.001)

    def test_timeout_is_an_ffmpeg_error(self):
        self.assertTrue(issubclass(FFmpegTimeout, FFmpegError))


class ExtractFrameTests(FFmpegTestCase):
    def test_frame_from_the_middle(self):
        source = self.clip(width=320, height=240, seconds=2)
        output = self.dir / 'frame.png'
        extract_frame(source, output, at_seconds=1.0)
        with Image.open(output) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.size, (320, 240))

    def test_after_the_end_raises(self):
        with self.assertRaises(FFmpegError):
            extract_frame(self.clip(seconds=1), self.dir / 'frame.png', at_seconds=60)

    def test_garbage_raises(self):
        path = self.dir / 'garbage.mp4'
        path.write_bytes(b'not a video')
        with self.assertRaises(FFmpegError):
            extract_frame(path, self.dir / 'frame.png', at_seconds=0)
