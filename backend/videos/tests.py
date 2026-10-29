import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AnalysisStatus, Video

# Uploaded files go to a throw-away folder, removed after the test class runs.
TEST_MEDIA_ROOT = tempfile.mkdtemp()


def video_file(name='dance.mp4', content=b'fake video bytes'):
    return SimpleUploadedFile(name, content, content_type='video/mp4')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class VideoApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.dancer = get_user_model().objects.create_user(username='dancer', password='pass')
        self.client.force_authenticate(self.dancer)

    def upload(self, **data):
        return self.client.post('/api/videos/', data, format='multipart')

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/videos/').status_code, status.HTTP_403_FORBIDDEN)

    def test_list_hides_internal_fields(self):
        response = self.client.get('/api/videos/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data[0]), {'id', 'title', 'file_size'})

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

    def test_upload_ignores_owner_in_form(self):
        other = get_user_model().objects.create_user(username='other', password='pass')
        response = self.upload(title='New', file=video_file(), owner=other.pk)
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
            response = self.upload(title='New', file=video_file(content=b'12345'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)
        self.assertFalse(Video.objects.exists())

    def test_upload_requires_title(self):
        response = self.upload(file=video_file())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)

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
