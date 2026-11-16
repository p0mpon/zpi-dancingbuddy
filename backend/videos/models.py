import uuid

from django.conf import settings
from django.db import models



def video_thumbnail_upload_path(video, filename):
    """'thumbnails/videos/user_1/<random>.jpg', relative to MEDIA_ROOT."""
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'thumbnails/videos/user_{video.owner_id}/{uuid.uuid4().hex}.{extension}'

def video_upload_path(video, filename):
    """Where the uploaded file is stored, relative to MEDIA_ROOT: 'videos/user_1/<random>.mp4'."""
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'videos/user_{video.owner_id}/{uuid.uuid4().hex}.{extension}'

class Visibility(models.TextChoices):
    PRIVATE = 'private', 'Private'      # only the owner sees it (default)
    PUBLIC = 'public', 'Public'         # shown in the library


class Difficulty(models.TextChoices):
    BEGINNER = 'beginner', 'Beginner'
    INTERMEDIATE = 'intermediate', 'Intermediate'
    ADVANCED = 'advanced', 'Advanced'

class AnalysisStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'                  # uploaded, waiting for a worker
    PROCESSING = 'processing', 'Processing'         # a Celery worker is analyzing it
    DONE = 'done', 'Done'                           # json_analysis is filled
    FAILED = 'failed', 'Failed'                     # analysis crashed; can be re-run


class VideoQuerySet(models.QuerySet):
    """Who may see which video. The rule is written once here and reused by every view.

    Attached to the model as `objects = VideoQuerySet.as_manager()`, so these methods chain like
    any other queryset method: `Video.objects.visible_to(user).filter(difficulty='beginner')`.
    """

    # "In the public library": published, and the owner isn't blocked (is_active).
    # A Q object is a condition that isn't attached to a query yet, so it can be reused and OR-ed.
    IS_PUBLIC = models.Q(visibility=Visibility.PUBLIC, owner__is_active=True)

    def owned_by(self, user):
        """`user`'s own uploads, private and public (/api/videos/, library scope=mine)."""
        return self.filter(owner=user)

    def public(self):
        """The public library only (what can be liked)."""
        return self.filter(self.IS_PUBLIC)

    def visible_to(self, user):
        """Everything `user` may open: the public library plus all their own videos.

        `user` is request.user, so it can be a visitor who isn't logged in (Django's AnonymousUser).
        A visitor owns nothing and sees the public library only (docs/api-decisions.md D7.6).
        """
        if not user.is_authenticated:
            # AnonymousUser is not a row in the database, so `owner=user` can't be put in a query.
            return self.public()
        # `|` is OR. Two chained .filter() calls would mean AND, which is why Q is needed here.
        return self.filter(self.IS_PUBLIC | models.Q(owner=user))


class Video(models.Model):
    """VIDEO table from db/diagram/v2.md."""

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
    json_analysis = models.JSONField(null=True, blank=True)     # JSON json_analysis (null = not analyzed yet)
    analysis_status = models.CharField(                         # string analysis_status
        max_length=20,
        choices=AnalysisStatus,
        default=AnalysisStatus.PENDING,
    )
    visibility = models.CharField(                              # string visibility
        max_length=20,
        choices=Visibility,
        default=Visibility.PRIVATE,
    )
    published_at = models.DateTimeField(null=True, blank=True)  # null while private
    difficulty = models.CharField(                              # null until the owner sets it
        max_length=20,
        choices=Difficulty,
        null=True,
        blank=True,
    )
    duration_seconds = models.FloatField(null=True, blank=True) # read on upload (ffprobe), null if unreadable
    thumbnail = models.ImageField(                              # null until generated
        upload_to=video_thumbnail_upload_path,
        null=True,
        blank=True,
    )
    song_author = models.CharField(max_length=200, blank=True, default='')  # typed by the user
    song_title = models.CharField(max_length=200, blank=True, default='')
    likes_count = models.IntegerField(default=0)                # kept in sync with VIDEO_LIKE

    created_at = models.DateTimeField(auto_now_add=True)        # date created_at
    updated_at = models.DateTimeField(auto_now=True)            # date updated_at

    # Video.objects is still the normal manager, plus the VideoQuerySet methods above.
    objects = VideoQuerySet.as_manager()

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
            models.CheckConstraint(
                condition=models.Q(visibility__in=Visibility.values),
                name='video_visibility_valid',
            ),
            models.CheckConstraint(  # published_at is set  <=>  public
                condition=(
                        models.Q(visibility=Visibility.PUBLIC, published_at__isnull=False)
                        | models.Q(visibility=Visibility.PRIVATE, published_at__isnull=True)
                ),
                name='video_published_at_iff_public',
            ),
            models.CheckConstraint(  # NULL passes automatically (see below)
                condition=models.Q(difficulty__in=Difficulty.values),
                name='video_difficulty_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(duration_seconds__gte=0),
                name='video_duration_seconds_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(likes_count__gte=0),
                name='video_likes_count_non_negative',
            ),
        ]
        indexes = [
            models.Index(fields=['visibility', '-published_at'], name='video_library_newest_idx'),
            models.Index(fields=['visibility', '-likes_count'], name='video_library_likes_idx'),
            models.Index(fields=['difficulty'], name='video_difficulty_idx'),
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

    @property
    def is_public(self):
        return self.visibility == Visibility.PUBLIC