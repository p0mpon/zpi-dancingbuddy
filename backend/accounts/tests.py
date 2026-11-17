"""User model rules. The API is tested in tests_api.py."""

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dancer01', nickname='Ana', password='pass-Word-123')

    def test_str_is_the_public_nickname_never_the_username(self):
        self.assertEqual(str(self.user), 'Ana')

    def test_profile_fields_default_to_empty(self):
        self.assertIsNone(self.user.avatar.name)
        self.assertEqual(self.user.bio, '')
        self.assertEqual(self.user.recovery_code_hash, '')
        self.assertEqual(self.user.email, '')       # Django's field, unused

    def test_nickname_is_unique_case_insensitively(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='someone_else', nickname='ana')

    def test_username_is_unique_case_insensitively(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='DANCER01', nickname='Other')

    def test_sign_in_ignores_username_case(self):
        self.assertEqual(authenticate(username='DaNcEr01', password='pass-Word-123'), self.user)

    def test_sign_in_with_the_nickname_fails(self):
        self.assertIsNone(authenticate(username='Ana', password='pass-Word-123'))


class UserValidationTests(TestCase):
    def make(self, **fields):
        data = {'username': 'dancer01', 'nickname': 'Ana', 'password': 'x'} | fields
        return User(**data)

    def errors(self, **fields):
        try:
            self.make(**fields).full_clean()
        except ValidationError as error:
            return error.message_dict
        return {}

    def test_valid_user_passes(self):
        self.assertEqual(self.errors(), {})

    def test_nickname_me_is_reserved_in_any_case(self):
        self.assertIn('nickname', self.errors(nickname='me'))
        self.assertIn('nickname', self.errors(nickname='ME'))

    def test_nickname_length(self):
        self.assertIn('nickname', self.errors(nickname='ab'))
        self.assertIn('nickname', self.errors(nickname='a' * 33))
        self.assertEqual(self.errors(nickname='abc'), {})

    def test_nickname_only_url_safe_characters(self):
        for bad in ['ana maria', 'ana/x', 'ana@x', 'żaba']:
            with self.subTest(nickname=bad):
                self.assertIn('nickname', self.errors(nickname=bad))
        self.assertEqual(self.errors(nickname='Ana.M_a-1'), {})

    def test_username_length(self):
        self.assertIn('username', self.errors(username='short'))
        self.assertIn('username', self.errors(username='a' * 33))
        self.assertEqual(self.errors(username='sixsix'), {})

    def test_nickname_is_required(self):
        self.assertIn('nickname', self.errors(nickname=''))
