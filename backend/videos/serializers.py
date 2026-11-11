"""
Request/response shapes for the videos API, matching the VIDEO table in db/diagram/v2.md.

VideoSerializer is a ModelSerializer: its fields map 1:1 to Video columns, so DRF
builds them (types, max_length, ...) from the model; nothing is declared by hand;
validate() rejects a `file` in PATCH. VideoUploadSerializer is a plain Serializer because the upload doesn't match the model: the request sends `file`, the
model stores `path_to_resource`, and `file_size` is computed, not sent.

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
