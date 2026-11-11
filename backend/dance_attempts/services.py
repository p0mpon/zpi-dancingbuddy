from dance_attempts.models import DanceAttempt
from django.core.files import File
from django.db import transaction
from django.db.models import F, OuterRef, Subquery, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from typing import Optional
from videos.models import AnalysisStatus, Video


class VideoNotReadyError(Exception):
    """Raised when a video is not ready for analysis."""


def start_attempt_analysis(*, attempt):
    """
    Queues the scoring analysis (run by Celery).
    Always called through transaction.on_commit.
    """
    from .tasks import analyse_attempt
    analyse_attempt.delay(attempt.pk)


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
        raise Http404("The video you want to attempt does not exist.")

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

    return attempt


def set_attempt_result(
        *, 
        attempt_id: int, 
        status: AnalysisStatus, 
        score: Optional[int] = None, 
        score_details: Optional[dict] = None
    ):
    """
    Updates the DanceAttempt after score analysis is complete.
    Returns True if the update was successful, False otherwise.
    """
    updated_count = DanceAttempt.objects.filter(
        id=attempt_id
    ).update(
        status=status,
        score=score,
        score_details=score_details
    )

    return updated_count > 0


def delete_attempt(*, attempt: DanceAttempt):
    """
    Permanently deletes a DanceAttempt and its associated physical recording file.
    """
    if attempt.recording:
        attempt.recording.delete(save=False)
        
    attempt.delete()