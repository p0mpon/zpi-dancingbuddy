import uuid

from django.conf import settings
from django.db import models


def video_upload_path(video, filename):
    """Where the uploaded file is stored, relative to MEDIA_ROOT: 'videos/user_1/<random>.mp4'."""
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'videos/user_{video.owner_id}/{uuid.uuid4().hex}.{extension}'


class AnalysisStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'                  # uploaded, waiting for a worker
    PROCESSING = 'processing', 'Processing'         # a Celery worker is analysing it
    DONE = 'done', 'Done'                           # json_analysis is filled
    FAILED = 'failed', 'Failed'                     # analysis crashed; can be re-run


class Video(models.Model):
    """VIDEO table from db/diagram/v1.md."""

    # int id: Django adds it automatically, nothing to write
    title = models.CharField(max_length=200)                        # string title
    description = models.CharField(max_length=500, blank=True)      # string description
    owner = models.ForeignKey(                                      # int owner_id
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='videos',
    )
    path_to_resource = models.FileField(upload_to=video_upload_path)  # string path_to_resource
    file_size = models.FloatField()                             # float file_size
    json_analysis = models.JSONField(null=True, blank=True)     # json json_analysis (null = not analysed yet)
    analysis_status = models.CharField(                         # string analysis_status
        max_length=20,
        choices=AnalysisStatus,
        default=AnalysisStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)        # date created_at
    updated_at = models.DateTimeField(auto_now=True)            # date updated_at

    class Meta:
        ordering = ['-created_at']      # newest first
        constraints = [
            models.CheckConstraint(     # file size >= 0
                condition=models.Q(file_size__gte=0),
                name='video_file_size_non_negative',
            ),
            models.CheckConstraint(     # statuses
                condition=models.Q(analysis_status__in=AnalysisStatus.values),
                name='video_analysis_status_valid',
            ),
        ]

    def __str__(self):
        return self.title

    # ==== USEFUL FEATURES

    @property
    def is_pending(self):
        return self.analysis_status == AnalysisStatus.PENDING

    @property
    def is_processing(self):
        return self.analysis_status == AnalysisStatus.PROCESSING

    @property
    def is_analysed(self):
        return self.analysis_status == AnalysisStatus.DONE

    @property
    def is_failed(self):
        return self.analysis_status == AnalysisStatus.FAILED