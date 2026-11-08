from django.db import models
from django.db.models import Q, CheckConstraint, Index
from django.contrib.auth import get_user_model
from videos.models import Video, AnalysisStatus

User = get_user_model()

def attempt_upload_path(instance, filename):
    """
    Determines where the recording file is saved.
    """
    import uuid
    ext = filename.split('.')[-1]
    return f"attempts/user_{instance.user.id}/{uuid.uuid4()}.{ext}"

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
    json_analysis = models.JSONField(null=True, blank=True) # NOTE: is it needed?
    
    score = models.IntegerField(null=True, blank=True)
    score_details = models.JSONField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=AnalysisStatus.choices, default=AnalysisStatus.PENDING)
    
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
            )
        ]

    def __str__(self):
        return f"{self.user.username}'s attempt at {self.reference_title}"