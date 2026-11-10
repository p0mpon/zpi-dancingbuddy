from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from dance_attempts.models import DanceAttempt
from dance_attempts.services import create_attempt, set_attempt_result
from videos.models import AnalysisStatus, Video


class DanceAttemptServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='dancer')
        self.other_user = User.objects.create_user(username='other')
        self.public_video = Video.objects.create(
            owner=self.user,
            title='Fancy',
            path_to_resource='videos/fancy-twice.mp4',
            file_size=100,
            published_at='2026-11-08T12:00:00Z',
            visibility='public',
        )
        self.private_video = Video.objects.create(
            owner=self.user,
            title='Feel Special',
            path_to_resource='videos/feel_special-twice.mp4',
            file_size=100,
            visibility='private',
        )

    def test_create_attempt_copies_reference_data_and_sets_pending_status(self):
        recording = SimpleUploadedFile('attempt.mp4', b'video', content_type='video/mp4')

        attempt = create_attempt(
            user=self.user,
            reference_video=self.public_video,
            recording=recording,
        )

        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.reference_video, self.public_video)
        self.assertEqual(attempt.reference_title, self.public_video.title)
        self.assertEqual(attempt.status, AnalysisStatus.PENDING)
        self.assertEqual(attempt.recording.name.split('/')[1], f'user_{self.user.id}')

    def test_create_attempt_rejects_another_users_private_video(self):
        with self.assertRaises(PermissionDenied):
            create_attempt(user=self.other_user, reference_video=self.private_video)

        self.assertFalse(DanceAttempt.objects.exists())

    def test_create_attempt_allows_public_video(self):
        attempt = create_attempt(user=self.other_user, reference_video=self.public_video)

        self.assertEqual(attempt.user, self.other_user)

    def test_create_attempt_allows_users_own_private_video(self):
        attempt = create_attempt(user=self.user, reference_video=self.private_video)

        self.assertEqual(attempt.user, self.user)

    def test_set_attempt_result_updates_matching_attempt(self):
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            recording='attempt.mp4',
        )

        result = set_attempt_result(
            attempt_id=attempt.pk,
            file_name=attempt.recording.name,
            status=AnalysisStatus.DONE,
            score=87,
            json_analysis={'frames': 10},
            score_details={'scored_frames': 0.87},
        )

        self.assertTrue(result)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.DONE)
        self.assertEqual(attempt.score, 87)
        self.assertEqual(attempt.json_analysis, {'frames': 10})
        self.assertEqual(attempt.score_details, {'scored_frames': 0.87})

    def test_set_attempt_result_returns_false_for_non_matching_recording(self):
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            recording='attempt.mp4',
        )

        result = set_attempt_result(
            attempt_id=attempt.pk,
            file_name='attempts/user_1/other.mp4',
            status=AnalysisStatus.DONE,
            score=87,
        )

        self.assertFalse(result)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.PENDING)
        self.assertIsNone(attempt.score)
