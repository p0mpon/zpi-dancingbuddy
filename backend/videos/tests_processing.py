"""
Tests for the processing pipeline of videos: normalization, thumbnail, analysis runs, error codes,
automatic retries and reanalyze (docs/api-decisions.md D3.4, D3.5, D3.7, D3.8).

They use real tiny clips made by ffmpeg (core/testing.py). The analysis itself (OpenCV + MediaPipe)
is patched out: it is too slow, and it has its own tests.
"""

import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from core.ffmpeg import FFmpegError, FFmpegTimeout, probe_video
from core.testing import make_clip

from . import services, tasks
from .models import MAX_ANALYSIS_RUNS, AnalysisError, AnalysisStatus, Video
from .serializers import LibraryVideoSerializer, VideoSerializer
from .tasks import normalize_video_file

TEST_MEDIA_ROOT = tempfile.mkdtemp()
FRAMES = [{'frame_id': 0}]      # what the patched run_analysis returns


def clip_upload(name='dance.mp4', **options):
    """A real tiny video as an uploaded file. The container comes from the extension."""
    with tempfile.TemporaryDirectory() as temp_dir:
        content = make_clip(Path(temp_dir) / name, **options).read_bytes()
    return SimpleUploadedFile(name, content, content_type='video/mp4')


def media_path(file_name):
    return Path(settings.MEDIA_ROOT, file_name)


def files_in(folder):
    """Names of all files below MEDIA_ROOT/folder (empty if the folder doesn't exist)."""
    root = media_path(folder)
    return sorted(str(p) for p in root.rglob('*') if p.is_file()) if root.exists() else []


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProcessingTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.dancer = get_user_model().objects.create_user(username='dancer', nickname='dancer', password='pass')
        self.addCleanup(shutil.rmtree, media_path('videos'), True)
        self.addCleanup(shutil.rmtree, media_path('thumbnails'), True)

    def upload(self, file=None, *, analysis=None):
        """Upload through the service and let the (eager) task run, like the API does."""
        patcher = mock.patch('videos.tasks.run_analysis', return_value=FRAMES) if analysis is None else analysis
        with patcher:
            with self.captureOnCommitCallbacks(execute=True):
                video = services.upload_video(owner=self.dancer, title='Salsa', file=file or clip_upload())
        video.refresh_from_db()
        return video

    def raw_video(self, file, **fields):
        """A row with a file but no task run (so it can be set up before the run)."""
        return Video.objects.create(owner=self.dancer, title='Salsa', path_to_resource=file, file_size=1.0, **fields)


