"""/api/auth/ and /api/users/ against docs/openapi.yaml, plus the file-cleanup signals."""

import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.images import ImageProcessingError
from dance_attempts.models import DanceAttempt
from videos.models import AnalysisStatus, Video, Visibility

from . import services

User = get_user_model()

TEST_MEDIA_ROOT = tempfile.mkdtemp()
PASSWORD = 'Correct-Horse-42'


def image_file(name='avatar.png', image_format='PNG', size=(8, 8)):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'red').save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f'image/{image_format.lower()}')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class AccountsApiTestCase(APITestCase):
    """Rate-limit counters live in the cache, which survives between tests: start each test clean."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.user, self.code = services.register_user(username='dancer01', nickname='Ana', password=PASSWORD)

    def log_in(self, user=None):
        self.client.force_login(user or self.user)


class CsrfTests(AccountsApiTestCase):
    def test_csrf_sets_cookie(self):
        response = self.client.get('/api/auth/csrf/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIn('csrftoken', response.cookies)

    def test_login_without_csrf_token_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post('/api/auth/login/', {'username': 'dancer01', 'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_with_csrf_token_works(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get('/api/auth/csrf/').cookies['csrftoken'].value
        response = client.post('/api/auth/login/', {'username': 'dancer01', 'password': PASSWORD},
                               format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RegisterTests(AccountsApiTestCase):
    def register(self, **data):
        body = {'username': 'newdancer', 'nickname': 'Bea', 'password': PASSWORD} | data
        return self.client.post('/api/auth/register/', body, format='json')

    def test_register_returns_current_user_and_recovery_code_and_logs_in(self):
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(set(response.data), {'id', 'username', 'nickname', 'avatar_url', 'bio', 'recovery_code'})
        self.assertEqual(response.data['nickname'], 'Bea')
        self.assertIsNone(response.data['avatar_url'])
        self.assertRegex(response.data['recovery_code'], r'^[A-Z2-9]{4}(-[A-Z2-9]{4}){3}$')
        self.assertEqual(self.client.get('/api/users/me/').data['username'], 'newdancer')
        user = User.objects.get(username='newdancer')
        self.assertNotIn(response.data['recovery_code'].replace('-', ''), user.recovery_code_hash)

    def test_taken_names_ignoring_case_are_400(self):
        response = self.register(username='DANCER01', nickname='ana')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('nickname', response.data)

    def test_reserved_nickname_is_400(self):
        response = self.register(nickname='Admin')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('nickname', response.data)

    def test_weak_password_is_400(self):
        for password in ['short', '12345678901234', 'newdancer1']:
            with self.subTest(password=password):
                cache.clear()   # stay under the register rate limit
                response = self.register(password=password)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('password', response.data)

    def test_rate_limited(self):
        for i in range(3):
            self.register(username=f'user{i}xyz', nickname=f'nick{i}')
        response = self.register(username='user9xyz', nickname='nick9')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', response.headers)


class LoginLogoutTests(AccountsApiTestCase):
    def login(self, username='dancer01', password=PASSWORD):
        return self.client.post('/api/auth/login/', {'username': username, 'password': password}, format='json')

    def test_login_returns_current_user(self):
        response = self.login(username='DANCER01')     # case doesn't matter
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nickname'], 'Ana')
        self.assertEqual(self.client.get('/api/users/me/').status_code, status.HTTP_200_OK)

    def test_wrong_password_or_nickname_is_401(self):
        self.assertEqual(self.login(password='wrong').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.login(username='Ana').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_cannot_log_in(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_fields_are_400(self):
        response = self.client.post('/api/auth/login/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_rate_limited(self):
        for _ in range(5):
            self.login(password='wrong')
        self.assertEqual(self.login().status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_rate_limit_counts_per_ip_even_when_logged_in(self):
        self.log_in()       # a logged-in attacker doesn't get a counter of their own
        for _ in range(5):
            self.login(username='someone', password='wrong')
        self.assertEqual(self.login(username='someone').status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_logout(self):
        self.login()
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get('/api/users/me/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_login(self):
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(AccountsApiTestCase):
    def reset(self, **data):
        body = {'username': 'dancer01', 'recovery_code': self.code, 'new_password': 'Brand-New-Pass-7'} | data
        return self.client.post('/api/auth/password-reset/', body, format='json')

    def test_reset_sets_password_and_issues_new_code(self):
        response = self.reset(recovery_code=self.code.lower().replace('-', ''))   # typed loosely
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data['recovery_code'], self.code)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Brand-New-Pass-7'))
        # the old code is used up
        self.assertEqual(self.reset(new_password='Another-Pass-88').status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_logs_out_other_sessions(self):
        other_device = APIClient()
        other_device.force_login(self.user)
        self.reset()
        self.assertEqual(other_device.get('/api/users/me/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_code_and_unknown_username_give_the_same_error(self):
        wrong_code = self.reset(recovery_code='AAAA-AAAA-AAAA-AAAA')
        unknown_user = self.reset(username='nobody123')
        self.assertEqual(wrong_code.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(wrong_code.data, unknown_user.data)
        self.assertEqual(wrong_code.data, {'detail': 'Invalid username or recovery code.'})

    def test_weak_new_password_is_field_error(self):
        response = self.reset(new_password='123')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)


class MeTests(AccountsApiTestCase):
    def setUp(self):
        super().setUp()
        self.log_in()

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/users/me/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me(self):
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.data, {'id': self.user.pk, 'username': 'dancer01', 'nickname': 'Ana',
                                         'avatar_url': None, 'bio': ''})

    def test_patch_nickname_and_bio(self):
        response = self.client.patch('/api/users/me/', {'nickname': 'Ana.M', 'bio': 'Salsa!'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((response.data['nickname'], response.data['bio']), ('Ana.M', 'Salsa!'))

    def test_patch_own_nickname_in_other_case_is_allowed(self):
        response = self.client.patch('/api/users/me/', {'nickname': 'ANA'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_taken_or_reserved_nickname_is_400(self):
        services.register_user(username='other123', nickname='Bea', password=PASSWORD)
        for nickname in ['bea', 'me', 'Support']:
            with self.subTest(nickname=nickname):
                response = self.client.patch('/api/users/me/', {'nickname': nickname}, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_patch_is_a_no_op(self):
        response = self.client.patch('/api/users/me/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nickname'], 'Ana')

    def test_username_cannot_be_changed_through_profile_patch(self):
        self.client.patch('/api/users/me/', {'username': 'hacked1'}, format='json')
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'dancer01')

    def test_avatar_upload_replace_and_delete(self):
        response = self.client.patch('/api/users/me/', {'avatar': image_file()}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['avatar_url'].startswith('http://testserver/'))
        self.user.refresh_from_db()
        first = Path(settings.MEDIA_ROOT, self.user.avatar.name)
        self.assertTrue(first.is_file())

        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch('/api/users/me/', {'avatar': image_file('b.jpg', 'JPEG')}, format='multipart')
        self.user.refresh_from_db()
        second = Path(settings.MEDIA_ROOT, self.user.avatar.name)
        self.assertFalse(first.exists())        # the replaced file is gone
        self.assertTrue(second.is_file())

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete('/api/users/me/avatar/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(second.exists())
        self.assertIsNone(self.client.get('/api/users/me/').data['avatar_url'])

    def test_avatar_must_be_jpeg_or_png_image(self):
        not_an_image = SimpleUploadedFile('a.png', b'not an image', content_type='image/png')
        gif = image_file('a.gif', 'GIF')
        for file in [not_an_image, gif]:
            with self.subTest(file=file.name):
                response = self.client.patch('/api/users/me/', {'avatar': file}, format='multipart')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('avatar', response.data)

    def test_avatar_is_stored_as_512_webp(self):
        response = self.client.patch('/api/users/me/', {'avatar': image_file(size=(40, 30))}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.startswith(f'avatars/user_{self.user.pk}/'))
        self.assertTrue(self.user.avatar.name.endswith('.webp'))
        with Image.open(Path(settings.MEDIA_ROOT, self.user.avatar.name)) as stored:
            self.assertEqual(stored.format, 'WEBP')
            self.assertEqual(stored.size, (512, 512))

    def test_avatar_with_too_many_pixels_is_400(self):
        with patch('accounts.serializers.MAX_AVATAR_PIXELS', 100):
            response = self.client.patch('/api/users/me/', {'avatar': image_file(size=(20, 20))}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('avatar', response.data)

    def test_avatar_processing_failure_is_400_not_500(self):
        # MEDIA_ROOT is shared by the tests of this class: compare before / after, not against empty.
        files_before = set(Path(settings.MEDIA_ROOT, 'avatars').rglob('*.*'))
        with patch('accounts.serializers.make_square_webp', side_effect=ImageProcessingError('x')):
            response = self.client.patch('/api/users/me/', {'avatar': image_file()}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('avatar', response.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        self.assertEqual(set(Path(settings.MEDIA_ROOT, 'avatars').rglob('*.*')), files_before)

    def test_patch_without_avatar_keeps_the_avatar(self):
        self.client.patch('/api/users/me/', {'avatar': image_file()}, format='multipart')
        self.user.refresh_from_db()
        before = self.user.avatar.name
        self.client.patch('/api/users/me/', {'bio': 'hello'}, format='multipart')
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar.name, before)
        self.assertTrue(Path(settings.MEDIA_ROOT, before).is_file())

    def test_change_username(self):
        response = self.client.patch('/api/users/me/username/', {'username': 'dancer02', 'password': PASSWORD},
                                     format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'dancer02')
        self.assertIsNotNone(authenticate(username='dancer02', password=PASSWORD))

    def test_change_username_wrong_password_is_403(self):
        response = self.client.patch('/api/users/me/username/', {'username': 'dancer02', 'password': 'nope'},
                                     format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {'detail': 'Password is incorrect.'})

    def test_change_username_to_taken_is_400(self):
        services.register_user(username='other123', nickname='Bea', password=PASSWORD)
        response = self.client.patch('/api/users/me/username/', {'username': 'OTHER123', 'password': PASSWORD},
                                     format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_keeps_this_session_and_logs_out_others(self):
        other_device = APIClient()
        other_device.force_login(self.user)
        response = self.client.post('/api/users/me/password/',
                                    {'old_password': PASSWORD, 'new_password': 'Brand-New-Pass-7'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get('/api/users/me/').status_code, status.HTTP_200_OK)
        self.assertEqual(other_device.get('/api/users/me/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_wrong_old_is_403_and_weak_new_is_400(self):
        wrong = self.client.post('/api/users/me/password/',
                                 {'old_password': 'nope', 'new_password': 'Brand-New-Pass-7'}, format='json')
        weak = self.client.post('/api/users/me/password/',
                                {'old_password': PASSWORD, 'new_password': '123'}, format='json')
        self.assertEqual(wrong.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', weak.data)

    def test_regenerate_recovery_code(self):
        response = self.client.post('/api/users/me/recovery-code/', {'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_code = response.data['recovery_code']
        with self.assertRaises(services.InvalidRecoveryCode):      # the old one stopped working
            services.user_for_recovery(username='dancer01', recovery_code=self.code)
        self.assertEqual(services.user_for_recovery(username='dancer01', recovery_code=new_code), self.user)

    def test_regenerate_recovery_code_wrong_password_is_403(self):
        response = self.client.post('/api/users/me/recovery-code/', {'password': 'nope'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_account_wrong_password_is_403(self):
        response = self.client.delete('/api/users/me/', {'password': 'nope'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_account_removes_user_data_and_files(self):
        self.client.patch('/api/users/me/', {'avatar': image_file()}, format='multipart')
        self.user.refresh_from_db()
        video = Video.objects.create(owner=self.user, title='Mine', file_size=3.0,
                                     path_to_resource=SimpleUploadedFile('v.mp4', b'abc'))
        attempt = DanceAttempt.objects.create(user=self.user, reference_video=video, reference_title='Mine',
                                              recording=SimpleUploadedFile('r.mp4', b'abc'))
        files = [Path(settings.MEDIA_ROOT, f.name) for f in (self.user.avatar, video.path_to_resource,
                                                              attempt.recording)]
        self.assertTrue(all(f.is_file() for f in files))

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete('/api/users/me/', {'password': PASSWORD}, format='json')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Video.objects.filter(pk=video.pk).exists())
        self.assertFalse(DanceAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertEqual([f for f in files if f.exists()], [])
        self.assertEqual(self.client.get('/api/users/me/').status_code, status.HTTP_401_UNAUTHORIZED)


class PublicProfileTests(AccountsApiTestCase):
    def setUp(self):
        super().setUp()
        self.viewer, _ = services.register_user(username='viewer01', nickname='Bea', password=PASSWORD)
        self.log_in(self.viewer)
        for title, visibility in [('a', Visibility.PUBLIC), ('b', Visibility.PUBLIC), ('c', Visibility.PRIVATE)]:
            Video.objects.create(owner=self.user, title=title, path_to_resource='videos/x.mp4', file_size=1.0,
                                 analysis_status=AnalysisStatus.DONE, difficulty='beginner', visibility=visibility,
                                 published_at='2026-11-12T10:00:00Z' if visibility == Visibility.PUBLIC else None)

    def test_public_profile_never_shows_username(self):
        response = self.client.get('/api/users/ana/')      # nickname case doesn't matter
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'nickname': 'Ana', 'avatar_url': None, 'bio': '', 'public_videos_count': 2})

    def test_unknown_or_inactive_user_is_404(self):
        self.assertEqual(self.client.get('/api/users/nobody/').status_code, status.HTTP_404_NOT_FOUND)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get('/api/users/Ana/').status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/users/Ana/').status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class FileCleanupSignalTests(TestCase):
    """cleanups.md: files go with their rows however the rows are deleted."""

    def setUp(self):
        self.user = User.objects.create_user(username='owner01', nickname='Owner', password=PASSWORD)

    def video(self):
        return Video.objects.create(owner=self.user, title='v', file_size=3.0,
                                    path_to_resource=SimpleUploadedFile('v.mp4', b'abc'))

    def test_bulk_delete_removes_files(self):
        path = Path(settings.MEDIA_ROOT, self.video().path_to_resource.name)
        with self.captureOnCommitCallbacks(execute=True):
            Video.objects.filter(owner=self.user).delete()
        self.assertFalse(path.exists())

    def test_rollback_keeps_the_file(self):
        path = Path(settings.MEDIA_ROOT, self.video().path_to_resource.name)
        user_pk = self.user.pk      # delete() sets pk to None on the instance
        with self.captureOnCommitCallbacks(execute=False):
            try:
                with transaction.atomic():
                    self.user.delete()
                    raise RuntimeError('roll back')
            except RuntimeError:
                pass
        self.assertTrue(path.is_file())
        self.assertTrue(User.objects.filter(pk=user_pk).exists())
