"""
Tests for the processing of dance attempts: scoring (analyse_attempt) and normalizing the recording
(normalize_attempt_recording) are two independent tasks. Real tiny clips come from ffmpeg
(core/testing.py); the scoring itself is patched.
"""

import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.ffmpeg import FFmpegError, FFmpegTimeout, probe_video
from core.testing import make_clip
from dance_attempts import services
from dance_attempts.models import DanceAttempt
from dance_attempts.serializers import DanceAttemptDetailSerializer, DanceAttemptSerializer
from dance_attempts.tasks import analyse_attempt, normalize_attempt_recording
from videos.models import MAX_ANALYSIS_RUNS, AnalysisError, AnalysisStatus, Video

TEST_MEDIA_ROOT = tempfile.mkdtemp()
SCORE = ([{'score': 0.9}], 90)


def clip_upload(name='recording.mp4', **options):
    with tempfile.TemporaryDirectory() as temp_dir:
        content = make_clip(Path(temp_dir) / name, **options).read_bytes()
    return SimpleUploadedFile(name, content, content_type='video/mp4')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class AttemptProcessingTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='dancer', nickname='dancer', password='pass')
        self.folder = Path(settings.MEDIA_ROOT, 'dance_attempt')
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.video = Video.objects.create(
            owner=self.user, title='Fancy', path_to_resource='videos/fancy.mp4', file_size=1.0,
            analysis_status=AnalysisStatus.DONE, json_analysis=[{'ref': 1}],
        )

    def attempt(self, recording=None, **fields):
        return DanceAttempt.objects.create(
            user=self.user, reference_video=self.video, reference_title='Fancy',
            recording=recording, json_analysis=[{'mp': 1}], **fields,
        )

    def files(self):
        return [p for p in self.folder.rglob('*') if p.is_file()] if self.folder.exists() else []

    def normalize(self, attempt):
        """Run the normalization task like the worker does (eagerly: retries run at once)."""
        with self.captureOnCommitCallbacks(execute=True):
            normalize_attempt_recording.apply(args=[attempt.pk])
        attempt.refresh_from_db()
        return attempt


class ScoringTests(AttemptProcessingTestCase):
    def test_score_is_saved(self):
        attempt = self.attempt()
        with mock.patch('dance_attempts.tasks.run_score_analysis', return_value=SCORE) as score:
            analyse_attempt(attempt.pk)
        score.assert_called_once_with([{'ref': 1}], [{'mp': 1}])
        attempt.refresh_from_db()
        self.assertEqual((attempt.status, attempt.score, attempt.analysis_runs), (AnalysisStatus.DONE, 90, 1))

    def test_score_does_not_need_a_readable_recording(self):
        attempt = self.attempt(SimpleUploadedFile('bad.mp4', b'not a video'))
        with mock.patch('dance_attempts.tasks.run_score_analysis', return_value=SCORE):
            analyse_attempt(attempt.pk)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.DONE)
        self.assertFalse(attempt.is_normalized)

    def test_scoring_error_is_code_5(self):
        attempt = self.attempt()
        with mock.patch('dance_attempts.tasks.run_score_analysis', side_effect=ValueError('bad')):
            with self.assertLogs('dance_attempts.tasks'):
                analyse_attempt(attempt.pk)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.FAILED)
        self.assertEqual(attempt.analysis_error_code, AnalysisError.ANALYSIS_FAILED)
        self.assertEqual(attempt.analysis_runs, 1)

    def test_deleted_reference_video_is_code_5(self):
        attempt = self.attempt()
        self.video.delete()
        with self.assertLogs('dance_attempts.tasks'):
            analyse_attempt(attempt.pk)
        attempt.refresh_from_db()
        self.assertEqual(attempt.analysis_error_code, AnalysisError.ANALYSIS_FAILED)

    def test_run_clears_the_old_error_code(self):
        attempt = self.attempt(
            status=AnalysisStatus.FAILED, analysis_error_code=AnalysisError.ANALYSIS_FAILED, analysis_runs=1,
        )
        with mock.patch('dance_attempts.tasks.run_score_analysis', return_value=SCORE):
            analyse_attempt(attempt.pk)
        attempt.refresh_from_db()
        self.assertIsNone(attempt.analysis_error_code)
        self.assertEqual(attempt.analysis_runs, 2)


