"""
Tests for DAN-141: who sees which video (VideoQuerySet), the shared filters, and /api/library/.

The files are never opened here, so `path_to_resource` is just a dummy path string and no
MEDIA_ROOT override is needed (the stream tests, which do read files, are in videos/tests.py).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from dance_attempts.models import DanceAttempt
from likes.models import VideoLike
from likes.services import like_video

from .filters import (
    LibraryFilterParams,
    MyVideosFilterParams,
    VideoFilterParams,
    annotate_for_library,
    annotate_times_played,
    filter_videos,
    only_liked_by,
    validate_params,
)
from .models import AnalysisStatus, Difficulty, Video, Visibility

User = get_user_model()


def make_user(nickname, **fields):
    """A user whose private username differs from the public nickname, so a leak would show."""
    return User.objects.create_user(username=f'{nickname}_login', nickname=nickname, password='pass', **fields)


def make_video(owner, title='Video', *, public=False, **fields):
    """A private video by default; public=True fills in what publishing requires."""
    if public:
        fields.setdefault('analysis_status', AnalysisStatus.DONE)
        fields.setdefault('difficulty', Difficulty.BEGINNER)
        fields.setdefault('published_at', timezone.now())
        fields['visibility'] = Visibility.PUBLIC
    return Video.objects.create(
        owner=owner, title=title, path_to_resource='videos/dummy.mp4', file_size=16.0, **fields,
    )


def make_attempt(user, video, score=None):
    """A dance attempt on `video`: finished with `score`, or still pending when score is None."""
    return DanceAttempt.objects.create(
        user=user, reference_video=video, reference_title=video.title,
        status=AnalysisStatus.DONE if score is not None else AnalysisStatus.PENDING, score=score,
    )


def days_ago(days):
    return timezone.now() - timedelta(days=days)


def set_created_at(video, when):
    """created_at is auto_now_add, so it can only be changed with an UPDATE."""
    Video.objects.filter(pk=video.pk).update(created_at=when)


def titles(videos):
    return [video.title for video in videos]


class VideoQuerySetTests(TestCase):
    """Video.objects.owned_by / public / visible_to: the visibility rule itself, without HTTP."""

    def setUp(self):
        self.me = make_user('me_dancer')
        self.other = make_user('other_dancer')
        self.blocked = make_user('blocked_dancer', is_active=False)

        self.my_private = make_video(self.me, 'My private')
        self.my_public = make_video(self.me, 'My public', public=True)
        self.others_private = make_video(self.other, 'Their private')
        self.others_public = make_video(self.other, 'Their public', public=True)
        self.blocked_public = make_video(self.blocked, 'Blocked public', public=True)

    def test_owned_by(self):
        self.assertCountEqual(Video.objects.owned_by(self.me), [self.my_private, self.my_public])

    def test_public_hides_private_and_inactive_owners(self):
        self.assertCountEqual(Video.objects.public(), [self.my_public, self.others_public])

    def test_visible_to_is_public_plus_mine(self):
        self.assertCountEqual(
            Video.objects.visible_to(self.me),
            [self.my_private, self.my_public, self.others_public],
        )

    def test_visible_to_another_user(self):
        self.assertCountEqual(
            Video.objects.visible_to(self.other),
            [self.my_public, self.others_private, self.others_public],
        )

    def test_visible_to_a_visitor_is_public_only(self):
        # AnonymousUser is what request.user is when nobody is logged in.
        self.assertCountEqual(Video.objects.visible_to(AnonymousUser()), [self.my_public, self.others_public])

    def test_methods_chain_with_normal_filters(self):
        videos = Video.objects.visible_to(self.me).filter(title__startswith='My')
        self.assertCountEqual(videos, [self.my_private, self.my_public])


class FilterParamsTests(SimpleTestCase):
    """The query-param serializers alone: what is accepted, what is a 400."""

    def test_nothing_sent_is_valid_and_empty(self):
        self.assertEqual(validate_params(LibraryFilterParams, QueryDict('')), {})

    def test_valid_values_are_returned(self):
        params = validate_params(
            LibraryFilterParams,
            QueryDict('search=salsa&difficulty=beginner&author=Ana&ordering=likes&scope=mine'),
        )
        self.assertEqual(
            dict(params),
            {'search': 'salsa', 'difficulty': 'beginner', 'author': 'Ana', 'ordering': 'likes', 'scope': 'mine'},
        )

    def test_empty_values_are_accepted(self):
        params = validate_params(MyVideosFilterParams, QueryDict('difficulty=&ordering=&visibility=&search='))
        self.assertEqual(set(params.values()), {''})

    def test_bad_choice_is_a_field_error(self):
        cases = [
            (VideoFilterParams, 'difficulty', 'foo'),
            (VideoFilterParams, 'ordering', 'x'),
            (LibraryFilterParams, 'scope', 'bar'),
            (MyVideosFilterParams, 'analysis_status', 'finished'),
            (MyVideosFilterParams, 'visibility', 'hidden'),
        ]
        for serializer_class, field, value in cases:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as raised:
                    validate_params(serializer_class, QueryDict(f'{field}={value}'))
                self.assertEqual(list(raised.exception.detail), [field])

    def test_params_of_another_endpoint_are_ignored(self):
        # The liked list has no `scope`; an unknown param is dropped, not an error.
        self.assertEqual(validate_params(VideoFilterParams, QueryDict('scope=bar&visibility=hidden')), {})


class FilterVideosTests(TestCase):
    """filter_videos() on real rows, without HTTP."""

    def setUp(self):
        self.ana = make_user('Ana')
        self.bob = make_user('bob')

    def filtered(self, **params):
        return filter_videos(Video.objects.all(), params)

    # ==== search

    def test_search_hits_each_of_the_four_fields(self):
        make_video(self.bob, 'Salsa basics')
        make_video(self.bob, 'Video 2', song_title='Suavemente')
        make_video(self.bob, 'Video 3', song_author='Elvis Crespo')
        make_video(self.ana, 'Video 4')
        make_video(self.bob, 'Nothing matches')

        self.assertEqual(titles(self.filtered(search='SALSA')), ['Salsa basics'])
        self.assertEqual(titles(self.filtered(search='suave')), ['Video 2'])
        self.assertEqual(titles(self.filtered(search='crespo')), ['Video 3'])
        self.assertEqual(titles(self.filtered(search='an')), ['Video 4'])       # part of the nickname 'Ana'

    def test_search_never_looks_at_the_private_username(self):
        make_video(self.ana, 'Video')
        self.assertEqual(titles(self.filtered(search='Ana_login')), [])

    def test_empty_search_is_no_filter(self):
        make_video(self.ana, 'Video')
        self.assertEqual(titles(self.filtered(search='')), ['Video'])

    # ==== exact filters

    def test_difficulty(self):
        make_video(self.ana, 'Easy', difficulty=Difficulty.BEGINNER)
        make_video(self.ana, 'Hard', difficulty=Difficulty.ADVANCED)
        make_video(self.ana, 'Not set')
        self.assertEqual(titles(self.filtered(difficulty='advanced')), ['Hard'])

    def test_author_is_exact_but_ignores_case(self):
        make_video(self.ana, 'By Ana')
        make_video(self.bob, 'By Bob')
        self.assertEqual(titles(self.filtered(author='aNA')), ['By Ana'])
        self.assertEqual(titles(self.filtered(author='An')), [])            # not a partial match
        self.assertEqual(titles(self.filtered(author='nobody')), [])        # unknown nickname: empty, no error

    def test_analysis_status_and_visibility(self):
        make_video(self.ana, 'Pending')
        make_video(self.ana, 'Failed', analysis_status=AnalysisStatus.FAILED)
        make_video(self.ana, 'Published', public=True)
        self.assertEqual(titles(self.filtered(analysis_status='failed')), ['Failed'])
        self.assertEqual(titles(self.filtered(visibility='public')), ['Published'])
        self.assertCountEqual(titles(self.filtered(visibility='private')), ['Pending', 'Failed'])

    def test_filters_combine_with_and(self):
        make_video(self.ana, 'Salsa easy', difficulty=Difficulty.BEGINNER)
        make_video(self.ana, 'Salsa hard', difficulty=Difficulty.ADVANCED)
        make_video(self.bob, 'Salsa easy too', difficulty=Difficulty.BEGINNER)
        self.assertEqual(titles(self.filtered(search='salsa', difficulty='beginner', author='ana')), ['Salsa easy'])

    # ==== ordering

    def test_newest_is_default_and_mixes_private_and_public(self):
        # Sorted by published_at, or created_at for a private video (which has no published_at).
        private = make_video(self.ana, 'Private, created 3 days ago')
        set_created_at(private, days_ago(3))
        old_but_just_published = make_video(self.ana, 'Published 1 day ago', public=True, published_at=days_ago(1))
        set_created_at(old_but_just_published, days_ago(9))
        new_but_published_long_ago = make_video(self.ana, 'Published 5 days ago', public=True, published_at=days_ago(5))
        set_created_at(new_but_published_long_ago, days_ago(6))

        expected = ['Published 1 day ago', 'Private, created 3 days ago', 'Published 5 days ago']
        self.assertEqual(titles(self.filtered()), expected)
        self.assertEqual(titles(self.filtered(ordering='newest')), expected)
        self.assertEqual(titles(self.filtered(ordering='')), expected)

    def test_likes(self):
        make_video(self.ana, 'One like', likes_count=1)
        make_video(self.ana, 'Five likes', likes_count=5)
        make_video(self.ana, 'No likes')
        self.assertEqual(titles(self.filtered(ordering='likes')), ['Five likes', 'One like', 'No likes'])

    def test_played(self):
        once = make_video(self.ana, 'Danced once')
        make_video(self.ana, 'Never danced')
        twice = make_video(self.ana, 'Danced twice')
        make_attempt(self.bob, once)
        make_attempt(self.bob, twice)
        make_attempt(self.ana, twice)

        videos = filter_videos(annotate_times_played(Video.objects.all()), {'ordering': 'played'})
        self.assertEqual(titles(videos), ['Danced twice', 'Danced once', 'Never danced'])

    def test_ties_are_broken_by_id_so_pages_are_stable(self):
        first = make_video(self.ana, 'First')
        second = make_video(self.ana, 'Second')
        third = make_video(self.ana, 'Third')
        Video.objects.update(created_at=days_ago(1))        # all three now tie on every ordering

        for ordering in ['newest', 'likes', 'played']:
            with self.subTest(ordering=ordering):
                videos = filter_videos(annotate_times_played(Video.objects.all()), {'ordering': ordering})
                self.assertEqual(list(videos), [third, second, first])

    def test_default_ordering_can_be_replaced(self):
        make_video(self.ana, 'B')
        make_video(self.ana, 'A')
        by_title = filter_videos(Video.objects.all(), {}, default_ordering=['title'])
        self.assertEqual(titles(by_title), ['A', 'B'])
        # An explicit ?ordering= still wins over the default.
        explicit = filter_videos(Video.objects.all(), {'ordering': 'newest'}, default_ordering=['title'])
        self.assertEqual(titles(explicit), ['A', 'B'])      # 'A' was created last, so it is the newest


class LibraryAnnotationsTests(TestCase):
    """annotate_for_library(): liked_by_me, times_played, best_score."""

    def setUp(self):
        self.me = make_user('me_dancer')
        self.other = make_user('other_dancer')
        self.third = make_user('third_dancer')
        self.video = make_video(self.other, 'Busy video', public=True)
        self.quiet = make_video(self.other, 'Quiet video', public=True)

    def annotated(self, video, user=None):
        return annotate_for_library(Video.objects.all(), user or self.me).get(pk=video.pk)

    def test_two_likes_and_three_attempts_do_not_multiply(self):
        # With two joined aggregates this would give 6 and 6 (2 x 3 rows).
        like_video(user=self.me, video=self.video)
        like_video(user=self.other, video=self.video)
        make_attempt(self.me, self.video, score=40)
        make_attempt(self.me, self.video, score=85)
        make_attempt(self.third, self.video, score=99)

        video = self.annotated(self.video)
        self.assertEqual(video.likes_count, 2)
        self.assertEqual(video.times_played, 3)
        self.assertIs(video.liked_by_me, True)
        self.assertEqual(video.best_score, 85)        # my best, not the third user's 99

    def test_video_without_likes_or_attempts(self):
        video = self.annotated(self.quiet)
        self.assertEqual(video.times_played, 0)        # 0, not None
        self.assertIs(video.liked_by_me, False)
        self.assertIsNone(video.best_score)

    def test_values_are_per_user(self):
        like_video(user=self.me, video=self.video)
        make_attempt(self.me, self.video, score=70)

        for_third = self.annotated(self.video, user=self.third)
        self.assertIs(for_third.liked_by_me, False)
        self.assertIsNone(for_third.best_score)
        self.assertEqual(for_third.times_played, 1)    # counts everyone's attempts

    def test_unfinished_attempts_count_as_played_but_have_no_score(self):
        make_attempt(self.me, self.video)               # pending: score is NULL
        video = self.annotated(self.video)
        self.assertEqual(video.times_played, 1)
        self.assertIsNone(video.best_score)

        make_attempt(self.me, self.video, score=0)      # a finished 0 is a real score
        self.assertEqual(self.annotated(self.video).best_score, 0)

    def test_visitor_gets_constants_but_real_totals(self):
        like_video(user=self.me, video=self.video)
        make_attempt(self.me, self.video, score=70)

        video = self.annotated(self.video, user=AnonymousUser())
        self.assertIs(video.liked_by_me, False)
        self.assertIsNone(video.best_score)
        self.assertEqual(video.times_played, 1)
        self.assertEqual(video.likes_count, 1)

    def test_owner_is_loaded_and_json_analysis_is_not(self):
        with self.assertNumQueries(1):
            video = self.annotated(self.video)
            self.assertEqual(video.owner.nickname, 'other_dancer')
        self.assertIn('json_analysis', video.get_deferred_fields())

    def test_only_liked_by(self):
        like_video(user=self.me, video=self.video)
        like_video(user=self.third, video=self.quiet)

        liked = only_liked_by(annotate_for_library(Video.objects.all(), self.me), self.me)
        self.assertEqual(list(liked), [self.video])
        self.assertEqual(liked[0].liked_at, VideoLike.objects.get(user=self.me, video=self.video).created_at)


LIBRARY_VIDEO_KEYS = {
    'id', 'title', 'description', 'song_title', 'song_author', 'difficulty', 'duration_seconds',
    'thumbnail_url', 'visibility', 'published_at', 'author_nickname', 'author_avatar_url', 'is_mine',
    'likes_count', 'liked_by_me', 'times_played', 'best_score', 'created_at',
}


class LibraryApiTestCase(APITestCase):
    """Shared setup: I am `me`; there is another user and a blocked (inactive) one."""

    def setUp(self):
        self.me = make_user('me_dancer')
        self.other = make_user('Other_Dancer')
        self.blocked = make_user('blocked_dancer', is_active=False)

        self.my_private = make_video(self.me, 'My private')
        self.my_public = make_video(self.me, 'My public', public=True)
        self.others_private = make_video(self.other, 'Their private')
        self.others_public = make_video(self.other, 'Their public', public=True)
        self.blocked_public = make_video(self.blocked, 'Blocked public', public=True)

        self.client.force_authenticate(self.me)

    def get_list(self, url='/api/library/', **params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response

    def listed_titles(self, url='/api/library/', **params):
        return [video['title'] for video in self.get_list(url, **params).data['results']]

    def detail_url(self, video):
        return f'/api/library/{video.pk}/'

    def like_url(self, video):
        return f'/api/library/{video.pk}/like/'

    def unpublish(self, video):
        """What PATCH visibility=private does to the row (the likes are kept)."""
        Video.objects.filter(pk=video.pk).update(visibility=Visibility.PRIVATE, published_at=None)


class LibraryListApiTests(LibraryApiTestCase):
    """GET /api/library/ and GET /api/library/{id}/."""

    def test_library_is_read_only(self):
        self.assertEqual(self.client.post('/api/library/', {}).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        for method in [self.client.patch, self.client.put, self.client.delete]:
            response = method(self.detail_url(self.my_private), {})
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Video.objects.filter(pk=self.my_private.pk).exists())

    # ==== scope

    def test_scope_all_is_public_plus_mine(self):
        # Hidden: another user's private video and the public video of an inactive owner.
        expected = ['My private', 'My public', 'Their public']
        self.assertCountEqual(self.listed_titles(), expected)
        self.assertCountEqual(self.listed_titles(scope='all'), expected)
        self.assertCountEqual(self.listed_titles(scope=''), expected)

    def test_scope_mine(self):
        self.assertCountEqual(self.listed_titles(scope='mine'), ['My private', 'My public'])

    # ==== filters and ordering through HTTP (the details are tested in FilterVideosTests)

    def test_bad_params_are_400_with_a_field_error(self):
        for field, value in [('difficulty', 'foo'), ('scope', 'bar'), ('ordering', 'x')]:
            with self.subTest(field=field):
                response = self.client.get('/api/library/', {field: value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(list(response.data), [field])

    def test_filters(self):
        make_video(self.other, 'Hard salsa', public=True, difficulty=Difficulty.ADVANCED, song_title='Suavemente')

        self.assertEqual(self.listed_titles(search='suave'), ['Hard salsa'])
        self.assertEqual(self.listed_titles(difficulty='advanced'), ['Hard salsa'])
        self.assertCountEqual(self.listed_titles(author='other_dancer'), ['Their public', 'Hard salsa'])
        self.assertEqual(self.listed_titles(author='nobody'), [])
        # Filters never widen what I may see: the other user's private video stays hidden.
        self.assertEqual(self.listed_titles(search='Their private'), [])
        self.assertEqual(self.listed_titles(scope='mine', author='other_dancer'), [])

    def test_ordering(self):
        Video.objects.filter(pk=self.others_public.pk).update(likes_count=7)
        make_attempt(self.other, self.my_public)

        self.assertEqual(self.listed_titles(ordering='likes')[0], 'Their public')
        self.assertEqual(self.listed_titles(ordering='played')[0], 'My public')
        # Default = newest; all three were created just now, so the last tie-breaker (-id) decides.
        self.assertEqual(self.listed_titles(), ['Their public', 'My public', 'My private'])

    # ==== pagination

    def test_page_shape_and_following_next(self):
        response = self.get_list(limit=2)
        self.assertEqual(set(response.data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 2)
        self.assertIsNone(response.data['previous'])

        second_page = self.client.get(response.data['next'])
        self.assertEqual(len(second_page.data['results']), 1)
        self.assertIsNone(second_page.data['next'])
        self.assertIsNotNone(second_page.data['previous'])
        # The two pages together are the whole list, nothing twice.
        ids = [video['id'] for video in response.data['results'] + second_page.data['results']]
        self.assertCountEqual(ids, [self.my_private.pk, self.my_public.pk, self.others_public.pk])

    def test_default_page_is_20_and_limit_is_capped_at_100(self):
        Video.objects.bulk_create([
            Video(owner=self.me, title=f'Bulk {number}', path_to_resource='videos/dummy.mp4', file_size=1.0)
            for number in range(110)
        ])
        self.assertEqual(len(self.get_list().data['results']), 20)
        self.assertEqual(len(self.get_list(limit=50).data['results']), 50)
        self.assertEqual(len(self.get_list(limit=5000).data['results']), 100)

    # ==== the DTO

    def test_fields_of_another_users_video(self):
        self.other.avatar = 'avatars/user_2/face.jpg'       # a path is enough, the file isn't opened
        self.other.save()

        video = self.client.get(self.detail_url(self.others_public)).data
        self.assertEqual(set(video), LIBRARY_VIDEO_KEYS)
        self.assertEqual(video['title'], 'Their public')
        self.assertEqual(video['visibility'], 'public')
        self.assertEqual(video['difficulty'], 'beginner')
        self.assertIsNotNone(video['published_at'])
        self.assertEqual(video['author_nickname'], 'Other_Dancer')
        self.assertEqual(video['author_avatar_url'], 'http://testserver/media/avatars/user_2/face.jpg')
        self.assertIsNone(video['thumbnail_url'])
        self.assertIs(video['is_mine'], False)
        self.assertEqual(video['likes_count'], 0)
        self.assertIs(video['liked_by_me'], False)
        self.assertEqual(video['times_played'], 0)
        self.assertIsNone(video['best_score'])

    def test_list_items_have_the_same_fields(self):
        for video in self.get_list().data['results']:
            self.assertEqual(set(video), LIBRARY_VIDEO_KEYS)

    def test_private_username_is_never_in_a_response(self):
        for url in ['/api/library/', self.detail_url(self.others_public)]:
            content = self.client.get(url).content.decode()
            self.assertNotIn('_login', content)         # every test username ends with '_login'
            self.assertNotIn('username', content)

    def test_is_mine_and_visibility_of_my_private_video(self):
        video = self.client.get(self.detail_url(self.my_private)).data
        self.assertIs(video['is_mine'], True)
        self.assertEqual(video['visibility'], 'private')
        self.assertIsNone(video['published_at'])
        self.assertIsNone(video['author_avatar_url'])

    def test_counts_with_two_likes_and_three_attempts(self):
        # Through HTTP this time: joined aggregates would report 6 and 6.
        like_video(user=self.me, video=self.others_public)
        like_video(user=self.other, video=self.others_public)
        make_attempt(self.me, self.others_public, score=40)
        make_attempt(self.me, self.others_public, score=85)
        make_attempt(self.other, self.others_public, score=99)

        for video in [
            self.client.get(self.detail_url(self.others_public)).data,
            self.get_list(search='Their public').data['results'][0],
        ]:
            self.assertEqual(video['likes_count'], 2)
            self.assertIs(video['liked_by_me'], True)
            self.assertEqual(video['times_played'], 3)
            self.assertEqual(video['best_score'], 85)

    def test_list_runs_the_same_number_of_queries_for_1_or_many_videos(self):
        with CaptureQueriesContext(connection) as with_one:
            self.assertEqual(len(self.get_list(search='Their public').data['results']), 1)

        for number in range(5):
            video = make_video(self.other, f'More {number}', public=True)
            like_video(user=self.me, video=video)
            make_attempt(self.me, video, score=50)
        with CaptureQueriesContext(connection) as with_many:
            self.assertEqual(len(self.get_list().data['results']), 8)

        # One COUNT for the page info + one SELECT for the rows, whatever the number of rows.
        self.assertEqual(len(with_one), 2)
        self.assertEqual(len(with_many), 2)

    # ==== detail

    def test_detail_access(self):
        cases = [
            (self.others_public, status.HTTP_200_OK),
            (self.my_private, status.HTTP_200_OK),
            (self.my_public, status.HTTP_200_OK),
            (self.others_private, status.HTTP_404_NOT_FOUND),
            (self.blocked_public, status.HTTP_404_NOT_FOUND),
        ]
        for video, expected in cases:
            with self.subTest(video=video.title):
                self.assertEqual(self.client.get(self.detail_url(video)).status_code, expected)
        self.assertEqual(self.client.get('/api/library/999999/').status_code, status.HTTP_404_NOT_FOUND)


class LibraryVisitorApiTests(LibraryApiTestCase):
    """The library for a visitor who isn't logged in (D7.6): public videos only, read-only."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(None)        # nobody is logged in

    def test_list_shows_public_videos_only(self):
        # Hidden: every private video and the public video of an inactive owner.
        self.assertCountEqual(self.listed_titles(), ['My public', 'Their public'])
        self.assertCountEqual(self.listed_titles(scope='all'), ['My public', 'Their public'])

    def test_scope_mine_needs_login(self):
        # "My videos" of nobody: 401, not an empty list.
        response = self.client.get('/api/library/', {'scope': 'mine'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_personal_fields_are_false_and_null(self):
        # Other people liked and danced it. The totals are real; the "me" fields have no "me".
        like_video(user=self.me, video=self.others_public)
        make_attempt(self.me, self.others_public, score=85)
        make_attempt(self.other, self.others_public, score=60)

        for video in [
            self.client.get(self.detail_url(self.others_public)).data,
            self.get_list(search='Their public').data['results'][0],
        ]:
            self.assertEqual(set(video), LIBRARY_VIDEO_KEYS)        # the same fields as when logged in
            self.assertEqual(video['likes_count'], 1)
            self.assertEqual(video['times_played'], 2)
            self.assertIs(video['is_mine'], False)
            self.assertIs(video['liked_by_me'], False)
            self.assertIsNone(video['best_score'])

    def test_filters_ordering_and_pages_work(self):
        make_video(self.other, 'Their salsa', public=True, difficulty=Difficulty.ADVANCED, likes_count=5)

        self.assertEqual(self.listed_titles(search='SALSA'), ['Their salsa'])
        self.assertEqual(self.listed_titles(difficulty='advanced'), ['Their salsa'])
        self.assertCountEqual(self.listed_titles(author='other_dancer'), ['Their public', 'Their salsa'])
        self.assertEqual(self.listed_titles(ordering='likes')[0], 'Their salsa')

        response = self.get_list(limit=1)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIsNotNone(response.data['next'])

    def test_bad_params_are_400(self):
        response = self.client.get('/api/library/', {'difficulty': 'expert'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('difficulty', response.data)

    def test_private_username_is_never_in_a_response(self):
        for url in ['/api/library/', self.detail_url(self.others_public)]:
            content = self.client.get(url).content.decode()
            self.assertNotIn('_login', content)
            self.assertNotIn('username', content)

    def test_list_runs_two_queries(self):
        # No session to load and no user to look up: one COUNT + one SELECT.
        with self.assertNumQueries(2):
            self.get_list()

    def test_detail_access(self):
        cases = [
            (self.others_public, status.HTTP_200_OK),
            (self.my_public, status.HTTP_200_OK),
            (self.my_private, status.HTTP_404_NOT_FOUND),       # 404, not 401: don't reveal that the id exists
            (self.others_private, status.HTTP_404_NOT_FOUND),
            (self.blocked_public, status.HTTP_404_NOT_FOUND),
        ]
        for video, expected in cases:
            with self.subTest(video=video.title):
                self.assertEqual(self.client.get(self.detail_url(video)).status_code, expected)

    def test_liked_list_needs_login(self):
        self.assertEqual(self.client.get('/api/library/liked/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_like_needs_login(self):
        self.assertEqual(self.client.put(self.like_url(self.others_public)).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.delete(self.like_url(self.others_public)).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(VideoLike.objects.count(), 0)

    def test_library_is_still_read_only(self):
        self.assertEqual(self.client.post('/api/library/', {}).status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.delete(self.detail_url(self.others_public))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Video.objects.filter(pk=self.others_public.pk).exists())


class LikeApiTests(LibraryApiTestCase):
    """PUT / DELETE /api/library/{id}/like/ at the HTTP level (the counting is tested in likes/tests/)."""

    def stored_likes_count(self, video):
        return Video.objects.get(pk=video.pk).likes_count

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.put(self.like_url(self.others_public)).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.delete(self.like_url(self.others_public)).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(VideoLike.objects.count(), 0)

    def test_only_put_and_delete(self):
        for method in [self.client.get, self.client.post, self.client.patch]:
            response = method(self.like_url(self.others_public))
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_twice_likes_once(self):
        for _ in range(2):
            response = self.client.put(self.like_url(self.others_public))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, {'likes_count': 1, 'liked_by_me': True})
        self.assertEqual(VideoLike.objects.filter(user=self.me, video=self.others_public).count(), 1)
        self.assertEqual(self.stored_likes_count(self.others_public), 1)

    def test_delete_twice_unlikes_once(self):
        like_video(user=self.other, video=self.others_public)
        self.client.put(self.like_url(self.others_public))
        expected = {'likes_count': 1, 'liked_by_me': False}      # the other user's like stays

        for _ in range(2):
            response = self.client.delete(self.like_url(self.others_public))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, expected)
        self.assertFalse(VideoLike.objects.filter(user=self.me).exists())
        self.assertEqual(self.stored_likes_count(self.others_public), 1)

    def test_like_shows_up_in_the_library(self):
        self.client.put(self.like_url(self.others_public))
        video = self.client.get(self.detail_url(self.others_public)).data
        self.assertEqual(video['likes_count'], 1)
        self.assertIs(video['liked_by_me'], True)

    def test_own_public_video_can_be_liked(self):
        response = self.client.put(self.like_url(self.my_public))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'likes_count': 1, 'liked_by_me': True})

    def test_put_on_a_video_that_is_not_public_is_404(self):
        # Another user's private video, my own private video, a blocked owner's public video, no video.
        for video in [self.others_private, self.my_private, self.blocked_public]:
            with self.subTest(video=video.title):
                self.assertEqual(self.client.put(self.like_url(video)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.put('/api/library/999999/like/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(VideoLike.objects.count(), 0)

    def test_delete_works_on_my_own_video_after_i_unpublished_it(self):
        self.client.put(self.like_url(self.my_public))
        self.unpublish(self.my_public)

        response = self.client.delete(self.like_url(self.my_public))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'likes_count': 0, 'liked_by_me': False})
        self.assertEqual(self.stored_likes_count(self.my_public), 0)

    def test_delete_on_another_users_private_video_is_404(self):
        self.assertEqual(self.client.delete(self.like_url(self.others_private)).status_code, status.HTTP_404_NOT_FOUND)

        # Also when I liked it while it was public: the like stays and comes back if it is published again.
        self.client.put(self.like_url(self.others_public))
        self.unpublish(self.others_public)
        self.assertEqual(self.client.delete(self.like_url(self.others_public)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(VideoLike.objects.filter(user=self.me, video=self.others_public).exists())
        self.assertEqual(self.stored_likes_count(self.others_public), 1)


class LikedListApiTests(LibraryApiTestCase):
    """GET /api/library/liked/."""

    def like_at(self, video, when, user=None):
        """Like `video` and move the like's date (created_at is auto_now_add)."""
        like_video(user=user or self.me, video=video)
        VideoLike.objects.filter(user=user or self.me, video=video).update(created_at=when)

    def liked_titles(self, **params):
        return self.listed_titles('/api/library/liked/', **params)

    def test_is_the_list_action_not_a_video_called_liked(self):
        response = self.get_list('/api/library/liked/')
        self.assertEqual(set(response.data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(response.data['results'], [])

    def test_only_my_likes_newest_like_first(self):
        third_public = make_video(self.other, 'Liked long ago', public=True)
        self.like_at(third_public, days_ago(5))
        self.like_at(self.my_public, days_ago(1))
        self.like_at(self.others_public, days_ago(3))
        # Someone else's like is not mine.
        unliked = make_video(self.other, 'Liked by someone else', public=True)
        self.like_at(unliked, days_ago(0), user=self.other)

        # By like date, not by the video's own date (the newest video here was liked first).
        self.assertEqual(self.liked_titles(), ['My public', 'Their public', 'Liked long ago'])

        video = self.get_list('/api/library/liked/').data['results'][0]
        self.assertEqual(set(video), LIBRARY_VIDEO_KEYS)        # `liked_at` is not part of the DTO
        self.assertIs(video['liked_by_me'], True)

    def test_unpublished_video_is_hidden_but_the_like_is_kept(self):
        self.like_at(self.others_public, days_ago(1))
        self.unpublish(self.others_public)
        self.assertEqual(self.liked_titles(), [])
        self.assertTrue(VideoLike.objects.filter(user=self.me, video=self.others_public).exists())

        # Published again: it is back in the list.
        Video.objects.filter(pk=self.others_public.pk).update(
            visibility=Visibility.PUBLIC, published_at=timezone.now(),
        )
        self.assertEqual(self.liked_titles(), ['Their public'])

    def test_my_own_unpublished_video_stays(self):
        self.like_at(self.my_public, days_ago(1))
        self.unpublish(self.my_public)
        self.assertEqual(self.liked_titles(), ['My public'])

    def test_video_of_a_blocked_owner_is_hidden(self):
        self.like_at(self.others_public, days_ago(1))
        self.other.is_active = False
        self.other.save()
        self.assertEqual(self.liked_titles(), [])

    def test_filters_and_explicit_ordering(self):
        hard = make_video(self.other, 'Hard one', public=True, difficulty=Difficulty.ADVANCED, likes_count=9)
        self.like_at(hard, days_ago(4))
        self.like_at(self.others_public, days_ago(2))
        self.like_at(self.my_public, days_ago(1))

        self.assertEqual(self.liked_titles(difficulty='advanced'), ['Hard one'])
        self.assertEqual(self.liked_titles(search='their'), ['Their public'])
        self.assertEqual(self.liked_titles(author='ME_dancer'), ['My public'])
        # ?ordering= replaces "newest like first".
        self.assertEqual(self.liked_titles(ordering='likes')[0], 'Hard one')
        self.assertEqual(self.liked_titles(ordering='newest'), ['Hard one', 'Their public', 'My public'])

    def test_bad_ordering_is_400_and_scope_is_ignored(self):
        response = self.client.get('/api/library/liked/', {'ordering': 'x'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(list(response.data), ['ordering'])
        # The liked list has no `scope` param, so even a wrong value is not an error.
        self.assertEqual(self.liked_titles(scope='bar'), [])

    def test_is_paginated(self):
        self.like_at(self.others_public, days_ago(2))
        self.like_at(self.my_public, days_ago(1))
        response = self.get_list('/api/library/liked/', limit=1)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual([video['title'] for video in response.data['results']], ['My public'])
        self.assertIsNotNone(response.data['next'])
