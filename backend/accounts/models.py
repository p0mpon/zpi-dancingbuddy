import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


def user_thumbnail_upload_path(user, filename):
    """'thumbnails/users/user_1/<random>.jpg', relative to MEDIA_ROOT."""
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'thumbnails/users/user_{user.pk}/{uuid.uuid4().hex}.{extension}'


class User(AbstractUser):
    """USER table from db/diagram/v2.md (Django's fields + profile fields)."""

    thumbnail = models.ImageField(
        upload_to=user_thumbnail_upload_path,
        null=True,          # null = show the default picture
        blank=True,
    )