class NormalizationTests(AttemptProcessingTestCase):
    def test_recording_is_normalized(self):
        attempt = self.attempt(clip_upload('rec.mov', fps=25))
        original = Path(attempt.recording.path)
        attempt = self.normalize(attempt)

        self.assertTrue(attempt.is_normalized)
        stem = original.stem
        self.assertEqual(attempt.recording.name, f'dance_attempt/normalized/{stem}_normalized.mp4')
        self.assertFalse(original.exists())         # the raw file is deleted
        info = probe_video(attempt.recording.path)
        self.assertEqual(info.video_codec, 'h264')
        self.assertAlmostEqual(info.fps, 30, places=1)
        self.assertEqual(self.files(), [Path(attempt.recording.path)])      # only the normalized file is left

    def test_skipped_without_recording_or_when_already_normalized(self):
        for attempt in [self.attempt(), self.attempt(clip_upload(), is_normalized=True)]:
            with mock.patch('dance_attempts.tasks.normalize_video') as encode:
                self.normalize(attempt)
            encode.assert_not_called()

    def test_ffmpeg_error_is_logged_and_not_retried(self):
        attempt = self.attempt(clip_upload())
        failing = mock.Mock(side_effect=FFmpegError('broken'))
        with mock.patch('dance_attempts.tasks.normalize_video', failing), self.assertLogs('dance_attempts.tasks'):
            attempt = self.normalize(attempt)
        self.assertEqual(failing.call_count, 1)
        self.assertFalse(attempt.is_normalized)

    def test_unreadable_recording_is_not_retried(self):
        attempt = self.attempt(SimpleUploadedFile('bad.mp4', b'not a video'))
        with mock.patch('dance_attempts.tasks.normalize_video') as encode, self.assertLogs('dance_attempts.tasks'):
            attempt = self.normalize(attempt)
        encode.assert_not_called()
        self.assertFalse(attempt.is_normalized)

    def test_timeout_is_retried_up_to_5_runs(self):
        attempt = self.attempt(clip_upload())
        failing = mock.Mock(side_effect=FFmpegTimeout('slow'))
        with mock.patch('dance_attempts.tasks.normalize_video', failing):
            attempt = self.normalize(attempt)
        self.assertEqual(failing.call_count, 5)
        self.assertFalse(attempt.is_normalized)

    def test_unexpected_error_is_retried(self):
        attempt = self.attempt(clip_upload())
        failing = mock.Mock(side_effect=RuntimeError('who knows'))
        with mock.patch('dance_attempts.tasks.normalize_video', failing), self.assertLogs('dance_attempts.tasks'):
            self.normalize(attempt)
        self.assertEqual(failing.call_count, 5)

    def test_delete_during_normalization_leaves_no_file(self):
        attempt = self.attempt(clip_upload())

        def delete_meanwhile(src, dst, *, has_audio):
            shutil.copy(src, dst)
            DanceAttempt.objects.filter(pk=attempt.pk).delete()

        with mock.patch('dance_attempts.tasks.normalize_video', side_effect=delete_meanwhile):
            with self.captureOnCommitCallbacks(execute=True):
                normalize_attempt_recording.apply(args=[attempt.pk])
        self.assertEqual(self.files(), [])

    def test_update_recording_of_a_deleted_attempt_keeps_no_file(self):
        attempt = self.attempt(clip_upload())
        new_path = Path(tempfile.mkdtemp()) / 'normalized.mp4'
        self.addCleanup(shutil.rmtree, new_path.parent, True)
        shutil.copy(attempt.recording.path, new_path)

        with self.captureOnCommitCallbacks(execute=True):
            attempt.delete()    # the signal removes the raw file after the commit
            result = services.update_attempt_recording(attempt_id=attempt.pk, new_path=new_path)
        self.assertIsNone(result)
        self.assertEqual(self.files(), [])


