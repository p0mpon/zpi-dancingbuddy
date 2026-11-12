import json
from unittest.mock import patch
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from videos.models import Video, AnalysisStatus
from dance_attempts.models import DanceAttempt

User = get_user_model()

class DanceAttemptViewSetTests(APITestCase):

    BASE_URL = '/api/dance-attempts'

    def setUp(self):
        self.user = User.objects.create_user(username='dancer')
        self.other_user = User.objects.create_user(username='other')
        
        # Test client acts as the logged-in user
        self.client.force_authenticate(user=self.user)

        self.video = Video.objects.create(
            owner=self.user,
            title='Fancy',
            path_to_resource='videos/fancy-twice.mp4',
            file_size=100,
            published_at='2026-11-08T12:00:00Z',
            visibility='public',
            analysis_status=AnalysisStatus.DONE,
        )
        self.other_video = Video.objects.create(
            owner=self.user,
            title='Feel Special',
            path_to_resource='videos/feel_special-twice.mp4',
            file_size=100,
            published_at='2026-11-08T12:00:00Z',
            visibility='public',
            analysis_status=AnalysisStatus.DONE,
        )
        self.private_video = Video.objects.create(
            owner=self.other_user,
            title='Gods Menu',
            path_to_resource='videos/gods_menu-stray_kids.mp4',
            file_size=100,
            published_at=None,
            visibility='private',
            analysis_status=AnalysisStatus.DONE,
        )

    def test_list_attempts_with_pagination(self):
        # GIVEN the user has 3 attempts
        for _ in range(3):
            DanceAttempt.objects.create(
                user=self.user, 
                reference_video=self.video,
                status=AnalysisStatus.DONE,
                score=80,
            )

        # WHEN we request the list with a limit
        response = self.client.get(f'{self.BASE_URL}/', {'limit': 2})

        # THEN we should get a 200 OK and paginated structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_attempts_filters_by_video_id(self):
        # GIVEN attempts for two different videos
        DanceAttempt.objects.create(user=self.user, reference_video=self.video)
        DanceAttempt.objects.create(user=self.user, reference_video=self.other_video)

        # WHEN we filter by the first video's ID
        response = self.client.get(f'{self.BASE_URL}/', {'video_id': self.video.id})

        # THEN only 1 attempt should be returned
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_attempt_success(self):
        # GIVEN valid multipart upload data
        recording = SimpleUploadedFile('dance.mp4', b'video_data', content_type='video/mp4')
        payload = {
            'reference_video_id': self.video.id,
            'recording': recording,
            'mediapipe_data': json.dumps([{"x": 1}])
        }

        # WHEN we try to create an attempt
        response = self.client.post(f'{self.BASE_URL}/', payload, format='multipart')

        # THEN we should get a 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], AnalysisStatus.PENDING)

    def test_create_attempt_video_not_found_returns_404(self):
        # GIVEN a non-existent video ID
        recording = SimpleUploadedFile('dance.mp4', b'video_data', content_type='video/mp4')
        payload = {
            'reference_video_id': 9999,
            'recording': recording,
            'mediapipe_data': json.dumps([{"x": 1}])
        }

        # WHEN we try to create an attempt
        response = self.client.post(f'{self.BASE_URL}/', payload, format='multipart')

        # THEN should return 404 Not Found
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', response.data)

    def test_create_attempt_video_not_owned_returns_404(self):
        # GIVEN a private video that belongs to another user
        recording = SimpleUploadedFile('dance.mp4', b'video_data', content_type='video/mp4')
        payload = {
            'reference_video_id': self.private_video.id,
            'recording': recording,
            'mediapipe_data': json.dumps([{"x": 1}])
        }

        # WHEN we try to create an attempt
        response = self.client.post(f'{self.BASE_URL}/', payload, format='multipart')

        # THEN should return 404 Not Found since the video is not accessible
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', response.data)

    def test_create_attempt_video_not_ready_returns_409(self):
        # GIVEN the video is still processing
        self.video.analysis_status = AnalysisStatus.PENDING
        self.video.save()

        recording = SimpleUploadedFile('dance.mp4', b'data', content_type='video/mp4')
        payload = {
            'reference_video_id': self.video.id,
            'recording': recording,
            'mediapipe_data': json.dumps([{"x": 1}]),
        }

        # WHEN we try to create an attempt
        response = self.client.post(f'{self.BASE_URL}/', payload, format='multipart')

        # THEN should catch the error and return 409 Conflict
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

    def test_delete_attempt_success(self):
        # GIVEN an existing attempt
        attempt = DanceAttempt.objects.create(user=self.user, reference_video=self.video)

        # WHEN we send a DELETE request
        response = self.client.delete(f'{self.BASE_URL}/{attempt.id}/')

        # THEN we get 204 No Content and it is removed from the database
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DanceAttempt.objects.filter(id=attempt.id).exists())

    def test_delete_someone_elses_attempt_returns_404(self):
        # GIVEN an attempt belonging to a different user
        other_attempt = DanceAttempt.objects.create(user=self.other_user, reference_video=self.video)

        # WHEN our authenticated user tries to delete it
        response = self.client.delete(f'{self.BASE_URL}/{other_attempt.id}/')

        # THEN returns 404 Not Found and the attempt still exists
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(DanceAttempt.objects.filter(id=other_attempt.id).exists())

    def test_reanalyze_failed_attempt_success(self):
        # GIVEN a failed analysis status attempt
        attempt = DanceAttempt.objects.create(
            user=self.user, reference_video=self.video, status=AnalysisStatus.FAILED
        )

        # WHEN we trigger reanalyze
        response = self.client.post(f'{self.BASE_URL}/{attempt.id}/reanalyze/')

        # THEN it returns 202 Accepted and status shifts to pending
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['status'], AnalysisStatus.PENDING)

    def test_reanalyze_pending_attempt_returns_409(self):
        # GIVEN an attempt that is already PENDING (not failed)
        attempt = DanceAttempt.objects.create(
            user=self.user, reference_video=self.video, status=AnalysisStatus.PENDING
        )

        # WHEN we trigger reanalyze
        response = self.client.post(f'{self.BASE_URL}/{attempt.id}/reanalyze/')

        # THEN returns 409
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)