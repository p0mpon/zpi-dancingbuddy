"""
Every write to VIDEO_LIKE goes through this file. Nothing here knows about HTTP.

The rule these services keep (db/diagram/v2.md): `Video.likes_count` changes only together with a
VIDEO_LIKE insert or delete, by exactly one, in the same transaction.

What these services do NOT do:
- They don't check visibility ("only public videos can be liked"). The caller (the DAN-141 library
  view) decides whether this user may like this video and passes in an already-allowed pair.
- They don't fix the counter when likes disappear by CASCADE. Deleting a user deletes their likes
  without decrementing `likes_count` on the videos they liked (accepted drift; the same happens when
  a like is deleted in the admin). A future worker will re-sync `likes_count` from VIDEO_LIKE.
"""

from django.db import transaction
from django.db.models import F

from videos.models import Video

from .models import VideoLike


def like_video(*, user, video) -> int:
    """
    `user` likes `video`. Returns the video's new likes_count.

    Idempotent: liking a video you already like changes nothing and returns the current count.
    The caller has already checked that `user` is allowed to like `video` (see the module docstring).
    """
    # atomic: the like row and the counter change are saved together, or neither is.
    with transaction.atomic():
        # get_or_create = "SELECT the row; if there is none, INSERT it". `created` says which happened.
        # If two identical requests arrive at once, both can miss on the SELECT and both try to INSERT.
        # The unique constraint lets only one through; get_or_create catches the IntegrityError of the
        # other one and SELECTs the row again, so that request gets created=False instead of an error.
        _, created = VideoLike.objects.get_or_create(user=user, video=video)

        if created:
            # F('likes_count') + 1 becomes SQL: UPDATE ... SET likes_count = likes_count + 1.
            # The database does the +1 on the value it has right now. With `video.likes_count += 1;
            # video.save()` two users liking at once would both read 5 and both write 6: one like lost.
            # .update() also leaves Video.updated_at alone (auto_now only fires on save()), which is
            # what we want: a like isn't an edit of the video.
            Video.objects.filter(pk=video.pk).update(likes_count=F('likes_count') + 1)

        # The object in memory still holds the old number; read the real one back from the database.
        video.refresh_from_db(fields=['likes_count'])

    return video.likes_count


def unlike_video(*, user, video) -> int:
    """
    `user` takes their like off `video`. Returns the video's new likes_count.

    Idempotent: unliking a video you don't like changes nothing and returns the current count.
    The caller has already checked that `user` is allowed to see `video` (see the module docstring).
    """
    with transaction.atomic():
        # .delete() on a queryset returns (total rows deleted, {model: rows}). We only need the
        # total: 1 if the like existed, 0 if it didn't. If two identical requests arrive at once,
        # only one of them deletes the row, so only one of them decrements.
        deleted, _ = VideoLike.objects.filter(user=user, video=video).delete()

        if deleted:
            # Same reason for F() as in like_video. Only runs when a row was really deleted, so the
            # counter can't go below zero here (and the check constraint on Video would refuse it).
            Video.objects.filter(pk=video.pk).update(likes_count=F('likes_count') - 1)

        video.refresh_from_db(fields=['likes_count'])

    return video.likes_count
