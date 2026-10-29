"""
Every write for videos goes through here: creating/updating/deleting rows and the
files on disk. Views validate the request with a serializer, then call one of these.

Plain functions with keyword-only arguments, so a call reads like a sentence:
upload_video(owner=user, title='Salsa', file=f). They know nothing about HTTP.
"""

from django.db import transaction

from .models import Video


def upload_video(*, owner, title, file, description=''):
    """Store the uploaded file and create its Video row. analysis_status defaults to pending."""
    # Saving the row writes the file first (FileField.pre_save -> storage.save, path from
    # video_upload_path), then runs the INSERT.
    # Known limitation: if the INSERT fails, the file stays on disk (orphaned).
    return Video.objects.create(
        owner=owner,
        title=title,
        description=description,
        path_to_resource=file,
        file_size=float(file.size),
    )


def update_video(*, video, **fields):
    """Change editable fields (title, description). Saves only what changed + updated_at."""
    if not fields:  # PATCH {}: nothing to write
        return video
    for name, value in fields.items():
        setattr(video, name, value)
    # 'updated_at' must be listed: with update_fields, auto_now is only written for listed fields.
    video.save(update_fields=[*fields, 'updated_at'])
    return video


def delete_video(*, video):
    """Delete the row, then the file, but only after the transaction commits."""
    # If the DB delete fails (or the transaction is rolled back), the file must still exist,
    # so the file is removed in an on_commit callback, not right away.
    # Known limitation: deleting a user CASCADE-deletes their rows but leaves their files.
    with transaction.atomic():
        storage = video.path_to_resource.storage
        name = video.path_to_resource.name
        video.delete()
        transaction.on_commit(lambda: storage.delete(name))