class NormalizationTests(ProcessingTestCase):
    def test_upload_is_normalized_and_analysed(self):
        original = None
        with mock.patch('videos.services.start_analysis'):      # catch the original name before the task runs
            with self.captureOnCommitCallbacks(execute=True):
                video = services.upload_video(
                    owner=self.dancer, title='Salsa', file=clip_upload('dance.mov', width=1280, height=720, fps=25),
                )
            original = video.path_to_resource.name
        self.assertTrue(original.endswith('.mov'))

        with mock.patch('videos.tasks.run_analysis', return_value=FRAMES):
            with self.captureOnCommitCallbacks(execute=True):
                normalize_video_file.apply(args=[video.pk])
        video.refresh_from_db()

        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)
        self.assertEqual(video.json_analysis, FRAMES)
        self.assertTrue(video.is_normalized)
        self.assertEqual(video.analysis_runs, 1)
        self.assertIsNone(video.analysis_error_code)

        stored = video.path_to_resource.name
        self.assertTrue(stored.endswith('.mp4'))
        stem = Path(original).stem
        self.assertEqual(stored, f'videos/normalized/{stem}_normalized.mp4')
        self.assertFalse(media_path(original).exists())             # the original is deleted
        info = probe_video(media_path(stored))
        self.assertEqual(info.video_codec, 'h264')
        self.assertAlmostEqual(info.fps, 30, places=1)
        self.assertEqual(video.file_size, media_path(stored).stat().st_size)
        self.assertAlmostEqual(video.duration_seconds, info.duration_seconds, places=2)

    def test_upload_runs_the_whole_chain(self):
        video = self.upload()
        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)
        self.assertTrue(video.is_normalized)
        self.assertEqual(len(files_in('videos')), 1)     # only the normalized file

    def test_webm_upload_works_the_same(self):
        video = self.upload(clip_upload('dance.webm', video_codec='libvpx', audio_codec='libvorbis'))
        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)
        self.assertTrue(video.path_to_resource.name.endswith('.mp4'))
        self.assertEqual(probe_video(video.path_to_resource.path).video_codec, 'h264')

    def test_video_without_audio_is_accepted(self):
        video = self.upload(clip_upload(audio=False))
        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)
        self.assertTrue(probe_video(video.path_to_resource.path).has_audio)

    def test_already_normalized_is_not_normalized_again(self):
        video = self.upload()
        with mock.patch('videos.tasks.normalize_video') as normalize, \
                mock.patch('videos.tasks.run_analysis', return_value=FRAMES):
            normalize_video_file.apply(args=[video.pk])
        normalize.assert_not_called()
        video.refresh_from_db()
        self.assertEqual(video.analysis_runs, 2)
        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)

    def test_delete_during_normalization_leaves_no_file(self):
        video = self.raw_video(clip_upload())

        def delete_meanwhile(src, dst, *, has_audio):
            shutil.copy(src, dst)
            Video.objects.filter(pk=video.pk).delete()

        with mock.patch('videos.tasks.normalize_video', side_effect=delete_meanwhile), \
                mock.patch('videos.tasks.run_analysis') as run_analysis:
            with self.captureOnCommitCallbacks(execute=True):
                normalize_video_file.apply(args=[video.pk])
        run_analysis.assert_not_called()
        self.assertEqual(files_in('videos'), [])

    def test_delete_during_the_swap_removes_the_new_file(self):
        video = self.raw_video(clip_upload())
        new_file = Path(tempfile.mkdtemp()) / 'normalized.mp4'
        self.addCleanup(shutil.rmtree, new_file.parent, True)
        shutil.copy(video.path_to_resource.path, new_file)

        # read_duration_seconds runs after the new file is saved, right before the UPDATE: delete the row there.
        def delete_row(path):
            Video.objects.filter(pk=video.pk).delete()
            return 1.0

        with mock.patch('videos.services.read_duration_seconds', side_effect=delete_row):
            with self.captureOnCommitCallbacks(execute=True):
                result = services.update_video_file(
                    video_id=video.pk, new_path=new_file,
                )
        self.assertIsNone(result)
        self.assertEqual(files_in('videos'), [])


class ThumbnailTests(ProcessingTestCase):
    def test_thumbnail_is_made_from_the_normalized_video(self):
        video = self.upload(clip_upload(width=1920, height=1080, seconds=1))
        self.assertTrue(video.thumbnail)
        self.assertTrue(video.thumbnail.name.startswith('thumbnails/videos/'))
        with Image.open(video.thumbnail.path) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertEqual(image.size, (720, 405))

    def test_vertical_video_thumbnail(self):
        video = self.upload(clip_upload(width=1080, height=1920, seconds=1))
        with Image.open(video.thumbnail.path) as image:
            self.assertEqual(image.size, (405, 720))

    def test_failure_does_not_fail_the_analysis(self):
        with mock.patch('videos.tasks.extract_frame', side_effect=FFmpegError('boom')):
            with self.assertLogs('videos.tasks', level='WARNING'):
                video = self.upload()
        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)
        self.assertFalse(video.thumbnail)

    def test_existing_thumbnail_is_kept(self):
        video = self.upload()
        first = video.thumbnail.name
        with mock.patch('videos.tasks.extract_frame') as extract_frame, \
                mock.patch('videos.tasks.run_analysis', return_value=FRAMES):
            normalize_video_file.apply(args=[video.pk])
        extract_frame.assert_not_called()
        video.refresh_from_db()
        self.assertEqual(video.thumbnail.name, first)


