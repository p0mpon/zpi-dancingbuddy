from typing import Optional, Any
from django.core.exceptions import PermissionDenied
from django.core.files import File
from dance_attempts.models import DanceAttempt
from videos.models import AnalysisStatus, Video

def create_attempt(
        *, 
        user, 
        reference_video: Video, 
        recording: Optional[File] = None
    ) -> DanceAttempt:
    """
    Creates a DanceAttempt instance for the given user and reference video.
    Returns the created DanceAttempt object.
    Raises PermissionDenied if the user is not allowed to attempt the video.
    """
    # Enforce rule: Video must be public or belong to the user
    if not reference_video.is_public and reference_video.owner != user:
        raise PermissionDenied("You cannot attempt a private video that isn't yours.")
        
    attempt = DanceAttempt.objects.create(
        user=user,
        reference_video=reference_video,
        reference_title=reference_video.title, # Copy title on creation
        recording=recording,
        status=AnalysisStatus.PENDING
    )

    return attempt

def set_attempt_result(
        *, 
        attempt_id: int, 
        file_name: str, 
        status: AnalysisStatus, 
        score: Optional[int] = None, 
        json_analysis: Optional[dict] = None, 
        score_details: Optional[dict] = None
    ):
    """
    Updates the DanceAttempt after score analysis is complete.
    Returns True if the update was successful, False otherwise.
    """
    # Only update if the id matches and the recording matches the file_name
    updated_count = DanceAttempt.objects.filter(
        id=attempt_id,
        recording=file_name
    ).update(
        status=status,
        score=score,
        json_analysis=json_analysis,
        score_details=score_details
    )

    return updated_count > 0