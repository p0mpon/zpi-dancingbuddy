"""
File cleanup when a VIDEO row is deleted, however it's deleted: services.delete_video(), the admin,
bulk `.delete()`, or CASCADE from deleting its owner (cleanups.md, "Orphaned files when a user is
deleted"). This is the only place video files are deleted; services.delete_video() just deletes the row.
"""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Video


@receiver(post_delete, sender=Video)
def delete_video_files(sender, instance, **kwargs):
    """Remove the video file and its thumbnail once the deletion is committed (kept on rollback)."""
    for field_file in (instance.path_to_resource, instance.thumbnail):
        if field_file:
            storage, name = field_file.storage, field_file.name
            transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
