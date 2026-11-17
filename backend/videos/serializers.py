"""
Request/response shapes for the videos API, matching the VIDEO table in db/diagram/v2.md.

VideoSerializer is a ModelSerializer: its fields map 1:1 to Video columns, so DRF
builds them (types, max_length, ...) from the model; nothing is declared by hand;
validate() rejects a `file` in PATCH. VideoUploadSerializer is a plain Serializer because the upload doesn't match the model: the request sends `file`, the
model stores `path_to_resource`, and `file_size` is computed, not sent.

LibraryVideoSerializer is the read-only shape of /api/library/ (PublicVideo in docs/openapi.yaml).

Serializers only validate and convert; saving happens in videos/services.py.
"""

from rest_framework import serializers

from .models import Video, Difficulty
from core.validators import validate_video_file


class VideoSerializer(serializers.ModelSerializer):
    """A video as returned by the API. PATCH may change title, description, song_author, song_title, difficulty and visibility.

    Not exposed: owner (always the logged-in user), path_to_resource (served by
    /stream/) and json_analysis (too large for the list; served by /analysis/).
    """

    class Meta:
        model = Video
        fields = [
            'id', 'title', 'description',
            'song_author', 'song_title', 'difficulty',  # editable
            'file_size', 'duration_seconds', 'analysis_status',  # facts / set by the system
            'visibility', 'published_at', 'likes_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'file_size', 'duration_seconds', 'analysis_status',
            'published_at', 'likes_count',
        ]

    def validate(self, attrs):
        if 'file' in self.initial_data:
            raise serializers.ValidationError(
                {'file': "A video's file can't be changed. Delete the video and upload a new one."}
            )
        return attrs


class LibraryVideoSerializer(serializers.ModelSerializer):
    """PublicVideo in docs/openapi.yaml: a video as everyone sees it (library cards, detail page).

    Read-only: the library never writes through this serializer.
    Never add `username` (private), `file_size`, `analysis_status`, `updated_at` (owner-only),
    `path_to_resource` or `json_analysis` here.

    `liked_by_me`, `times_played` and `best_score` are not Video columns. They are computed by the
    database in the list query itself (videos/filters.py: annotate_for_library) and arrive as plain
    attributes on each video, so this serializer runs no query of its own.
    """

    # ImageField turns the stored path into a URL (absolute when the view passes `request` in the
    # context, which GenericViewSet does), or null when there is no image.
    thumbnail_url = serializers.ImageField(source='thumbnail', read_only=True)
    # `source='owner.nickname'` reads video.owner.nickname. The owner is already loaded (select_related).
    author_nickname = serializers.CharField(source='owner.nickname', read_only=True)
    author_avatar_url = serializers.ImageField(source='owner.avatar', read_only=True)
    is_mine = serializers.SerializerMethodField()       # filled by get_is_mine() below
    liked_by_me = serializers.BooleanField(read_only=True)
    times_played = serializers.IntegerField(read_only=True)
    best_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Video
        fields = [
            'id', 'title', 'description',
            'song_title', 'song_author', 'difficulty', 'duration_seconds',
            'thumbnail_url', 'visibility', 'published_at',
            'author_nickname', 'author_avatar_url', 'is_mine',
            'likes_count', 'liked_by_me', 'times_played', 'best_score',
            'created_at',
        ]
        read_only_fields = fields

    def get_is_mine(self, video):
        # owner_id is a column of the video row itself, so comparing ids costs no query.
        # A visitor who isn't logged in is AnonymousUser, whose id is None: never equal, so False.
        return video.owner_id == self.context['request'].user.id


class VideoUploadSerializer(serializers.Serializer):
    """Body of POST /api/videos/ (multipart/form-data)."""

    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    file = serializers.FileField()
    song_author = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    song_title = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, required=False, allow_null=True, default=None)

    def validate_file(self, file):
        return validate_video_file(file)
