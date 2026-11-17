"""
Query parameters of the video lists, shared by GET /api/library/, GET /api/library/liked/ and
GET /api/videos/ (docs/api-decisions.md D0.1, D4.2), and the per-request values of the library DTO.

Written by hand on purpose (no django-filter, no DRF filter backends). A list view does three things:

    1. validate request.query_params with one of the *FilterParams serializers below
       (a wrong value such as ?difficulty=foo becomes a 400 with a field error),
    2. build its base queryset (who may see what: Video.objects.visible_to / owned_by) and add the
       annotations it needs (annotate_times_played / annotate_for_library),
    3. call filter_videos(queryset, params) to apply the filters and the ordering.

This module may import `likes` and `dance_attempts`; videos/models.py must not (circular import).
"""

from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from rest_framework import serializers

from dance_attempts.models import DanceAttempt
from likes.models import VideoLike

from .models import AnalysisStatus, Difficulty, Visibility

# ---------------------------------------------------------------- ordering

# ?ordering=<key> -> what goes into .order_by(). Every list ends with '-id': many videos can share
# the same likes_count or times_played, and without a last, unique column the database may return
# such rows in a different order on the next page, so items would repeat or go missing.
ORDERINGS = {
    # Private videos have no published_at, so fall back to created_at (D0.1).
    'newest': [Coalesce('published_at', 'created_at').desc(), '-id'],
    # The stored column, kept in sync by likes.services (D5.1).
    'likes': ['-likes_count', '-id'],
    # Needs the `times_played` annotation: call annotate_times_played() / annotate_for_library() first.
    'played': ['-times_played', '-id'],
}


# ---------------------------------------------------------------- query-param serializers

class VideoFilterParams(serializers.Serializer):
    """Query params every video list accepts.

    All optional. `required=False` = the param may be missing; `allow_blank=True` = `?difficulty=`
    (empty) is accepted too. Both mean "no filter". ChoiceField rejects any other value with a 400.
    """

    search = serializers.CharField(required=False, allow_blank=True)
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, required=False, allow_blank=True)
    author = serializers.CharField(required=False, allow_blank=True)
    ordering = serializers.ChoiceField(choices=list(ORDERINGS), required=False, allow_blank=True)


class LibraryFilterParams(VideoFilterParams):
    """GET /api/library/: the shared params + the "public + mine" / "mine only" toggle."""

    SCOPE_ALL = 'all'
    SCOPE_MINE = 'mine'

    scope = serializers.ChoiceField(choices=[SCOPE_ALL, SCOPE_MINE], required=False, allow_blank=True)


class MyVideosFilterParams(VideoFilterParams):
    """GET /api/videos/: the shared params + the two filters that only make sense for my uploads."""

    analysis_status = serializers.ChoiceField(choices=AnalysisStatus.choices, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=Visibility.choices, required=False, allow_blank=True)


def validate_params(serializer_class, query_params):
    """request.query_params -> a dict of validated params; raises a 400 with field errors if invalid."""
    serializer = serializer_class(data=query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


# ---------------------------------------------------------------- filtering

def filter_videos(queryset, params, *, default_ordering=ORDERINGS['newest']):
    """Apply validated params (from one of the serializers above) to a Video queryset.

    A missing or empty param is skipped. `scope` is not handled here: it decides which videos the
    view starts from (visible_to or owned_by), and that needs the user.
    `default_ordering` is used when ?ordering= is not given (the liked list passes "newest like first").
    """
    search = params.get('search')
    if search:
        # icontains = case-insensitive "contains" (SQL ILIKE '%text%'). `|` = OR: a hit in any field counts.
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(song_title__icontains=search)
            | Q(song_author__icontains=search)
            | Q(owner__nickname__icontains=search)
        )

    if params.get('difficulty'):
        queryset = queryset.filter(difficulty=params['difficulty'])

    if params.get('author'):
        # iexact = the whole nickname, ignoring case (nicknames are unique ignoring case).
        # An unknown nickname simply matches nothing: an empty page, not a 404.
        queryset = queryset.filter(owner__nickname__iexact=params['author'])

    # Only MyVideosFilterParams has these two; for the other serializers .get() returns None.
    if params.get('analysis_status'):
        queryset = queryset.filter(analysis_status=params['analysis_status'])

    if params.get('visibility'):
        queryset = queryset.filter(visibility=params['visibility'])

    ordering = params.get('ordering')
    order_by = ORDERINGS[ordering] if ordering else default_ordering
    return queryset.order_by(*order_by)


