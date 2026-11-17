"""
Admin page for likes.

Careful: adding or deleting a like here does NOT change `Video.likes_count`. The admin writes
VideoLike rows directly and skips likes/services.py, which is the only code that moves the counter.
It's the same accepted drift as deleting a user (see likes/services.py); a future worker will
re-sync `likes_count` from VIDEO_LIKE.
"""

from django.contrib import admin

from .models import VideoLike


@admin.register(VideoLike)
class VideoLikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'video', 'created_at')
    # The list shows str(user) and str(video) for every row. select_related fetches both with a
    # JOIN in the list query, instead of two extra queries per row.
    list_select_related = ('user', 'video')
    search_fields = ('user__nickname', 'video__title')
