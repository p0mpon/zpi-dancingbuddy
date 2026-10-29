"""
Every write for videos goes through here: creating/updating/deleting rows and the
files on disk. Views validate the request with a serializer, then call one of these.

Plain functions with keyword-only arguments, so a call reads like a sentence:
upload_video(owner=user, title='Salsa', file=f). They know nothing about HTTP.

Analysis flow: upload (or a new file via PATCH) -> analysis_status 'pending' ->
start_analysis() after the transaction commits -> a worker fills json_analysis.
"""

from django.db import transaction
from django.utils import timezone

from .models import AnalysisStatus, Video


def start_analysis(*, video):
    """Queue the analysis of the video's file (videos/tasks.py, run by the Celery worker).

    Always called through transaction.on_commit, so the worker only starts once
    the row (and the file) is really saved.
    """
    # Imported here, not at the top: tasks.py imports this module.
    from .tasks import analyse_video
    analyse_video.delay(video.pk)


def set_analysis_result(*, video_id, file_name, status, json_analysis=None):
    """Write analysis_status (and json_analysis) for the analysis of file_name.

    Only writes if the video still exists and still has that file. Returns False
    if it doesn't (deleted, or a new file was uploaded via PATCH meanwhile).
    """
    # One UPDATE ... WHERE id = .. AND path_to_resource = .., so the check and the write
    # can't be split by a PATCH in between. .update() skips auto_now, so updated_at is set here.
    updated = Video.objects.filter(pk=video_id, path_to_resource=file_name).update(
        analysis_status=status,
        json_analysis=json_analysis,
        updated_at=timezone.now(),
    )
    return updated == 1


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
        # robust=True: if Redis is down, log the error instead of failing the request;
        # the video is already saved and stays 'pending'.
        transaction.on_commit(lambda: start_analysis(video=video), robust=True)
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
            transaction.on_commit(lambda: start_analysis(video=video), robust=True)
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
