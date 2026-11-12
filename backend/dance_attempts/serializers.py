from rest_framework import serializers

from .models import DanceAttempt
from core.validators import validate_video_file


class DanceAttemptSerializer(serializers.ModelSerializer):
    """
    Dance attempt as returned by the API. This serializer is used for 
    listing attempts and retrieving basic information.
    """
    score_diff_previous = serializers.IntegerField(read_only=True, default=None)
    score_diff_best = serializers.IntegerField(read_only=True, default=None)
    
    class Meta:
        model = DanceAttempt
        fields = (
            'id', 'status', 'score', 
            'score_diff_previous', 'score_diff_best', 
            'reference_title', 'created_at'
        )
        read_only_fields = fields


class DanceAttemptDetailSerializer(DanceAttemptSerializer):
    """
    Extends the base serializer to include heavy fields 
    like score_details and the recording_url.
    """
    recording_url = serializers.FileField(source='recording', read_only=True)
    reference_video_url = serializers.FileField(source='reference_video.path_to_resource', read_only=True, default=None)
    
    class Meta(DanceAttemptSerializer.Meta):
        fields = DanceAttemptSerializer.Meta.fields + (
            'recording_url', 'reference_video_url',
            'score_details'
        )
        read_only_fields = fields


class DanceAttemptUploadSerializer(serializers.Serializer):
    """Body of POST /api/dance-attempts/ (multipart/form-data)."""

    reference_video_id = serializers.IntegerField(min_value=1)
    recording = serializers.FileField()
    mediapipe_data = serializers.JSONField()

    def validate_recording(self, recording):
        """Validate the uploaded recording file."""
        return validate_video_file(recording)