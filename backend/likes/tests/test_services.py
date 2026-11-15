"""Tests for like_video / unlike_video: the VideoLike row and Video.likes_count always move together."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from likes.models import VideoLike
from likes.services import like_video, unlike_video
from videos.models import Video


class LikeServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', nickname='owner_nick')
        self.user = User.objects.create_user(username='dancer', nickname='dancer_nick')
        self.other_user = User.objects.create_user(username='other', nickname='other_nick')
        # A dummy path string is enough: these tests never open the file.
        self.video = Video.objects.create(
            owner=self.owner,
            title='Fancy',
            path_to_resource='videos/fancy.mp4',
            file_size=100,
        )

    def stored_likes_count(self):
        """likes_count as it is in the database, not on the self.video object in memory."""
        return Video.objects.get(pk=self.video.pk).likes_count

    # ==== like

    def test_like_creates_row_and_increments_count(self):
        result = like_video(user=self.user, video=self.video)

        self.assertEqual(result, 1)
        self.assertEqual(VideoLike.objects.filter(user=self.user, video=self.video).count(), 1)
        self.assertEqual(self.stored_likes_count(), 1)
        # The object passed in is refreshed too.
        self.assertEqual(self.video.likes_count, 1)

    def test_like_twice_is_idempotent(self):
        like_video(user=self.user, video=self.video)
        result = like_video(user=self.user, video=self.video)

        self.assertEqual(result, 1)
        self.assertEqual(VideoLike.objects.count(), 1)
        self.assertEqual(self.stored_likes_count(), 1)

    def test_two_users_like(self):
        like_video(user=self.user, video=self.video)
        result = like_video(user=self.other_user, video=self.video)

        self.assertEqual(result, 2)
        self.assertEqual(VideoLike.objects.count(), 2)
        self.assertEqual(self.stored_likes_count(), 2)

    def test_owner_can_like_own_video(self):
        result = like_video(user=self.owner, video=self.video)

        self.assertEqual(result, 1)

    def test_like_only_touches_that_video(self):
        second_video = Video.objects.create(
            owner=self.owner, title='Feel Special', path_to_resource='videos/feel.mp4', file_size=100,
        )

        like_video(user=self.user, video=self.video)

        self.assertEqual(Video.objects.get(pk=second_video.pk).likes_count, 0)

    def test_like_uses_database_value_not_stale_object(self):
        # Two requests each load their own copy of the video while likes_count is still 0.
        first_copy = Video.objects.get(pk=self.video.pk)
        second_copy = Video.objects.get(pk=self.video.pk)

        like_video(user=self.user, video=first_copy)
        # second_copy.likes_count is still 0 in memory; F() makes the database add to its own value.
        result = like_video(user=self.other_user, video=second_copy)

        self.assertEqual(result, 2)
        self.assertEqual(self.stored_likes_count(), 2)

    def test_like_does_not_change_updated_at(self):
        updated_at_before = Video.objects.get(pk=self.video.pk).updated_at

        like_video(user=self.user, video=self.video)

        self.assertEqual(Video.objects.get(pk=self.video.pk).updated_at, updated_at_before)

    # ==== unlike

    def test_unlike_deletes_row_and_decrements_count(self):
        like_video(user=self.user, video=self.video)

        result = unlike_video(user=self.user, video=self.video)

        self.assertEqual(result, 0)
        self.assertEqual(VideoLike.objects.count(), 0)
        self.assertEqual(self.stored_likes_count(), 0)

    def test_unlike_twice_never_goes_negative(self):
        like_video(user=self.user, video=self.video)
        unlike_video(user=self.user, video=self.video)

        result = unlike_video(user=self.user, video=self.video)

        self.assertEqual(result, 0)
        self.assertEqual(self.stored_likes_count(), 0)

    def test_unlike_never_liked_is_a_no_op(self):
        result = unlike_video(user=self.user, video=self.video)

        self.assertEqual(result, 0)
        self.assertEqual(self.stored_likes_count(), 0)

    def test_unlike_removes_only_that_users_like(self):
        like_video(user=self.user, video=self.video)
        like_video(user=self.other_user, video=self.video)

        result = unlike_video(user=self.user, video=self.video)

        self.assertEqual(result, 1)
        self.assertEqual(list(VideoLike.objects.values_list('user_id', flat=True)), [self.other_user.pk])

    def test_like_again_after_unlike(self):
        like_video(user=self.user, video=self.video)
        unlike_video(user=self.user, video=self.video)

        result = like_video(user=self.user, video=self.video)

        self.assertEqual(result, 1)
        self.assertEqual(VideoLike.objects.count(), 1)

    # ==== accepted drift (DAN-110 context §4.3)

    def test_deleting_user_deletes_likes_but_does_not_decrement(self):
        like_video(user=self.user, video=self.video)
        like_video(user=self.other_user, video=self.video)

        self.other_user.delete()

        # CASCADE removed the row without going through unlike_video, so the counter is now one
        # too high. Documented and accepted: a future worker re-syncs likes_count from VIDEO_LIKE.
        self.assertEqual(VideoLike.objects.filter(video=self.video).count(), 1)
        self.assertEqual(self.stored_likes_count(), 2)