class ErrorCodeTests(ProcessingTestCase):
    def run_failing(self, video, **patches):
        """Run the task with the given patches (name -> mock kwargs) and return the video afterwards."""
        patches.setdefault('run_analysis', mock.Mock(return_value=FRAMES))
        with self.assertLogs('videos.tasks'):
            with self.captureOnCommitCallbacks(execute=True):
                with mock.patch.multiple('videos.tasks', **patches):
                    normalize_video_file.apply(args=[video.pk])
        video.refresh_from_db()
        return video

    def assertFailed(self, video, code, runs):
        self.assertEqual(video.analysis_status, AnalysisStatus.FAILED)
        self.assertEqual(video.analysis_error_code, code)
        self.assertEqual(video.analysis_runs, runs)

    def test_missing_file(self):
        video = self.raw_video(clip_upload())
        media_path(video.path_to_resource.name).unlink()
        self.assertFailed(self.run_failing(video), AnalysisError.FILE_MISSING, runs=1)

    def test_unreadable_file(self):
        video = self.raw_video(SimpleUploadedFile('bad.mp4', b'not a video'))
        self.assertFailed(self.run_failing(video), AnalysisError.UNREADABLE, runs=1)

    def test_ffmpeg_error_is_not_retried(self):
        video = self.raw_video(clip_upload())
        failing = mock.Mock(side_effect=FFmpegError('broken stream'))
        self.assertFailed(self.run_failing(video, normalize_video=failing), AnalysisError.NORMALIZATION_FAILED, runs=1)
        self.assertEqual(failing.call_count, 1)

    def test_timeout_is_retried_until_the_runs_are_used(self):
        video = self.raw_video(clip_upload())
        failing = mock.Mock(side_effect=FFmpegTimeout('too slow'))
        # Eager mode runs the queued retries at once, so the whole chain happens inside this call.
        video = self.run_failing(video, normalize_video=failing)
        self.assertFailed(video, AnalysisError.NORMALIZATION_TIMEOUT, runs=MAX_ANALYSIS_RUNS)
        self.assertEqual(failing.call_count, MAX_ANALYSIS_RUNS)

    def test_analysis_error_is_not_retried(self):
        video = self.raw_video(clip_upload(), is_normalized=True)
        failing = mock.Mock(side_effect=RuntimeError('boom'))
        self.assertFailed(self.run_failing(video, run_analysis=failing), AnalysisError.ANALYSIS_FAILED, runs=1)

    def test_unexpected_error_is_unknown_and_retried(self):
        video = self.raw_video(clip_upload())
        failing = mock.Mock(side_effect=RuntimeError('who knows'))
        video = self.run_failing(video, probe_video=failing)
        self.assertFailed(video, AnalysisError.UNKNOWN, runs=MAX_ANALYSIS_RUNS)

    def test_retry_delays_are_short(self):
        for tries_done, delay in enumerate([10, 30, 60, 120]):
            with self.subTest(tries_done=tries_done):
                video = self.raw_video(clip_upload())
                with mock.patch('videos.tasks.normalize_video', side_effect=FFmpegTimeout('slow')), \
                        mock.patch.object(normalize_video_file, 'retry', side_effect=RuntimeError('stop')) as retry:
                    normalize_video_file.apply(args=[video.pk], retries=tries_done)
                self.assertEqual(retry.call_args.kwargs['countdown'], delay)

    def test_tries_used_up_fails_with_the_timeout_code(self):
        video = self.raw_video(clip_upload())
        with mock.patch('videos.tasks.normalize_video', side_effect=FFmpegTimeout('slow')), \
                self.assertLogs('videos.tasks'):
            normalize_video_file.apply(args=[video.pk], retries=4)
        video.refresh_from_db()
        self.assertEqual(video.analysis_status, AnalysisStatus.FAILED)
        self.assertEqual(video.analysis_error_code, AnalysisError.NORMALIZATION_TIMEOUT)

    def test_run_clears_the_old_error_code(self):
        video = self.raw_video(
            clip_upload(), is_normalized=True, analysis_status=AnalysisStatus.FAILED,
            analysis_error_code=AnalysisError.UNKNOWN, analysis_runs=1,
        )
        with mock.patch('videos.tasks.run_analysis', return_value=FRAMES):
            normalize_video_file.apply(args=[video.pk])
        video.refresh_from_db()
        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)
        self.assertIsNone(video.analysis_error_code)


