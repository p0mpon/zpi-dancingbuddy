"""
Dance attempts API. Routes (registered in zpi_app/urls.py):

    GET     /api/attempts/                     list the current user's attempts
    GET     /api/attempts/{id}/                retrieve a single attempt
    POST    /api/attempts/                     create a new attempt (multipart upload)
"""
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status

from . import services
from .serializers import DanceAttemptDetailSerializer, DanceAttemptSerializer, DanceAttemptUploadSerializer
from core.validators import parse_positive_int_param


class DanceAttemptViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    # Default fallback serializer
    serializer_class = DanceAttemptSerializer
    
    action_serializers = {
        'retrieve': DanceAttemptDetailSerializer,
        'create': DanceAttemptSerializer,
        'reanalyze': DanceAttemptSerializer,
    }

    def get_serializer_class(self):
        """Returns the serializer class based on the action being performed."""
        return self.action_serializers.get(self.action, self.serializer_class)

    def get_queryset(self):
        """
        Returns the queryset of DanceAttempt objects for the current user, optionally 
        filtered by a reference video id, and annotated with score differences.
        """
        video_id = parse_positive_int_param(
            self.request.query_params.get('video_id'), 
            param_name='video_id'
        )

        return services.get_attempts_for_user_with_score_diffs(self.request.user, video_id=video_id)

    def list(self, request, *args, **kwargs):
        """GET /api/dance-attempts/"""
        queryset = self.get_queryset()
        queryset = queryset.defer('json_analysis', 'score_details')
        
        video_id = request.query_params.get('video_id')
        if video_id and video_id.isdigit():
            queryset = queryset.filter(reference_video_id=video_id)

        self.queryset = queryset
        
        # mixin super() will handle pagination, serialization, http response
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """POST /api/dance-attempts/"""
        input_serializer = DanceAttemptUploadSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        try:
            attempt = services.create_attempt(
                user=request.user,
                reference_video_id=input_serializer.validated_data['reference_video_id'],
                recording=input_serializer.validated_data['recording'],
                mediapipe_data=input_serializer.validated_data.get('mediapipe_data')
            )
        except services.VideoNotReadyError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        out_serializer = self.get_serializer(attempt)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)