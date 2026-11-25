"""
Every write for videos goes through here: creating/updating/deleting rows and the
files on disk. Views validate the request with a serializer, then call one of these.

Plain functions with keyword-only arguments, so a call reads like a sentence:
upload_video(owner=user, title='Salsa', file=f). They know nothing about HTTP.

Analysis flow: upload -> analysis_status 'pending' ->
start_analysis() after the transaction commits -> a worker normalizes the file, makes the thumbnail
and fills json_analysis (videos/tasks.py). The worker's steps write through the functions below.
"""

import os

from django.core.files import File
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from core.ffmpeg import read_duration_seconds
from .models import MAX_ANALYSIS_RUNS, AnalysisStatus, Video, Visibility, normalized_video_path


class VideoServiceError(Exception):
    """A rule in services.py refused the operation. Views turn it into 409."""


class VideoNotPublishable(VideoServiceError):
    """update_video(): publishing needs a finished analysis and a difficulty."""


class VideoNotFailed(VideoServiceError):
    """reanalyze_video(): only a failed analysis can be run again."""


class AnalysisRunLimitReached(VideoServiceError):
    """reanalyze_video(): the video has already used all MAX_ANALYSIS_RUNS runs."""


def start_analysis(*, video):
    """Queue the analysis of the video's file (videos/tasks.py, run by the Celery worker).

    Always called through transaction.on_commit, so the worker only starts once
    the row (and the file) is really saved.
    """
    # Imported here, not at the top: tasks.py imports this module.
    from .tasks import normalize_video_file
    normalize_video_file.delay(video.pk)


def mark_video_processing(*, video_id):
    """Begin a run: status 'processing', analysis_runs + 1, the old error code cleared.

    Returns False if the video is gone.
    """
    # F('analysis_runs') + 1 is evaluated by the database inside the UPDATE, so two runs can't
    # both read 2 and both write 3. .update() skips auto_now, so updated_at is set here.
    updated = Video.objects.filter(pk=video_id).update(
        analysis_status=AnalysisStatus.PROCESSING,
        analysis_runs=F('analysis_runs') + 1,
        analysis_error_code=None,
        updated_at=timezone.now(),
    )
    return updated == 1


def set_analysis_result(*, video_id, status, json_analysis=None, error_code=None):
    """Write analysis_status (and json_analysis, or the error code of a failed run).

    Returns False if the video is gone (deleted meanwhile).
    """
    updated = Video.objects.filter(pk=video_id).update(
        analysis_status=status,
        json_analysis=json_analysis,
        analysis_error_code=error_code,
        updated_at=timezone.now(),
    )
    return updated == 1




def update_video_file(*, video_id, new_path):
    """Move the normalized file at new_path (a temp file) to videos/normalized/, point the video at it
    and delete the original once the update is committed.

    Updates path_to_resource, file_size, duration_seconds and is_normalized in one UPDATE.
    Returns the new file name, or None if the video was deleted meanwhile (nothing is kept).
    """
    video = Video.objects.only('path_to_resource').filter(pk=video_id).first()
    if video is None:
        return None

    old_name = video.path_to_resource.name
    storage = video.path_to_resource.storage
    with open(new_path, 'rb') as source:
        new_name = storage.save(normalized_video_path(old_name), File(source))

    updated = Video.objects.filter(pk=video_id).update(
        path_to_resource=new_name,
        file_size=float(os.path.getsize(new_path)),
        duration_seconds=read_duration_seconds(new_path),
        is_normalized=True,
        updated_at=timezone.now(),
    )
    if updated == 0:    # deleted between the read and the update: don't leave the new file behind
        storage.delete(new_name)
        return None
    # After the commit, so a rollback keeps the old file that the row still points to.
    transaction.on_commit(lambda: storage.delete(old_name), robust=True)
    return new_name


def set_video_thumbnail(*, video_id, thumbnail):
    """Store `thumbnail` (a WebP ContentFile) as the video's thumbnail, if it has none yet.

    Returns False if the video is gone or already has a thumbnail: the saved image is then removed again.
    """
    video = Video.objects.only('owner_id').filter(pk=video_id).first()
    if video is None:
        return False

    field = Video._meta.get_field('thumbnail')
    storage = field.storage
    # The column can hold NULL or '' for "no thumbnail", depending on how the row was created.
    no_thumbnail = Q(thumbnail__isnull=True) | Q(thumbnail='')
    new_name = storage.save(field.generate_filename(video, thumbnail.name), thumbnail)

    updated = Video.objects.filter(no_thumbnail, pk=video_id).update(
        thumbnail=new_name,
        updated_at=timezone.now(),
    )
    if updated == 0:
        storage.delete(new_name)
    return updated == 1


