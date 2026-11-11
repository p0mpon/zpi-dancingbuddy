from datetime import timedelta
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from dance_attempts.models import DanceAttempt
from dance_attempts.services import (
    AttemptNotFailedError,
    VideoNotReadyError,
    create_attempt,
    delete_attempt,
    get_attempts_for_user_with_score_diffs,
    reanalyze_attempt,
    set_attempt_result,
)
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
            analysis_status=AnalysisStatus.DONE,
        )
        self.private_video = Video.objects.create(
            owner=self.user,
            title='Feel Special',
            path_to_resource='videos/feel_special-twice.mp4',
            file_size=100,
            visibility='private',
            analysis_status=AnalysisStatus.DONE,
        )

    def create_scored_attempt(self, video, score, created_at):
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=video,
            reference_title=video.title,
            status=AnalysisStatus.DONE,
            score=score,
        )
        DanceAttempt.objects.filter(pk=attempt.pk).update(created_at=created_at)
        return attempt

    def test_create_attempt_copies_reference_data_and_sets_pending_status_and_queues_analysis(self):
        # GIVEN a user, a reference video, and a recording file
        recording = SimpleUploadedFile('attempt.mp4', b'video', content_type='video/mp4')

        # WHEN we call create_attempt
        with patch(
            'dance_attempts.services.start_attempt_analysis'
        ) as start_analysis:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                attempt = create_attempt(
                    user=self.user,
                    reference_video_id=self.public_video.id,
                    recording=recording,
                )

        # THEN the attempt should be created with the correct data and PENDING status
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.reference_video, self.public_video)
        self.assertEqual(attempt.reference_title, self.public_video.title)
        self.assertEqual(attempt.status, AnalysisStatus.PENDING)
        self.assertEqual(attempt.recording.name.split('/')[1], f'user_{self.user.id}')
        # AND the recording file should exist
        self.assertTrue(os.path.exists(attempt.recording.path))
        # AND analysis should be queued
        self.assertEqual(len(callbacks), 1)
        start_analysis.assert_called_once_with(attempt=attempt)

    def test_create_attempt_rejects_another_users_private_video(self):
        # GIVEN another user and a private video owned by the first user
        # WHEN we call create_attempt with the other user and the private video
        # THEN it should raise an Not Found error
        with self.assertRaises(Http404):
            create_attempt(
                user=self.other_user,
                reference_video_id=self.private_video.id,
            )

        # AND no attempt should be created
        self.assertFalse(DanceAttempt.objects.exists())

    def test_create_attempt_allows_public_video(self):
        # GIVEN another user and a public video owned by the first user
        # WHEN we call create_attempt with the other user and the public video
        attempt = create_attempt(
            user=self.other_user,
            reference_video_id=self.public_video.id,
        )

        # THEN the attempt should be created successfully
        self.assertEqual(attempt.user, self.other_user)

    def test_create_attempt_allows_users_own_private_video(self):
        # GIVEN a user and their own private video
        # WHEN we call create_attempt with the user and their private video
        attempt = create_attempt(
            user=self.user,
            reference_video_id=self.private_video.id,
        )

        # THEN the attempt should be created successfully
        self.assertEqual(attempt.user, self.user)

    def test_create_attempt_rejects_video_that_is_not_ready(self):
        # GIVEN a public video that is not yet analyzed
        self.public_video.analysis_status = AnalysisStatus.PENDING
        self.public_video.save(update_fields=['analysis_status'])

        # WHEN we call create_attempt with that video
        # THEN it should raise a VideoNotReadyError
        with self.assertRaises(VideoNotReadyError):
            create_attempt(
                user=self.user,
                reference_video_id=self.public_video.id,
            )

        # AND no attempt should be created
        self.assertFalse(DanceAttempt.objects.exists())

    def test_set_attempt_result_updates_matching_attempt(self):
        # GIVEN a DanceAttempt with PENDING status
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            recording='attempt.mp4',
        )

        # WHEN we call set_attempt_result with the attempt's id and new status and score
        result = set_attempt_result(
            attempt_id=attempt.pk,
            status=AnalysisStatus.DONE,
            score=87,
            score_details={'scored_frames': 0.87},
        )

        # THEN the attempt's status, score, and score_details should be updated
        self.assertTrue(result)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.DONE)
        self.assertEqual(attempt.score, 87)
        self.assertEqual(attempt.score_details, {'scored_frames': 0.87})

    def test_set_attempt_result_returns_false_for_nonexistent_attempt(self):
        # GIVEN a DanceAttempt with PENDING status
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            recording='attempt.mp4',
        )

        # WHEN we call set_attempt_result with a non-existent attempt id
        result = set_attempt_result(
            attempt_id=attempt.pk + 1,
            status=AnalysisStatus.DONE,
            score=87,
        )

        # THEN the method should return False and the existing attempt should remain unchanged
        self.assertFalse(result)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.PENDING)
        self.assertIsNone(attempt.score)

    def test_delete_attempt_deletes_recording(self):
        # GIVEN a DanceAttempt with an associated recording file
        recording = SimpleUploadedFile(
            'attempt.mp4',
            b'video',
            content_type='video/mp4',
        )
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            recording=recording,
        )
        recording_name = attempt.recording.name
        recording_storage = attempt.recording.storage

        # file exists before deletion
        self.assertTrue(recording_storage.exists(recording_name))

        # WHEN we call delete_attempt
        delete_attempt(attempt=attempt)

        # THEN the DanceAttempt should be deleted and the recording file should no longer exist
        self.assertFalse(DanceAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertFalse(recording_storage.exists(recording_name))

    def test_reanalyze_attempt_resets_failed_attempt_and_queues_analysis(self):
        # GIVEN a failed attempt with previous analysis results
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            status=AnalysisStatus.FAILED,
            score_details={'error': 'analysis failed'},
        )

        # WHEN we reanalyze it
        with patch(
            'dance_attempts.services.start_attempt_analysis'
        ) as start_analysis:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                result = reanalyze_attempt(attempt=attempt)

        # THEN the attempt is reset and analysis is queued
        self.assertEqual(result.pk, attempt.pk)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.PENDING)
        self.assertIsNone(attempt.score)
        self.assertIsNone(attempt.score_details)
        self.assertEqual(len(callbacks), 1)
        start_analysis.assert_called_once_with(attempt=attempt)

    def test_reanalyze_attempt_rejects_non_failed_attempt(self):
        # GIVEN an attempt that is not failed
        attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            status=AnalysisStatus.PENDING,
        )

        # WHEN we try to reanalyze it
        # THEN the service rejects the request
        with self.assertRaises(AttemptNotFailedError):
            reanalyze_attempt(attempt=attempt)

        # AND the attempt's status remains unchanged
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AnalysisStatus.PENDING)

    def test_get_attempts_for_user_with_score_diffs_returns_all_attempts(self):
        # GIVEN a user with multiple DanceAttempts for different videos, each with scores
        start = timezone.now()
        first = self.create_scored_attempt(self.public_video, 50, start)
        second = self.create_scored_attempt(
            self.public_video, 70, start + timedelta(minutes=1)
        )
        third = self.create_scored_attempt(
            self.public_video, 60, start + timedelta(minutes=2)
        )
        other_video_first = self.create_scored_attempt(
            self.private_video, 80, start
        )
        other_video_second = self.create_scored_attempt(
            self.private_video, 90, start + timedelta(minutes=1)
        )
        DanceAttempt.objects.create(
            user=self.other_user,
            reference_video=self.public_video,
            reference_title=self.public_video.title,
            status=AnalysisStatus.DONE,
            score=100,
        )

        # WHEN we call get_attempts_for_user_with_score_diffs for the user
        attempts = get_attempts_for_user_with_score_diffs(self.user)
        attempts_by_id = {attempt.pk: attempt for attempt in attempts}

        # THEN all attempts for the user should be returned, and score diffs should be calculated correctly
        # all attempts are returned
        self.assertEqual(set(attempts_by_id), {
            first.pk,
            second.pk,
            third.pk,
            other_video_first.pk,
            other_video_second.pk,
        })
        # score diffs are calculated correctly
        self.assertIsNone(attempts_by_id[first.pk].score_diff_previous)
        self.assertIsNone(attempts_by_id[first.pk].score_diff_best)
        self.assertEqual(attempts_by_id[second.pk].score_diff_previous, 20)
        self.assertEqual(attempts_by_id[second.pk].score_diff_best, 20)
        self.assertEqual(attempts_by_id[third.pk].score_diff_previous, -10)
        self.assertEqual(attempts_by_id[third.pk].score_diff_best, -10)
        self.assertIsNone(attempts_by_id[other_video_first.pk].score_diff_previous)
        self.assertIsNone(attempts_by_id[other_video_first.pk].score_diff_best)
        self.assertEqual(attempts_by_id[other_video_second.pk].score_diff_previous, 10)
        self.assertEqual(attempts_by_id[other_video_second.pk].score_diff_best, 10)

    def test_get_attempts_for_user_with_score_diffs_filters_by_video(self):
        # GIVEN a user with multiple DanceAttempts for different videos, each with scores
        start = timezone.now()
        first = self.create_scored_attempt(self.public_video, 50, start)
        second = self.create_scored_attempt(
            self.public_video, 70, start + timedelta(minutes=1)
        )
        third = self.create_scored_attempt(
            self.public_video, 60, start + timedelta(minutes=2)
        )
        other_video_attempt = self.create_scored_attempt(
            self.private_video, 90, start + timedelta(minutes=1)
        )

        # WHEN we call get_attempts_for_user_with_score_diffs for the user and filter by the public video id
        attempts = get_attempts_for_user_with_score_diffs(
            self.user,
            video_id=self.public_video.id,
        )
        attempts_by_id = {attempt.pk: attempt for attempt in attempts}

        # THEN only the attempts for the specified video should be returned, and score diffs should be calculated correctly
        # only attempts for the specified video are returned
        self.assertEqual(set(attempts_by_id), {first.pk, second.pk, third.pk})
        self.assertNotIn(other_video_attempt.pk, attempts_by_id)
        # score diffs are calculated correctly
        self.assertIsNone(attempts_by_id[first.pk].score_diff_previous)
        self.assertIsNone(attempts_by_id[first.pk].score_diff_best)
        self.assertEqual(attempts_by_id[second.pk].score_diff_previous, 20)
        self.assertEqual(attempts_by_id[second.pk].score_diff_best, 20)
        self.assertEqual(attempts_by_id[third.pk].score_diff_previous, -10)
        self.assertEqual(attempts_by_id[third.pk].score_diff_best, -10)