class ConstraintTests(ProcessingTestCase):
    def test_error_code_needs_a_failed_status(self):
        video = self.raw_video(SimpleUploadedFile('a.mp4', b'x'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Video.objects.filter(pk=video.pk).update(analysis_error_code=AnalysisError.UNKNOWN)

    def test_unknown_code_is_refused(self):
        video = self.raw_video(SimpleUploadedFile('a.mp4', b'x'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Video.objects.filter(pk=video.pk).update(analysis_status=AnalysisStatus.FAILED, analysis_error_code=7)

    def test_failed_with_a_code_is_fine(self):
        video = self.raw_video(SimpleUploadedFile('a.mp4', b'x'))
        Video.objects.filter(pk=video.pk).update(analysis_status=AnalysisStatus.FAILED, analysis_error_code=3)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ReanalyzeApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.dancer = User.objects.create_user(username='dancer', nickname='dancer', password='pass')
        self.other = User.objects.create_user(username='other', nickname='other', password='pass')
        self.client.force_authenticate(self.dancer)

    def video(self, owner=None, **fields):
        return Video.objects.create(
            owner=owner or self.dancer, title='Salsa', path_to_resource='videos/x.mp4', file_size=1.0, **fields,
        )

    def failed_video(self, **fields):
        return self.video(analysis_status=AnalysisStatus.FAILED, analysis_error_code=AnalysisError.UNKNOWN,
                          analysis_runs=2, **fields)

    def post(self, video):
        return self.client.post(f'/api/videos/{video.pk}/reanalyze/')

    def test_failed_video_goes_back_to_pending(self):
        video = self.failed_video()
        with self.captureOnCommitCallbacks() as callbacks:      # collected, not run: no task here
            response = self.post(video)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['analysis_status'], 'pending')
        self.assertIsNone(response.data['analysis_error_code'])
        self.assertEqual(len(callbacks), 1)
        video.refresh_from_db()
        self.assertEqual(video.analysis_status, AnalysisStatus.PENDING)
        self.assertEqual(video.analysis_runs, 2)    # counted when the task runs, not here

    def test_queues_the_task_after_commit(self):
        video = self.failed_video()
        with mock.patch('videos.services.start_analysis') as start_analysis:
            with self.captureOnCommitCallbacks(execute=True):
                self.post(video)
        start_analysis.assert_called_once()

    def test_not_failed_is_409(self):
        for state in [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING, AnalysisStatus.DONE]:
            with self.subTest(state=state):
                self.assertEqual(self.post(self.video(analysis_status=state)).status_code, status.HTTP_409_CONFLICT)

    def test_no_runs_left_is_409(self):
        video = self.failed_video()
        Video.objects.filter(pk=video.pk).update(analysis_runs=MAX_ANALYSIS_RUNS)
        response = self.post(video)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        video.refresh_from_db()
        self.assertEqual(video.analysis_status, AnalysisStatus.FAILED)

    def test_someone_elses_video_is_404(self):
        video = self.failed_video()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.post(video).status_code, status.HTTP_404_NOT_FOUND)

    def test_login_required(self):
        video = self.failed_video()
        self.client.force_authenticate(None)
        self.assertEqual(self.post(video).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_thumbnail_route_is_gone(self):
        video = self.video()
        self.assertEqual(self.client.get(f'/api/videos/{video.pk}/thumbnail/').status_code, status.HTTP_404_NOT_FOUND)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DtoTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='dancer', nickname='dancer', password='pass')
        self.video = Video.objects.create(
            owner=user, title='Salsa', path_to_resource='videos/x.mp4', file_size=1.0,
            analysis_status=AnalysisStatus.FAILED, analysis_error_code=AnalysisError.UNREADABLE,
            analysis_runs=3, is_normalized=True,
        )

    def test_my_video_has_thumbnail_url_and_error_code_only(self):
        data = VideoSerializer(self.video).data
        self.assertIn('thumbnail_url', data)
        self.assertIsNone(data['thumbnail_url'])
        self.assertEqual(data['analysis_error_code'], 2)
        self.assertNotIn('analysis_runs', data)
        self.assertNotIn('is_normalized', data)

    def test_library_video_shows_no_processing_fields(self):
        for name in ['analysis_error_code', 'analysis_runs', 'is_normalized']:
            self.assertNotIn(name, LibraryVideoSerializer.Meta.fields)
