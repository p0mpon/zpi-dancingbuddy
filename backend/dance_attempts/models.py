from pathlib import PurePosixPath

from django.db import models
from django.db.models import Q, CheckConstraint, Index
from django.contrib.auth import get_user_model
from videos.models import AnalysisError, AnalysisStatus, Video

User = get_user_model()

def attempt_upload_path(instance, filename):
    """
    Where the uploaded (raw) recording is saved, relative to MEDIA_ROOT:
    'dance_attempt/raw/<random>.<ext>'.
    """
    import uuid
    ext = filename.split('.')[-1]
    return f"dance_attempt/raw/{uuid.uuid4()}.{ext}"


def normalized_recording_path(raw_name):
    """
    Where the normalized copy of a recording goes, with the same name plus '_normalized':
    'dance_attempt/raw/abc.mov' -> 'dance_attempt/normalized/abc_normalized.mp4'.
    """
    return f"dance_attempt/normalized/{PurePosixPath(raw_name).stem}_normalized.mp4"

class DanceAttempt(models.Model):
    """
    Tracks a user's attempt at dancing to a reference video.
    
    Note on Large Fields: `json_analysis` and `score_details` can be large. 
    Use `.defer('json_analysis', 'score_details')` when querying lists of attempts.
    
    Note on reference_title: This is a snapshot.
    Renaming the original video later doesn't change this field on old attempts.
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dance_attempts')
    
    reference_video = models.ForeignKey(Video, on_delete=models.SET_NULL, null=True, related_name='attempts')
    reference_title = models.CharField(max_length=200)
    
    recording = models.FileField(upload_to=attempt_upload_path, null=True, blank=True)
    json_analysis = models.JSONField(null=True, blank=True) # NOTE: for now this is treated as the data gotten from mediapipe at creation
    
    score = models.IntegerField(null=True, blank=True)
    score_details = models.JSONField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=AnalysisStatus.choices, default=AnalysisStatus.PENDING)
    # Same three fields and rules as on Video (videos/models.py).
    analysis_error_code = models.PositiveSmallIntegerField(choices=AnalysisError.choices, null=True, blank=True)
    analysis_runs = models.PositiveSmallIntegerField(default=0)
    is_normalized = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        
        indexes = [
            Index(fields=['user', '-created_at']),
            Index(fields=['user', 'reference_video']),
        ]
        
        constraints = [
            CheckConstraint(
                condition=Q(status__in=AnalysisStatus.values),
                name='valid_status_choice'
            ),
            CheckConstraint(
                condition=Q(score__isnull=True) | (Q(score__gte=0) & Q(score__lte=100)),
                name='score_between_0_and_100'
            ),
            CheckConstraint(
                condition=(Q(status='done', score__isnull=False) | (~Q(status='done') & Q(score__isnull=True))),
                name='score_matches_status'
            ),
            CheckConstraint(
                condition=Q(analysis_error_code__in=AnalysisError.values),
                name='attempt_analysis_error_code_valid'
            ),
            CheckConstraint(
                condition=Q(analysis_error_code__isnull=True) | Q(status=AnalysisStatus.FAILED),
                name='attempt_analysis_error_code_only_when_failed'
            ),
        ]

    def __str__(self):
        return f"{self.user.nickname}'s attempt at {self.reference_title}"