from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model

from videos.models import Video, AnalysisStatus
from dance_attempts.models import DanceAttempt
from dance_attempts.tasks import analyse_attempt

User = get_user_model()

class AnalyseAttemptTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dancer')
        self.video = Video.objects.create(
            owner=self.user,
            title='Fancy',
            path_to_resource='videos/fancy-twice.mp4',
            file_size=100,
            published_at='2026-11-08T12:00:00Z',
            visibility='public',
            analysis_status=AnalysisStatus.DONE,
        )
        self.attempt = DanceAttempt.objects.create(
            user=self.user,
            reference_video=self.video,
            reference_title=self.video.title,
            status=AnalysisStatus.PENDING,
            json_analysis={'some': 'data'}
        )

    @patch('dance_attempts.tasks.run_score_analysis')
    def test_analyse_attempt_success(self, mock_run_score_analysis):
        # GIVEN the run_score_analysis function returns a valid score and details
        mock_run_score_analysis.return_value = (95, {'frames': [0.95]})

        # WHEN the Celery worker runs the task
        analyse_attempt(self.attempt.pk)

        # THEN the attempt should be marked DONE and save the score
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, AnalysisStatus.DONE)
        self.assertEqual(self.attempt.score, 95)
        self.assertEqual(self.attempt.score_details, {'frames': [0.95]})
        
        # AND verify the method was called correctly with the attempt's data
        mock_run_score_analysis.assert_called_once_with({'some': 'data'})

    @patch('dance_attempts.tasks.run_score_analysis')
    def test_analyse_attempt_handles_failure(self, mock_run_score_analysis):
        # GIVEN the run_score_analysis function crashes for some reason
        mock_run_score_analysis.side_effect = Exception("Crashed!")

        # WHEN the Celery worker runs the task
        with self.assertLogs('dance_attempts.tasks', level='ERROR') as captured_logs:
            analyse_attempt(self.attempt.pk)

        # THEN the attempt should be marked as FAILED
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, AnalysisStatus.FAILED)
        self.assertIsNone(self.attempt.score)
        self.assertIsNone(self.attempt.score_details)
        # AND correct error message should be logged
        self.assertIn("Analysis of attempt", captured_logs.output[0])

    @patch('dance_attempts.tasks.run_score_analysis')
    def test_analyse_attempt_aborts_if_deleted(self, mock_run_score_analysis):
        # GIVEN the attempt is deleted from the database before the worker starts
        attempt_id = self.attempt.pk
        self.attempt.delete()

        # WHEN the worker tries to run the task
        analyse_attempt(attempt_id)

        # THEN the task should quietly exit without crashing or calling the analysis function
        mock_run_score_analysis.assert_not_called()