from dance_attempts.exceptions import (
    AnalysisRunLimitReached,
    AttemptNotFailedError,
    VideoNotFoundError,
    VideoNotReadyError,
)
from dance_attempts.models import DanceAttempt, normalized_recording_path
from django.core.files import File
from django.db import transaction
from django.db.models import F, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from typing import Optional
from django.utils import timezone
from videos.models import MAX_ANALYSIS_RUNS, AnalysisStatus, Video


def start_attempt_analysis(*, attempt):
    """
    Queues the scoring analysis (run by Celery).
    Always called through transaction.on_commit.
    """
    from .tasks import analyse_attempt
    analyse_attempt.delay(attempt.pk)


def start_attempt_normalization(*, attempt):
    """Queues the re-encoding of the recording (run by Celery). Always called through transaction.on_commit."""
    from .tasks import normalize_attempt_recording
    normalize_attempt_recording.delay(attempt.pk)


def get_attempts_for_user_with_score_diffs(user, video_id=None):
    """
    Service method to fetch attempts with pre-calculated score diffs.
    Optionally filters by reference video id if provided.
    """
    # Subquery to find the previous score
    previous_score_subquery = DanceAttempt.objects.filter(
        user=OuterRef('user'),
        reference_video=OuterRef('reference_video'),
        created_at__lt=OuterRef('created_at'),
        score__isnull=False
    ).order_by('-created_at').values('score')[:1]

    # Subquery to find the best score so far
    best_score_subquery = DanceAttempt.objects.filter(
        user=OuterRef('user'),
        reference_video=OuterRef('reference_video'),
        created_at__lt=OuterRef('created_at'),
        score__isnull=False
    ).order_by('-score').values('score')[:1]

    queryset = DanceAttempt.objects.filter(user=user)

    if video_id is not None:
        queryset = queryset.filter(reference_video_id=video_id)

    return queryset.annotate(
        _prev_score=Subquery(previous_score_subquery),
        _best_score=Subquery(best_score_subquery),
        
        score_diff_previous=F('score') - F('_prev_score'),
        score_diff_best=F('score') - F('_best_score')
    )


def create_attempt(
        *, 
        user, 
        reference_video_id: int, 
        recording: Optional[File] = None,
        mediapipe_data: Optional[list] = None
    ) -> DanceAttempt:
    """
    Creates a DanceAttempt instance for the given user and reference video.
    Returns the created DanceAttempt object.
    Raises PermissionDenied if the user is not allowed to attempt the video.
    """
    # Enforce rule: Video must be public or belong to the user
    reference_video = get_object_or_404(
        Video, 
        id=reference_video_id
    )

    # Enforce rule: Video must be public or belong to the user
    if not reference_video.is_public and reference_video.owner != user:
        raise VideoNotFoundError("The video you want to attempt does not exist.")

    if reference_video.analysis_status != AnalysisStatus.DONE:
        raise VideoNotReadyError("The reference video is not analysed yet.")
    
    with transaction.atomic():
        attempt = DanceAttempt.objects.create(
            user=user,
            reference_video=reference_video,
            reference_title=reference_video.title, # Copy title on creation
            recording=recording,
            json_analysis=mediapipe_data,
            status=AnalysisStatus.PENDING
        )

        transaction.on_commit(
            lambda: start_attempt_analysis(attempt=attempt),
            robust=True
        )
        # Independent of the scoring: the score doesn't need the recording. Both start together.
        transaction.on_commit(
            lambda: start_attempt_normalization(attempt=attempt),
            robust=True
        )

    return attempt


def mark_attempt_processing(*, attempt_id: int) -> bool:
    """
    Begins a run: status PROCESSING, analysis_runs + 1, the old error code cleared.
    Returns False if the attempt is gone.
    """
    # Guarded by id only: scoring doesn't depend on the recording file.
    # F() is evaluated by the database, so two runs can't both read 2 and both write 3.
    updated_count = DanceAttempt.objects.filter(id=attempt_id).update(
        status=AnalysisStatus.PROCESSING,
        analysis_runs=F('analysis_runs') + 1,
        analysis_error_code=None,
        updated_at=timezone.now(),
    )
    return updated_count > 0


def update_attempt_recording(*, attempt_id: int, new_path) -> Optional[str]:
    """
    Moves the normalized file at new_path (a temp file) to dance_attempt/normalized/, points the
    attempt at it, sets is_normalized and deletes the original once the update is committed.
    Returns the new file name, or None if the attempt was deleted meanwhile (nothing is kept).
    """
    attempt = DanceAttempt.objects.filter(pk=attempt_id).first()
    if attempt is None:
        return None

    old_name = attempt.recording.name
    storage = attempt.recording.storage
    with open(new_path, 'rb') as source:
        new_name = storage.save(normalized_recording_path(old_name), File(source))

    updated_count = DanceAttempt.objects.filter(pk=attempt_id).update(
        recording=new_name,
        is_normalized=True,
        updated_at=timezone.now(),
    )
    if updated_count == 0:      # deleted between the read and the update
        storage.delete(new_name)
        return None

    # After the commit, so a rollback keeps the old file that the row still points to.
    transaction.on_commit(lambda: storage.delete(old_name), robust=True)
    return new_name


def set_attempt_result(
        *,
        attempt_id: int,
        status: AnalysisStatus,
        score: Optional[int] = None,
        score_details: Optional[dict] = None,
        error_code: Optional[int] = None,
    ) -> bool:
    """
    Updates the DanceAttempt after score analysis is complete (or with the error code of a failed run).
    Returns True if the update was successful, False otherwise.
    """
    updated_count = DanceAttempt.objects.filter(
        id=attempt_id
    ).update(
        status=status,
        score=score,
        score_details=score_details,
        analysis_error_code=error_code,
    )

    return updated_count > 0


def delete_attempt(*, attempt: DanceAttempt):
    """
    Permanently deletes a DanceAttempt. Only the row is deleted here: the recording file is
    removed after the commit by the post_delete signal in dance_attempts/signals.py, which also
    covers the admin, bulk deletes and CASCADE from deleting the user.

    Don't delete the file here as well: it would be gone even if the transaction rolled back
    (the row would then point to a missing file), and clearing `attempt.recording` first makes
    the signal skip its own cleanup.
    """
    attempt.delete()


def reanalyze_attempt(*, attempt: DanceAttempt) -> DanceAttempt:
    """
    Resets a failed attempt to PENDING and queues it for analysis again.
    Counts as a run like the automatic retries: analysis_runs is not reset.
    """
    if attempt.status != AnalysisStatus.FAILED:
        raise AttemptNotFailedError("Only failed attempts can be reanalyzed.")
    if attempt.analysis_runs >= MAX_ANALYSIS_RUNS:
        raise AnalysisRunLimitReached("The attempt has used all its analysis runs.")

    with transaction.atomic():
        attempt.status = AnalysisStatus.PENDING
        attempt.score = None
        attempt.score_details = None
        attempt.analysis_error_code = None

        attempt.save(update_fields=['status', 'score', 'score_details', 'analysis_error_code'])

        transaction.on_commit(
            lambda: start_attempt_analysis(attempt=attempt), 
            robust=True
        )

    return attempt