def reanalyze_video(*, video):
    """Run the analysis of a failed video again: status 'pending', error code cleared, task queued.

    Counts as a run like the automatic retries: analysis_runs is not reset.
    """
    if not video.is_failed:
        raise VideoNotFailed('Only a failed video can be analysed again.')
    if video.analysis_runs >= MAX_ANALYSIS_RUNS:
        raise AnalysisRunLimitReached('The video has used all its analysis runs.')

    with transaction.atomic():
        video.analysis_status = AnalysisStatus.PENDING
        video.analysis_error_code = None
        video.save(update_fields=['analysis_status', 'analysis_error_code', 'updated_at'])
        transaction.on_commit(lambda: start_analysis(video=video), robust=True)
    return video


def upload_video(*, owner, title, file, description='', song_author='', song_title='', difficulty=None):
    """Store the uploaded file, create its Video row (analysis_status 'pending') and queue the analysis."""
    # Saving the row writes the file first (FileField.pre_save -> storage.save, path from
    # video_upload_path), then runs the INSERT.
    # Known limitation: if the INSERT fails, the file stays on disk (orphaned).
    with transaction.atomic():
        video = Video.objects.create(
            owner=owner,
            title=title,
            description=description,
            song_author=song_author,
            song_title=song_title,
            difficulty=difficulty,
            path_to_resource=file,
            file_size=float(file.size),
        )
        duration = read_duration_seconds(video.path_to_resource.path)
        if duration is not None:
            video.duration_seconds = duration
            # Part of creating the row, so updated_at is left out on purpose (stays == created_at).
            video.save(update_fields=['duration_seconds'])
        # robust=True: if Redis is down, log the error instead of failing the request;
        # the video is already saved and stays 'pending'.
        transaction.on_commit(lambda: start_analysis(video=video), robust=True)
    return video


def update_video(*, video, **fields):
    """Change editable fields (title, description, song_author, song_title, difficulty, visibility).

    A new visibility also sets published_at. All rules are checked before anything
    changes, then everything is written in one UPDATE.
    The file can't be changed: to use a different file, delete the video and upload a new one.
    """

    if fields.get('visibility') == video.visibility:
        del fields['visibility']  # sent, but it's already this value: not a change

    if not fields:           # PATCH {}, or nothing really changes
        return video

    visibility = fields.pop('visibility', None)     # out of the generic fields (see docstring)

    if visibility is not None:  # a real change (same value was removed above)
        if visibility == Visibility.PUBLIC:
            if not video.is_analysed:
                raise VideoNotPublishable('The video must be analysed before it can be published.')
            fields.update({'visibility': visibility, 'published_at': timezone.now()})  # publish: both together (constraint)
        else:   # Unpublish video
            fields.update({'visibility': visibility, 'published_at': None})     # unpublish

    # Checked on the values the video WILL have after this update.
    video_ends_public = fields.get('visibility', video.visibility) == Visibility.PUBLIC
    if video_ends_public and fields.get('difficulty', video.difficulty) is None:
        raise VideoNotPublishable('A public video needs a difficulty.')

    for name, value in fields.items():
        setattr(video, name, value)
    # 'updated_at' must be listed: with update_fields, auto_now is only written for listed fields.
    video.save(update_fields=[*fields, 'updated_at'])
    return video


def delete_video(*, video):
    """Delete the row. The file (and thumbnail) is removed after the commit by the post_delete
    signal in videos/signals.py, which also covers the admin, bulk deletes and deleting the owner."""
    video.delete()

#   ENDPOINTS not used - use regular PATCH for visibility
#
# def publish_video(*, video):
#     """Make the video public (shown in the library). Needs a finished analysis and a difficulty."""
#     if video.is_public:                 # already public: nothing to do, keep the original date
#         return video
#     if not video.is_analysed:
#         raise VideoNotPublishable('The video must be analysed before it can be published.')
#     if video.difficulty is None:
#         raise VideoNotPublishable('Set a difficulty before publishing.')
#
#     video.visibility = Visibility.PUBLIC
#     video.published_at = timezone.now()
#     video.save(update_fields=['visibility', 'published_at', 'updated_at'])
#     return video
#
#
# def unpublish_video(*, video):
#     """Make the video private again. Likes stay (v2 rule); likes_count is not touched."""
#     if not video.is_public:
#         return video
#     video.visibility = Visibility.PRIVATE
#     video.published_at = None
#     video.save(update_fields=['visibility', 'published_at', 'updated_at'])
#     return video