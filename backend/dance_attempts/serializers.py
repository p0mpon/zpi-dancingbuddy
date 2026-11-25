from django.urls import reverse
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
            'id', 'status', 'analysis_error_code', 'score', 'reference_video_id',
            'score_diff_previous', 'score_diff_best', 
            'reference_title', 'created_at'
        )
        read_only_fields = fields


class DanceAttemptDetailSerializer(DanceAttemptSerializer):
    """
    Extends the base serializer to include heavy fields 
    like score_details and the recording_url.
    """
    # The owner-only /stream/ endpoint, not the file path: recordings are never served directly.
    recording_url = serializers.SerializerMethodField()
    
    class Meta(DanceAttemptSerializer.Meta):
        fields = DanceAttemptSerializer.Meta.fields + (
            'recording_url',
            'score_details'
        )
        read_only_fields = fields

    def get_recording_url(self, attempt):
        if not attempt.recording:
            return None
        url = reverse('dance-attempt-stream', args=[attempt.pk])
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class DanceAttemptUploadSerializer(serializers.Serializer):
    """Body of POST /api/dance-attempts/ (multipart/form-data)."""

    reference_video_id = serializers.IntegerField(min_value=1)
    recording = serializers.FileField()
    mediapipe_data = serializers.JSONField()

    def validate_recording(self, recording):
        """Validate the uploaded recording file."""
        return validate_video_file(recording)