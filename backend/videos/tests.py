from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase


class VideoApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='dancer', password='pass')
        self.client.force_authenticate(user)

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/videos/').status_code, status.HTTP_403_FORBIDDEN)

    def test_list_hides_internal_fields(self):
        response = self.client.get('/api/videos/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data[0]), {'id', 'title', 'file_size'})

    def test_upload(self):
        file = SimpleUploadedFile('dance.mp4', b'fake video bytes', content_type='video/mp4')
        response = self.client.post('/api/videos/', {'title': 'New', 'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['file_size'], len(b'fake video bytes'))

    def test_upload_rejects_non_video(self):
        file = SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')
        response = self.client.post('/api/videos/', {'title': 'New', 'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)

    def test_retrieve_and_404(self):
        self.assertEqual(self.client.get('/api/videos/1/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/videos/999/').status_code, status.HTTP_404_NOT_FOUND)

    def test_rename_ignores_read_only_fields(self):
        response = self.client.patch('/api/videos/1/', {'title': 'Renamed', 'file_size': 1})
        self.assertEqual(response.data['title'], 'Renamed')
        self.assertNotEqual(response.data['file_size'], 1)

    def test_delete(self):
        self.assertEqual(self.client.delete('/api/videos/1/').status_code, status.HTTP_204_NO_CONTENT)

    def test_stream_and_thumbnail_not_implemented(self):
        for path in ('stream', 'thumbnail'):
            response = self.client.get(f'/api/videos/1/{path}/')
            self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)

    def test_rerun_analysis(self):
        self.assertEqual(self.client.post('/api/videos/1/analysis/').status_code, status.HTTP_202_ACCEPTED)

    def test_frames_sliced_by_time_and_joints(self):
        response = self.client.get(
            '/api/videos/1/analysis/frames/',
            {'start': 1.5, 'end': 2.0, 'joints': 'left_knee,right_knee'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 16)  # frames 45..60 at 30 fps
        self.assertEqual(set(response.data[0]['joints']), {'left_knee', 'right_knee'})

    def test_frames_need_analysis(self):
        response = self.client.get('/api/videos/2/analysis/frames/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
