import math
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

from .models import AnalysisStatus, Video
from .tasks import analyse_video

# Uploaded files go to a throw-away folder, removed after the test class runs.
TEST_MEDIA_ROOT = tempfile.mkdtemp()

JOINTS = ['left_knee', 'right_knee', 'left_hip', 'right_hip']


def fake_frames(seconds, fps=30):
    """A json_analysis value: a list of Frame dicts (zpi_app/zpi_app/video_frame_model.py)."""
    return [
        {
            'frame_id': frame_id,
            'timestamp': round(frame_id / fps, 4),
            'joints': {
                name: {'angle': round(90 + 45 * math.sin(frame_id / fps * 2 + i), 2), 'visibility': 0.95}
                for i, name in enumerate(JOINTS)
            },
        }
        for frame_id in range(seconds * fps)
    ]


def video_file(name='dance.mp4', content=b'fake video bytes'):
    return SimpleUploadedFile(name, content, content_type='video/mp4')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class VideoApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.dancer = User.objects.create_user(username='dancer', password='pass')
        self.other = User.objects.create_user(username='other', password='pass')
        self.analysed = Video.objects.create(
            owner=self.dancer, title='Salsa basic step', path_to_resource=video_file('salsa.mp4'),
            file_size=16.0, analysis_status=AnalysisStatus.DONE, json_analysis=fake_frames(seconds=10),
        )
        self.pending = Video.objects.create(
            owner=self.dancer, title='Bachata turn', path_to_resource=video_file('bachata.mp4'), file_size=16.0,
        )
        self.others_video = Video.objects.create(
            owner=self.other, title='Not yours', path_to_resource=video_file('tango.mp4'), file_size=16.0,
        )
        self.client.force_authenticate(self.dancer)

    def url(self, video, suffix=''):
        return f'/api/videos/{video.pk}/{suffix}'

    def upload(self, **data):
        return self.client.post('/api/videos/', data, format='multipart')

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/videos/').status_code, status.HTTP_403_FORBIDDEN)

    def test_put_not_allowed(self):
        response = self.client.put(self.url(self.analysed), {'title': 'X'})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ==== LIST / RETRIEVE

    def test_list_only_own_videos_newest_first(self):
        response = self.client.get('/api/videos/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([video['id'] for video in response.data], [self.pending.pk, self.analysed.pk])

    def test_list_fields(self):
        response = self.client.get('/api/videos/')
        self.assertEqual(
            set(response.data[0]),
            {'id', 'title', 'description', 'file_size', 'analysis_status', 'created_at'},
        )

    def test_retrieve_own(self):
        response = self.client.get(self.url(self.analysed))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Salsa basic step')
        self.assertEqual(response.data['analysis_status'], 'done')

    def test_retrieve_other_users_video_is_404(self):
        self.assertEqual(self.client.get(self.url(self.others_video)).status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_missing_is_404(self):
        self.assertEqual(self.client.get('/api/videos/999999/').status_code, status.HTTP_404_NOT_FOUND)

    # ==== UPLOAD

    def test_upload_creates_row_and_file(self):
        response = self.upload(title='New', file=video_file())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New')
        self.assertEqual(response.data['file_size'], len(b'fake video bytes'))
        self.assertEqual(response.data['analysis_status'], 'pending')

        video = Video.objects.get(pk=response.data['id'])
        self.assertEqual(video.owner, self.dancer)
        self.assertEqual(video.file_size, len(b'fake video bytes'))
        self.assertEqual(video.analysis_status, AnalysisStatus.PENDING)
        self.assertTrue(video.path_to_resource.name.startswith(f'videos/user_{self.dancer.pk}/'))
        self.assertTrue(Path(settings.MEDIA_ROOT, video.path_to_resource.name).is_file())

    def test_upload_queues_analysis_after_commit(self):
        with mock.patch('videos.services.start_analysis') as start_analysis:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.upload(title='New', file=video_file())
        video = Video.objects.get(pk=response.data['id'])
        start_analysis.assert_called_once_with(video=video)

    def test_upload_ignores_owner_in_form(self):
        response = self.upload(title='New', file=video_file(), owner=self.other.pk)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Video.objects.get(pk=response.data['id']).owner, self.dancer)

    def test_upload_with_and_without_description(self):
        with_description = self.upload(title='A', file=video_file(), description='Warm-up')
        without_description = self.upload(title='B', file=video_file())
        self.assertEqual(with_description.data['description'], 'Warm-up')
        self.assertEqual(without_description.data['description'], '')

    def test_upload_rejects_non_video(self):
        response = self.upload(title='New', file=SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)

    def test_upload_rejects_too_large_file(self):
        # Shrink the limit to 4 bytes instead of building a 500 MB file.
        with mock.patch('videos.serializers.MAX_VIDEO_SIZE_BYTES', 4):
            response = self.upload(title='Too big', file=video_file(content=b'12345'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)
        self.assertFalse(Video.objects.filter(title='Too big').exists())

    def test_upload_requires_title(self):
        response = self.upload(file=video_file())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)

    # ==== RENAME / DELETE

    def test_rename_saves_title_and_description(self):
        old_updated_at = self.analysed.updated_at
        response = self.client.patch(self.url(self.analysed), {'title': 'Renamed', 'description': 'Slow'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Renamed')
        self.assertEqual(response.data['description'], 'Slow')

        self.analysed.refresh_from_db()
        self.assertEqual(self.analysed.title, 'Renamed')
        self.assertEqual(self.analysed.description, 'Slow')
        self.assertGreater(self.analysed.updated_at, old_updated_at)

    def test_rename_ignores_read_only_fields(self):
        response = self.client.patch(
            self.url(self.pending), {'title': 'Renamed', 'file_size': 1, 'analysis_status': 'done'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.file_size, 16.0)
        self.assertEqual(self.pending.analysis_status, AnalysisStatus.PENDING)

    def test_rename_empty_body_changes_nothing(self):
        response = self.client.patch(self.url(self.analysed), {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Salsa basic step')

    def test_rename_does_not_rerun_analysis(self):
        with mock.patch('videos.services.start_analysis') as start_analysis:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.patch(self.url(self.analysed), {'title': 'Renamed'})
        start_analysis.assert_not_called()
        self.analysed.refresh_from_db()
        self.assertEqual(self.analysed.analysis_status, AnalysisStatus.DONE)

    def test_replace_file_resets_and_reruns_analysis(self):
        old_path = Path(settings.MEDIA_ROOT, self.analysed.path_to_resource.name)
        with mock.patch('videos.services.start_analysis') as start_analysis:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.patch(
                    self.url(self.analysed), {'file': video_file('new.webm', b'new bytes!')}, format='multipart',
                )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('file', response.data)  # write-only
        self.assertEqual(response.data['analysis_status'], 'pending')

        self.analysed.refresh_from_db()
        self.assertEqual(self.analysed.file_size, len(b'new bytes!'))
        self.assertIsNone(self.analysed.json_analysis)
        self.assertTrue(self.analysed.path_to_resource.name.endswith('.webm'))
        self.assertTrue(Path(settings.MEDIA_ROOT, self.analysed.path_to_resource.name).is_file())
        self.assertFalse(old_path.exists())
        start_analysis.assert_called_once_with(video=mock.ANY)

    def test_replace_file_rejects_non_video(self):
        response = self.client.patch(
            self.url(self.analysed),
            {'file': SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)
        self.analysed.refresh_from_db()
        self.assertEqual(self.analysed.analysis_status, AnalysisStatus.DONE)

    def test_rename_other_users_video_is_404(self):
        response = self.client.patch(self.url(self.others_video), {'title': 'Mine now'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.others_video.refresh_from_db()
        self.assertEqual(self.others_video.title, 'Not yours')

    def test_delete_removes_row_and_file(self):
        file_path = Path(settings.MEDIA_ROOT, self.analysed.path_to_resource.name)
        self.assertTrue(file_path.is_file())
        # TestCase never commits, so on_commit callbacks (the file delete) would not run otherwise.
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.url(self.analysed))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Video.objects.filter(pk=self.analysed.pk).exists())
        self.assertFalse(file_path.exists())

    def test_delete_other_users_video_is_404(self):
        file_path = Path(settings.MEDIA_ROOT, self.others_video.path_to_resource.name)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.url(self.others_video))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Video.objects.filter(pk=self.others_video.pk).exists())
        self.assertTrue(file_path.is_file())

    # ==== OTHER ACTIONS

    def test_stream_and_thumbnail_not_implemented(self):
        for suffix in ('stream/', 'thumbnail/'):
            response = self.client.get(self.url(self.analysed, suffix))
            self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)

    # ==== ANALYSIS

    def test_analysis_returns_whole_json(self):
        response = self.client.get(self.url(self.analysed, 'analysis/'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), self.analysed.json_analysis)

    def test_analysis_needs_analysed_video(self):
        response = self.client.get(self.url(self.pending, 'analysis/'))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_analysis_other_users_video_is_404(self):
        response = self.client.get(self.url(self.others_video, 'analysis/'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_analysis_cannot_be_started_by_hand(self):
        response = self.client.post(self.url(self.analysed, 'analysis/'))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class AnalyseVideoTaskTests(TestCase):
    """The Celery task, called directly (in tests CELERY_TASK_ALWAYS_EAGER runs .delay() inline too)."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.dancer = get_user_model().objects.create_user(username='dancer', password='pass')
        self.video = Video.objects.create(
            owner=self.dancer, title='Salsa', path_to_resource=video_file(), file_size=16.0,
        )

    def test_success_saves_json_and_done(self):
        frames = fake_frames(seconds=1)
        with mock.patch('videos.tasks.run_analysis', return_value=frames) as run_analysis:
            analyse_video(self.video.pk)
        run_analysis.assert_called_once_with(self.video.path_to_resource.path)
        self.video.refresh_from_db()
        self.assertEqual(self.video.analysis_status, AnalysisStatus.DONE)
        self.assertEqual(self.video.json_analysis, frames)

    def test_status_is_processing_while_running(self):
        def check_status(file_path):
            self.assertEqual(Video.objects.get(pk=self.video.pk).analysis_status, AnalysisStatus.PROCESSING)
            return []

        with mock.patch('videos.tasks.run_analysis', side_effect=check_status):
            analyse_video(self.video.pk)

    def test_error_marks_failed(self):
        with mock.patch('videos.tasks.run_analysis', side_effect=RuntimeError('boom')):
            with self.assertLogs('videos.tasks', level='ERROR'):
                analyse_video(self.video.pk)
        self.video.refresh_from_db()
        self.assertEqual(self.video.analysis_status, AnalysisStatus.FAILED)
        self.assertIsNone(self.video.json_analysis)

    def test_not_connected_yet_marks_failed(self):
        with self.assertLogs('videos.tasks', level='ERROR'):
            analyse_video(self.video.pk)
        self.video.refresh_from_db()
        self.assertEqual(self.video.analysis_status, AnalysisStatus.FAILED)

    def test_result_dropped_if_file_replaced_meanwhile(self):
        def replace_file(file_path):
            # What a PATCH with a new file does while the worker is busy.
            Video.objects.filter(pk=self.video.pk).update(
                path_to_resource='videos/new.mp4', analysis_status=AnalysisStatus.PENDING,
            )
            return fake_frames(seconds=1)

        with mock.patch('videos.tasks.run_analysis', side_effect=replace_file):
            analyse_video(self.video.pk)
        self.video.refresh_from_db()
        self.assertEqual(self.video.analysis_status, AnalysisStatus.PENDING)
        self.assertIsNone(self.video.json_analysis)

    def test_deleted_video_is_skipped(self):
        with mock.patch('videos.tasks.run_analysis') as run_analysis:
            analyse_video(999999)
        run_analysis.assert_not_called()

    def test_upload_runs_the_task(self):
        """Whole chain: POST -> on_commit -> start_analysis -> analyse_video.delay (eager) -> done."""
        self.client.force_login(self.dancer)
        with mock.patch('videos.tasks.run_analysis', return_value=fake_frames(seconds=1)):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/videos/', {'title': 'New', 'file': video_file()})
        video = Video.objects.get(pk=response.json()['id'])
        self.assertEqual(video.analysis_status, AnalysisStatus.DONE)
