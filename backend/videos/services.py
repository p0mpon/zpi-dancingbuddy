"""
Every write for videos goes through here: creating/updating/deleting rows and the
files on disk. Views validate the request with a serializer, then call one of these.

Plain functions with keyword-only arguments, so a call reads like a sentence:
upload_video(owner=user, title='Salsa', file=f). They know nothing about HTTP.

Analysis flow: upload (or a new file via PATCH) -> analysis_status 'pending' ->
start_analysis() after the transaction commits -> a worker fills json_analysis.
"""

from django.db import transaction

from .models import AnalysisStatus, Video


def start_analysis(*, video):
    """Queue the analysis of the video's file.

    Always called through transaction.on_commit, so the worker only starts once
    the row (and the file) is really saved.
    """
    # TODO: queue the Celery task (separate ticket), e.g. analyse_video.delay(video.pk).
    # The task sets 'processing', writes json_analysis, then sets 'done' or 'failed'.


def upload_video(*, owner, title, file, description=''):
    """Store the uploaded file, create its Video row (analysis_status 'pending') and queue the analysis."""
    # Saving the row writes the file first (FileField.pre_save -> storage.save, path from
    # video_upload_path), then runs the INSERT.
    # Known limitation: if the INSERT fails, the file stays on disk (orphaned).
    with transaction.atomic():
        video = Video.objects.create(
            owner=owner,
            title=title,
            description=description,
            path_to_resource=file,
            file_size=float(file.size),
        )
        transaction.on_commit(lambda: start_analysis(video=video))
    return video


def update_video(*, video, file=None, **fields):
    """Change editable fields (title, description) and optionally replace the file.

    A new file throws away the old analysis and queues a new one; the old file is
    deleted after the transaction commits. Saves only what changed + updated_at.
    """
    if file is None and not fields:  # PATCH {}: nothing to write
        return video

    for name, value in fields.items():
        setattr(video, name, value)
    # 'updated_at' must be listed: with update_fields, auto_now is only written for listed fields.
    update_fields = [*fields, 'updated_at']

    if file is not None:
        old_storage = video.path_to_resource.storage
        old_name = video.path_to_resource.name
        video.path_to_resource = file           # saved under a new name on save()
        video.file_size = float(file.size)
        video.json_analysis = None              # the old analysis belongs to the old file
        video.analysis_status = AnalysisStatus.PENDING
        update_fields += ['path_to_resource', 'file_size', 'json_analysis', 'analysis_status']

    with transaction.atomic():
        video.save(update_fields=update_fields)
        if file is not None:
            transaction.on_commit(lambda: old_storage.delete(old_name))
            transaction.on_commit(lambda: start_analysis(video=video))
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
