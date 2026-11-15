import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models.functions import Lower

from .validators import (
    NICKNAME_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    nickname_characters,
    nickname_min_length,
    username_min_length,
    validate_nickname_not_reserved,
)


def user_avatar_upload_path(user, filename):
    """'avatars/user_1/<random>.jpg', relative to MEDIA_ROOT."""
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'avatars/user_{user.pk}/{uuid.uuid4().hex}.{extension}'


def user_thumbnail_upload_path(user, filename):
    """Old name of user_avatar_upload_path. Kept only because migration 0002 imports it; don't use."""
    return user_avatar_upload_path(user, filename)


class UserManager(DjangoUserManager):
    """Django's manager, but signing in ignores the case of the username."""

    def get_by_natural_key(self, username):
        # ModelBackend (login, admin login) looks the user up here. Usernames are unique
        # case-insensitively (see Meta), so `Dancer` and `dancer` are the same account.
        return self.get(username__iexact=username)


class User(AbstractUser):
    """USER table from db/diagram/v2.md.

    username: private, used only to sign in (Django's USERNAME_FIELD). Only its owner ever sees it.
    nickname: public, shown everywhere else (profile URL, video authors). See docs/api-decisions.md D1.1.

    Django's email, first_name and last_name stay in the table, always empty and never in the API.
    """

    username = models.CharField(
        max_length=USERNAME_MAX_LENGTH,
        unique=True,
        validators=[UnicodeUsernameValidator(), username_min_length],
        error_messages={'unique': 'A user with that username already exists.'},
        help_text='Private, used only to sign in. 6-32 characters: letters, digits and @/./+/-/_.',
    )
    nickname = models.CharField(
        max_length=NICKNAME_MAX_LENGTH,
        unique=True,
        validators=[nickname_characters, nickname_min_length, validate_nickname_not_reserved],
        error_messages={'unique': 'A user with that nickname already exists.'},
        help_text='Public name shown everywhere. 3-32 characters: letters, digits and ./-/_.',
    )
    avatar = models.ImageField(
        upload_to=user_avatar_upload_path,
        null=True,          # null = show the default avatar
        blank=True,
    )
    bio = models.CharField(max_length=300, blank=True)
    # make_password() hash of the one-time recovery code (D1.7); empty = no code issued yet.
    recovery_code_hash = models.CharField(max_length=128, blank=True)

    # createsuperuser asks for these besides username and password (Django's default is ['email']).
    REQUIRED_FIELDS = ['nickname']

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            # `unique=True` alone is case-sensitive; these stop `Ana` next to `ana`.
            models.UniqueConstraint(Lower('username'), name='user_username_ci_unique'),
            models.UniqueConstraint(Lower('nickname'), name='user_nickname_ci_unique'),
        ]

    def __str__(self):
        # Never the username: __str__ ends up in the admin, logs and StringRelatedField.
        return self.nickname
