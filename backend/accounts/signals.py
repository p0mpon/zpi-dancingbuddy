"""
File cleanup when a USER row is deleted, however it's deleted (API, admin, shell, bulk delete).
The user's videos and attempts are removed by CASCADE; their files go via the signals in
videos/signals.py and dance_attempts/signals.py (Django sends post_delete for every cascaded row).
"""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import User


@receiver(post_delete, sender=User)
def delete_avatar_file(sender, instance, **kwargs):
    """Remove the avatar once the deletion is committed (on rollback the row, and its file, stay)."""
    if instance.avatar:
        storage, name = instance.avatar.storage, instance.avatar.name
        transaction.on_commit(lambda: storage.delete(name))
