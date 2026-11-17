"""
The like a user puts on a video (table VIDEO_LIKE in db/diagram/v2.md).

Dependency direction: `likes` imports from `videos`, never the other way round. `videos/models.py`
must not import anything from this app, or Python would hit a circular import.

Rows are written only by likes/services.py (like_video / unlike_video), because every insert or
delete here must also move `Video.likes_count` by one.
"""

from django.conf import settings
from django.db import models


class VideoLike(models.Model):
    """VIDEO_LIKE table from db/diagram/v2.md: one row = one user likes one video."""

    # int id: Django adds it automatically, nothing to write
    user = models.ForeignKey(                       # int user_id
        settings.AUTH_USER_MODEL,                   # the string 'accounts.User', so no import of the User class
        on_delete=models.CASCADE,                   # deleting the user deletes their likes
        related_name='video_likes',                 # user.video_likes.all()
    )
    video = models.ForeignKey(                      # int video_id
        'videos.Video',                             # a string instead of the class: Django resolves it later
        on_delete=models.CASCADE,                   # deleting the video deletes its likes
        related_name='likes',                       # video.likes.all()
    )
    created_at = models.DateTimeField(auto_now_add=True)    # set once on insert; the liked list sorts by it

    class Meta:
        ordering = ['-created_at']      # newest like first
        constraints = [
            # One like per (user, video). The database refuses a second row for the same pair,
            # even if two requests arrive at the same moment.
            models.UniqueConstraint(
                fields=['user', 'video'],
                name='video_like_unique_user_video',
            ),
        ]
        indexes = [
            # "The videos I liked, newest first" (DAN-141 liked list).
            # No other index is needed: the unique constraint above is already an index starting
            # with `user`, and Django indexes every ForeignKey (so `video`) on its own.
            models.Index(fields=['user', '-created_at'], name='video_like_user_newest_idx'),
        ]

    def __str__(self):
        # nickname is the public name; username is private (sign-in only)
        return f'{self.user.nickname} likes {self.video.title}'