class CreateAttemptTests(AttemptProcessingTestCase):
    def test_both_tasks_are_queued_after_commit(self):
        with mock.patch('dance_attempts.services.start_attempt_analysis') as score, \
                mock.patch('dance_attempts.services.start_attempt_normalization') as normalize:
            with self.captureOnCommitCallbacks() as callbacks:
                attempt = services.create_attempt(
                    user=self.user, reference_video_id=self.video.pk, mediapipe_data=[{'mp': 1}],
                    recording=clip_upload(),
                )
            score.assert_not_called()
            normalize.assert_not_called()
            for callback in callbacks:
                callback()
        score.assert_called_once_with(attempt=attempt)
        normalize.assert_called_once_with(attempt=attempt)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ReanalyzeTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='dancer', nickname='dancer', password='pass')
        self.video = Video.objects.create(
            owner=self.user, title='Fancy', path_to_resource='videos/fancy.mp4', file_size=1.0,
            analysis_status=AnalysisStatus.DONE, json_analysis=[{'ref': 1}],
        )
        self.client.force_authenticate(self.user)

    def failed_attempt(self, runs=2):
        return DanceAttempt.objects.create(
            user=self.user, reference_video=self.video, reference_title='Fancy',
            status=AnalysisStatus.FAILED, analysis_error_code=AnalysisError.ANALYSIS_FAILED, analysis_runs=runs,
        )

    def post(self, attempt):
        return self.client.post(f'/api/dance-attempts/{attempt.pk}/reanalyze/')

    def test_reset_clears_the_error_code_and_keeps_the_runs(self):
        attempt = self.failed_attempt()
        with self.captureOnCommitCallbacks():       # collected, not run: no task here
            response = self.post(attempt)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIsNone(response.data['analysis_error_code'])
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.PENDING)
        self.assertIsNone(attempt.analysis_error_code)
        self.assertEqual(attempt.analysis_runs, 2)

    def test_no_runs_left_is_409(self):
        attempt = self.failed_attempt(runs=MAX_ANALYSIS_RUNS)
        self.assertEqual(self.post(attempt).status_code, status.HTTP_409_CONFLICT)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.FAILED)

    def test_dto_has_the_error_code_only(self):
        attempt = self.failed_attempt()
        for serializer in (DanceAttemptSerializer, DanceAttemptDetailSerializer):
            with self.subTest(serializer=serializer.__name__):
                data = serializer(attempt).data
                self.assertEqual(data['analysis_error_code'], 5)
                self.assertEqual(data['reference_video_id'], self.video.pk)
                self.assertNotIn('reference_video_url', data)
                self.assertNotIn('analysis_runs', data)
                self.assertNotIn('is_normalized', data)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class StreamTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='dancer', nickname='dancer', password='pass')
        self.other = User.objects.create_user(username='other', nickname='other', password='pass')
        self.addCleanup(shutil.rmtree, Path(settings.MEDIA_ROOT, 'dance_attempt'), True)
        self.attempt = DanceAttempt.objects.create(
            user=self.user, reference_title='Fancy', recording=SimpleUploadedFile('r.mp4', b'0123456789'),
        )
        self.client.force_authenticate(self.user)

    def url(self, attempt=None):
        return f'/api/dance-attempts/{(attempt or self.attempt).pk}/stream/'

    def test_owner_gets_the_file_and_can_seek(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b''.join(response.streaming_content), b'0123456789')
        partial = self.client.get(self.url(), HTTP_RANGE='bytes=2-4')
        self.assertEqual(partial.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(b''.join(partial.streaming_content), b'234')

    def test_someone_elses_recording_is_404(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_404_NOT_FOUND)

    def test_login_required(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_attempt_without_recording_is_404(self):
        attempt = DanceAttempt.objects.create(user=self.user, reference_title='Fancy')
        self.assertEqual(self.client.get(self.url(attempt)).status_code, status.HTTP_404_NOT_FOUND)

    def test_recording_url_points_at_the_stream_endpoint(self):
        data = self.client.get(f'/api/dance-attempts/{self.attempt.pk}/').json()
        self.assertTrue(data['recording_url'].endswith(self.url()))
