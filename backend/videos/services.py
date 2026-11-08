"""
Every write for videos goes through here: creating/updating/deleting rows and the
files on disk. Views validate the request with a serializer, then call one of these.

Plain functions with keyword-only arguments, so a call reads like a sentence:
upload_video(owner=user, title='Salsa', file=f). They know nothing about HTTP.

Analysis flow: upload -> analysis_status 'pending' ->
start_analysis() after the transaction commits -> a worker fills json_analysis.
"""

from django.db import transaction
from django.utils import timezone

from .media_info import read_duration_seconds
from .models import AnalysisStatus, Video, Visibility


class VideoServiceError(Exception):
    """A rule in services.py refused the operation. Views turn it into 409."""


class VideoNotPublishable(VideoServiceError):
    """update_video(): publishing needs a finished analysis and a difficulty."""


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
    if it doesn't (deleted meanwhile).
    """
    # One UPDATE ... WHERE id = .. AND path_to_resource = .., so the check and the write
    # can't be split by a delete in between. .update() skips auto_now, so updated_at is set here.
    updated = Video.objects.filter(pk=video_id, path_to_resource=file_name).update(
        analysis_status=status,
        json_analysis=json_analysis,
        updated_at=timezone.now(),
    )
    return updated == 1


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
    """Delete the row, then the file, but only after the transaction commits."""
    # If the DB delete fails (or the transaction is rolled back), the file must still exist,
    # so the file is removed in an on_commit callback, not right away.
    # Known limitation: deleting a user CASCADE-deletes their rows but leaves their files.
    with transaction.atomic():
        storage = video.path_to_resource.storage
        name = video.path_to_resource.name
        video.delete()
        transaction.on_commit(lambda: storage.delete(name))

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