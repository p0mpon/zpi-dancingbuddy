import math
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dance_attempts.models import DanceAttempt

from .models import AnalysisStatus, Difficulty, Video, Visibility
from core.streaming import RangeNotSatisfiable, parse_range_header
from .tasks import analyse_video

# Uploaded files go to a throw-away folder, removed after the test class runs.
TEST_MEDIA_ROOT = tempfile.mkdtemp()

JOINTS = ['left_knee', 'right_knee', 'left_hip', 'right_hip']


def fake_frames(seconds, fps=30):
    """A json_analysis value: a list of Frame dicts (video_analysis/video_frame_model.py)."""
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
        self.dancer = User.objects.create_user(username='dancer', nickname='dancer', password='pass')
        self.other = User.objects.create_user(username='other', nickname='other', password='pass')
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

    def others_public_video(self):
        """A published video of the other user, with a real file (for stream / analysis)."""
        return Video.objects.create(
            owner=self.other, title='Public tango', path_to_resource=video_file('public.mp4'), file_size=16.0,
            analysis_status=AnalysisStatus.DONE, json_analysis=fake_frames(seconds=1),
            difficulty=Difficulty.BEGINNER, visibility=Visibility.PUBLIC, published_at=timezone.now(),
        )

    def test_requires_login(self):
        self.client.force_authenticate(None)
        # 401, not DRF's default 403: accounts.authentication.SessionAuthentication (D7.5).
        self.assertEqual(self.client.get('/api/videos/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_not_allowed(self):
        response = self.client.put(self.url(self.analysed), {'title': 'X'})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ==== LIST / RETRIEVE

    def listed_ids(self, **params):
        response = self.client.get('/api/videos/', params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [video['id'] for video in response.data['results']]

    def test_list_only_own_videos_newest_first(self):
        # Another user's public video is in the library, but never in "my uploads".
        self.others_public_video()
        self.assertEqual(self.listed_ids(), [self.pending.pk, self.analysed.pk])

    def test_list_is_paginated(self):
        response = self.client.get('/api/videos/', {'limit': 1})
        self.assertEqual(set(response.data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(response.data['count'], 2)
        self.assertEqual([video['id'] for video in response.data['results']], [self.pending.pk])
        self.assertIsNone(response.data['previous'])

        second_page = self.client.get(response.data['next'])
        self.assertEqual([video['id'] for video in second_page.data['results']], [self.analysed.pk])
        self.assertIsNone(second_page.data['next'])

    def test_list_limit_is_capped_at_100(self):
        Video.objects.bulk_create([
            Video(owner=self.dancer, title=f'Bulk {number}', path_to_resource='videos/dummy.mp4', file_size=1.0)
            for number in range(105)
        ])
        self.assertEqual(len(self.listed_ids()), 20)
        self.assertEqual(len(self.listed_ids(limit=5000)), 100)

    def test_list_filters(self):
        published = Video.objects.create(
            owner=self.dancer, title='Kizomba', path_to_resource=video_file('kizomba.mp4'), file_size=16.0,
            song_title='Suavemente', analysis_status=AnalysisStatus.DONE, difficulty=Difficulty.ADVANCED,
            visibility=Visibility.PUBLIC, published_at=timezone.now(),
        )
        self.assertEqual(self.listed_ids(analysis_status='pending'), [self.pending.pk])
        self.assertEqual(self.listed_ids(analysis_status='done'), [published.pk, self.analysed.pk])
        self.assertEqual(self.listed_ids(visibility='public'), [published.pk])
        self.assertEqual(self.listed_ids(visibility='private'), [self.pending.pk, self.analysed.pk])
        self.assertEqual(self.listed_ids(difficulty='advanced'), [published.pk])
        self.assertEqual(self.listed_ids(search='suave'), [published.pk])
        self.assertEqual(self.listed_ids(search='SALSA'), [self.analysed.pk])
        self.assertEqual(self.listed_ids(author='DANCER'), [published.pk, self.pending.pk, self.analysed.pk])
        self.assertEqual(self.listed_ids(author='other'), [])       # filters never show someone else's videos
        self.assertEqual(self.listed_ids(visibility='public', analysis_status='pending'), [])

    def test_list_ordering(self):
        Video.objects.filter(pk=self.analysed.pk).update(likes_count=3)
        DanceAttempt.objects.create(user=self.other, reference_video=self.analysed, reference_title='Salsa')
        self.assertEqual(self.listed_ids(ordering='likes'), [self.analysed.pk, self.pending.pk])
        self.assertEqual(self.listed_ids(ordering='played'), [self.analysed.pk, self.pending.pk])
        self.assertEqual(self.listed_ids(ordering='newest'), [self.pending.pk, self.analysed.pk])

    def test_list_bad_params_are_400(self):
        for field, value in [('analysis_status', 'finished'), ('visibility', 'hidden'),
                             ('difficulty', 'foo'), ('ordering', 'x')]:
            with self.subTest(field=field):
                response = self.client.get('/api/videos/', {field: value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(list(response.data), [field])

    def test_list_fields(self):
        response = self.client.get('/api/videos/')
        self.assertEqual(
            set(response.data['results'][0]),
            {
                'id', 'title', 'description',
                'song_author', 'song_title', 'difficulty',
                'file_size', 'duration_seconds', 'analysis_status',
                'visibility', 'published_at', 'likes_count',
                'created_at', 'updated_at',
            },
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
            # execute=False: the callbacks are only collected, as if the transaction hadn't committed yet.
            with self.captureOnCommitCallbacks() as callbacks:
                response = self.upload(title='New', file=video_file())
            start_analysis.assert_not_called()  # not before the commit

            self.assertEqual(len(callbacks), 1)
            callbacks[0]()  # what Django runs once the transaction commits

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
        with mock.patch('core.validators.MAX_VIDEO_SIZE_BYTES', 4):
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

    # Disabled: the file can no longer be replaced via PATCH (it is 400 now). Kept in case that changes.
    # def test_replace_file_resets_and_reruns_analysis(self):
    #     old_path = Path(settings.MEDIA_ROOT, self.analysed.path_to_resource.name)
    #     with mock.patch('videos.services.start_analysis') as start_analysis:
    #         with self.captureOnCommitCallbacks(execute=True):
    #             response = self.client.patch(
    #                 self.url(self.analysed), {'file': video_file('new.webm', b'new bytes!')}, format='multipart',
    #             )
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertNotIn('file', response.data)  # write-only
    #     self.assertEqual(response.data['analysis_status'], 'pending')
    #
    #     self.analysed.refresh_from_db()
    #     self.assertEqual(self.analysed.file_size, len(b'new bytes!'))
    #     self.assertIsNone(self.analysed.json_analysis)
    #     self.assertTrue(self.analysed.path_to_resource.name.endswith('.webm'))
    #     self.assertTrue(Path(settings.MEDIA_ROOT, self.analysed.path_to_resource.name).is_file())
    #     self.assertFalse(old_path.exists())
    #     start_analysis.assert_called_once_with(video=self.analysed)

    def test_patch_with_file_is_400(self):
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

    # ==== STREAM

    def stream(self, video, headers=None, **params):
        """GET /stream/ and read the whole streamed body."""
        response = self.client.get(self.url(video, 'stream/'), params, headers=headers)
        # Reading to the end also closes the response (and the file). Don't call
        # response.close() again: that would close the test's DB connection.
        body = b''.join(response.streaming_content) if response.streaming else response.content
        return response, body

    def test_stream_whole_file(self):
        response, body = self.stream(self.analysed)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'video/mp4')
        self.assertEqual(response['Content-Length'], str(len(b'fake video bytes')))
        self.assertEqual(body, b'fake video bytes')
        # inline = play in the browser; the filename is only a suggestion for "Save as".
        self.assertEqual(response['Content-Disposition'], 'inline; filename="Salsa basic step.mp4"')
        self.assertEqual(response['Accept-Ranges'], 'bytes')

    def test_stream_range_start_end(self):
        response, body = self.stream(self.analysed, headers={'Range': 'bytes=0-3'})
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(body, b'fake')
        self.assertEqual(response['Content-Range'], 'bytes 0-3/16')
        self.assertEqual(response['Content-Length'], '4')
        self.assertEqual(response['Content-Type'], 'video/mp4')
        self.assertEqual(response['Accept-Ranges'], 'bytes')

    def test_stream_range_open_end(self):
        response, body = self.stream(self.analysed, headers={'Range': 'bytes=4-'})
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(body, b' video bytes')
        self.assertEqual(response['Content-Range'], 'bytes 4-15/16')

    def test_stream_range_suffix(self):
        response, body = self.stream(self.analysed, headers={'Range': 'bytes=-3'})
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(body, b'tes')
        self.assertEqual(response['Content-Range'], 'bytes 13-15/16')

    def test_stream_range_out_of_file_is_416(self):
        response, _ = self.stream(self.analysed, headers={'Range': 'bytes=16-'})
        self.assertEqual(response.status_code, status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
        self.assertEqual(response['Content-Range'], 'bytes */16')

    def test_stream_malformed_range_sends_whole_file(self):
        response, body = self.stream(self.analysed, headers={'Range': 'bytes=abc'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(body, b'fake video bytes')

    def test_stream_download_with_range_keeps_attachment(self):
        response, body = self.stream(self.analysed, headers={'Range': 'bytes=0-3'}, download='1')
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="Salsa basic step.mp4"')

    def test_stream_download(self):
        response, body = self.stream(self.analysed, download='1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="Salsa basic step.mp4"')
        self.assertEqual(body, b'fake video bytes')

    def test_stream_other_users_video_is_404(self):
        response = self.client.get(self.url(self.others_video, 'stream/'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_stream_other_users_public_video(self):
        response, body = self.stream(self.others_public_video())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(body, b'fake video bytes')

    def test_stream_public_video_of_inactive_owner_is_404(self):
        video = self.others_public_video()
        self.other.is_active = False
        self.other.save()
        self.assertEqual(self.client.get(self.url(video, 'stream/')).status_code, status.HTTP_404_NOT_FOUND)

    def test_stream_public_video_without_login(self):
        # A visitor can watch a public video (D7.6), Range included...
        public = self.others_public_video()
        self.client.force_authenticate(None)

        response, body = self.stream(public)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(body, b'fake video bytes')
        response, body = self.stream(public, headers={'Range': 'bytes=0-3'})
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(body, b'fake')

    def test_stream_private_video_without_login_is_404(self):
        # ...but nothing else: a private video is 404 (the same answer as "no such id").
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url(self.analysed, 'stream/')).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get('/api/videos/999999/stream/').status_code, status.HTTP_404_NOT_FOUND)

    def test_stream_is_the_only_video_route_open_without_login(self):
        public = self.others_public_video()
        self.client.force_authenticate(None)
        for suffix in ['', 'analysis/', 'thumbnail/']:
            with self.subTest(suffix=suffix):
                response = self.client.get(self.url(public, suffix))
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_users_public_video_is_still_not_mine_to_manage(self):
        # Only stream and analysis are open to others; /api/videos/{id}/ itself stays "my uploads".
        video = self.others_public_video()
        self.assertEqual(self.client.get(self.url(video)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(self.url(video), {'title': 'X'}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(self.url(video)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(self.url(video, 'thumbnail/')).status_code, status.HTTP_404_NOT_FOUND)

    # ==== OTHER ACTIONS

    def test_thumbnail_not_implemented(self):
        response = self.client.get(self.url(self.analysed, 'thumbnail/'))
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

    def test_analysis_other_users_public_video(self):
        video = self.others_public_video()
        response = self.client.get(self.url(video, 'analysis/'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), video.json_analysis)

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
        self.dancer = get_user_model().objects.create_user(username='dancer', nickname='dancer', password='pass')
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
        statuses_seen = []

        def record_status(file_path):
            statuses_seen.append(Video.objects.get(pk=self.video.pk).analysis_status)
            return []

        with mock.patch('videos.tasks.run_analysis', side_effect=record_status):
            analyse_video(self.video.pk)
        # Asserted here, not inside record_status: the task catches every exception from
        # run_analysis, so a failing assert in there would only mark the video 'failed'.
        self.assertEqual(statuses_seen, [AnalysisStatus.PROCESSING])

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


class ParseRangeHeaderTests(SimpleTestCase):
    """The Range parser alone, without HTTP. File size is 1000 bytes (0..999)."""

    def test_start_end(self):
        self.assertEqual(parse_range_header('bytes=0-99', 1000), (0, 99))

    def test_open_end(self):
        self.assertEqual(parse_range_header('bytes=500-', 1000), (500, 999))

    def test_suffix(self):
        self.assertEqual(parse_range_header('bytes=-100', 1000), (900, 999))

    def test_suffix_longer_than_file(self):
        self.assertEqual(parse_range_header('bytes=-5000', 1000), (0, 999))

    def test_end_clamped_to_file(self):
        self.assertEqual(parse_range_header('bytes=900-5000', 1000), (900, 999))

    def test_spaces_allowed(self):
        self.assertEqual(parse_range_header('bytes= 0 - 9', 1000), (0, 9))

    def test_ignored_headers(self):
        for header in [None, '', 'bytes=', 'bytes=-', 'items=0-9', 'bytes=abc', 'bytes=5', 'bytes=9-5',
                       'bytes=0-1,5-9', 'bytes=1.5-2']:
            with self.subTest(header=header):
                self.assertIsNone(parse_range_header(header, 1000))

    def test_not_satisfiable(self):
        for header, size in [('bytes=1000-', 1000), ('bytes=5000-6000', 1000), ('bytes=-0', 1000), ('bytes=-5', 0)]:
            with self.subTest(header=header, size=size):
                with self.assertRaises(RangeNotSatisfiable):
                    parse_range_header(header, size)