# ---------------------------------------------------------------- annotations
#
# An annotation is an extra column computed by the database for every row of the list, in the same
# query. Each one below is a correlated subquery: a small SELECT that runs "for this video"
# (OuterRef('pk') = the id of the video row of the outer query).
#
# Why subqueries and not Count('attempts') + Count('likes'): two aggregates over two different
# joins multiply each other's rows (2 likes x 3 attempts = 6 rows, so both counts would say 6).
# A subquery never touches the rows of the outer query, so nothing can multiply.

def annotate_times_played(queryset):
    """Add `times_played`: how many dance attempts exist on each video, by anyone (D4.3)."""
    # "SELECT COUNT(*) FROM dance_attempt WHERE reference_video_id = <this video> GROUP BY reference_video_id"
    # https://docs.djangoproject.com/en/stable/ref/models/expressions/#using-aggregates-within-a-subquery-expression
    attempts_on_this_video = (
        DanceAttempt.objects
        .filter(reference_video=OuterRef('pk'))
        .order_by()                     # drop the model's default ordering: it would be added to the GROUP BY
        .values('reference_video')      # GROUP BY reference_video (one group: this video)
        .annotate(total=Count('pk'))    # COUNT(*) of that group
        .values('total')                # a subquery must return exactly one column
    )
    # A video nobody danced has no group at all, so the subquery gives NULL; Coalesce turns it into 0.
    return queryset.annotate(times_played=Coalesce(Subquery(attempts_on_this_video), 0))


def annotate_for_library(queryset, user):
    """Everything LibraryVideoSerializer needs beyond the Video columns, for `user` (request.user).

    Adds `times_played`, `liked_by_me` and `best_score`, and loads the owner in the same query.
    The list costs the same number of queries for 1 video or 100.

    `liked_by_me` and `best_score` are about one person. For a visitor who isn't logged in there is
    nobody to look up, so they are a constant False / NULL (D7.6); `times_played` is the same for all.
    """
    if user.is_authenticated:
        my_like = VideoLike.objects.filter(user=user, video=OuterRef('pk'))

        # My highest score on this video: sort my finished attempts by score and take the first one.
        # Unfinished attempts have score = NULL and are skipped. No attempt at all = NULL (the API's null).
        my_best_attempt = (
            DanceAttempt.objects
            .filter(user=user, reference_video=OuterRef('pk'), score__isnull=False)
            .order_by('-score')
            .values('score')[:1]
        )

        liked_by_me = Exists(my_like)               # True / False: is there a VIDEO_LIKE row for me
        best_score = Subquery(my_best_attempt)
    else:
        # Value() = a constant written into the SQL, the same for every row. The columns still
        # exist, so the serializer works exactly as for a logged-in user.
        # NULL has no type of its own, so Django has to be told which column type it stands for.
        liked_by_me = Value(False)
        best_score = Value(None, output_field=IntegerField())

    return (
        annotate_times_played(queryset)
        .annotate(liked_by_me=liked_by_me, best_score=best_score)
        .select_related('owner')                    # JOIN the author (nickname, avatar): no query per row
        .defer('json_analysis')                     # huge and never shown in the library
    )


def only_liked_by(queryset, user):
    """Keep the videos `user` liked and add `liked_at` (when), for GET /api/library/liked/.

    Expects a queryset that already went through annotate_for_library (it filters on `liked_by_me`).
    """
    # (user, video) is unique in VIDEO_LIKE, so this is one row at most; [:1] says so to the database.
    my_like_date = VideoLike.objects.filter(user=user, video=OuterRef('pk')).values('created_at')[:1]
    return queryset.filter(liked_by_me=True).annotate(liked_at=Subquery(my_like_date))


# GET /api/library/liked/ without ?ordering=: the newest like first.
LIKED_ORDERING = ['-liked_at', '-id']
