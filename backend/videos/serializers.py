"""
Request/response shapes for the videos API, matching the VIDEO table in db/diagram/v1.md.

VideoSerializer is a ModelSerializer: its fields map 1:1 to Video columns, so DRF
builds them (types, max_length, ...) from the model. VideoUploadSerializer is a plain
Serializer because the upload doesn't match the model: the request sends `file`, the
model stores `path_to_resource`, and `file_size` is computed, not sent.

Serializers only validate and convert; saving happens in videos/services.py.
"""

from rest_framework import serializers

from .models import Video

ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'mov', 'webm']

MAX_VIDEO_SIZE_MB = 500
MAX_VIDEO_SIZE_BYTES = MAX_VIDEO_SIZE_MB * 1024 * 1024


class VideoSerializer(serializers.ModelSerializer):
    """A video as returned by the API. PATCH may change title and description.

    Not exposed: owner (always the logged-in user), path_to_resource (served by
    /stream/) and json_analysis (too large; served in slices by /analysis/frames/).
    """

    class Meta:
        model = Video
        fields = ['id', 'title', 'description', 'file_size', 'analysis_status', 'created_at']
        read_only_fields = ['file_size', 'analysis_status']


class VideoUploadSerializer(serializers.Serializer):
    """Body of POST /api/videos/ (multipart/form-data)."""

    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    file = serializers.FileField()

    def validate_file(self, file):
        if file.name.rsplit('.', 1)[-1].lower() not in ALLOWED_VIDEO_EXTENSIONS:
            raise serializers.ValidationError(f"Allowed file types: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}.")
        if file.size > MAX_VIDEO_SIZE_BYTES:
            raise serializers.ValidationError(f'File is too large (max {MAX_VIDEO_SIZE_MB} MB).')
        return file


class FramesQuerySerializer(serializers.Serializer):
    """Query params of GET /api/videos/{id}/analysis/frames/?start=1.5&end=4&joints=left_knee,right_knee"""

    start = serializers.FloatField(min_value=0, default=0)
    end = serializers.FloatField(min_value=0, required=False)
    joints = serializers.CharField(required=False)

    def validate_joints(self, value):
        return [name.strip() for name in value.split(',') if name.strip()]
