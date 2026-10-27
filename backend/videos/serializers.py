"""
Request/response shapes for the videos API, matching the VIDEO table in db/diagram/v1.md.

Plain Serializers because the Video model doesn't exist yet; once it does,
VideoSerializer becomes a ModelSerializer with the same fields.
"""

from rest_framework import serializers

ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'mov', 'webm']


class VideoSerializer(serializers.Serializer):
    """A video as returned by the API. Only `title` can be changed (PATCH).

    Not exposed: user_id (always the logged-in user), path_to_resource (served by
    /stream/) and big_ass_json (too large; served in slices by /analysis/frames/).
    """

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(max_length=200)
    file_size = serializers.FloatField(read_only=True)


class VideoUploadSerializer(serializers.Serializer):
    """Body of POST /api/videos/ (multipart/form-data)."""

    title = serializers.CharField(max_length=200)
    file = serializers.FileField()

    def validate_file(self, file):
        if file.name.rsplit('.', 1)[-1].lower() not in ALLOWED_VIDEO_EXTENSIONS:
            raise serializers.ValidationError(f"Allowed file types: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}.")
        return file


class FramesQuerySerializer(serializers.Serializer):
    """Query params of GET /api/videos/{id}/analysis/frames/?start=1.5&end=4&joints=left_knee,right_knee"""

    start = serializers.FloatField(min_value=0, default=0)
    end = serializers.FloatField(min_value=0, required=False)
    joints = serializers.CharField(required=False)

    def validate_joints(self, value):
        return [name.strip() for name in value.split(',') if name.strip()]
