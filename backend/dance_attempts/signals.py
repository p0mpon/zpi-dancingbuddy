"""
File cleanup when a DANCE_ATTEMPT row is deleted, however it's deleted (API, admin, bulk delete,
CASCADE from deleting its user). docs/api-decisions.md D6.7, D6.8.
"""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import DanceAttempt


@receiver(post_delete, sender=DanceAttempt)
def delete_recording_file(sender, instance, **kwargs):
    """Remove the recording once the deletion is committed (kept on rollback)."""
    if instance.recording:
        storage, name = instance.recording.storage, instance.recording.name
        transaction.on_commit(lambda: storage.delete(name))
