"""Tests for the VideoLike model: constraint, CASCADE, related names. No services here."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from likes.models import VideoLike
from videos.models import Video


class VideoLikeModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='dancer', nickname='dancer_nick')
        self.other_user = User.objects.create_user(username='other', nickname='other_nick')
        # A dummy path string is enough: these tests never open the file.
        self.video = Video.objects.create(
            owner=self.user,
            title='Fancy',
            path_to_resource='videos/fancy.mp4',
            file_size=100,
        )

    def test_created_at_is_set(self):
        like = VideoLike.objects.create(user=self.user, video=self.video)

        self.assertIsNotNone(like.created_at)

    def test_str_uses_nickname_not_username(self):
        like = VideoLike.objects.create(user=self.user, video=self.video)

        self.assertEqual(str(like), 'dancer_nick likes Fancy')

    def test_related_names(self):
        like = VideoLike.objects.create(user=self.user, video=self.video)

        self.assertEqual(list(self.video.likes.all()), [like])
        self.assertEqual(list(self.user.video_likes.all()), [like])

    def test_second_like_for_same_pair_raises_integrity_error(self):
        VideoLike.objects.create(user=self.user, video=self.video)

        # The inner atomic() is a savepoint: after the database error only this block is rolled
        # back, so the test can still run the count query below.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VideoLike.objects.create(user=self.user, video=self.video)

        self.assertEqual(VideoLike.objects.count(), 1)

    def test_same_user_can_like_different_videos_and_different_users_same_video(self):
        second_video = Video.objects.create(
            owner=self.user, title='Feel Special', path_to_resource='videos/feel.mp4', file_size=100,
        )

        VideoLike.objects.create(user=self.user, video=self.video)
        VideoLike.objects.create(user=self.user, video=second_video)
        VideoLike.objects.create(user=self.other_user, video=self.video)

        self.assertEqual(VideoLike.objects.count(), 3)

    def test_deleting_video_deletes_its_likes(self):
        VideoLike.objects.create(user=self.user, video=self.video)
        VideoLike.objects.create(user=self.other_user, video=self.video)

        self.video.delete()

        self.assertEqual(VideoLike.objects.count(), 0)

    def test_deleting_user_deletes_their_likes(self):
        VideoLike.objects.create(user=self.user, video=self.video)
        VideoLike.objects.create(user=self.other_user, video=self.video)

        self.other_user.delete()

        # Only the deleted user's like is gone.
        self.assertEqual(list(VideoLike.objects.values_list('user_id', flat=True)), [self.user.pk])
