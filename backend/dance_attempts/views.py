"""
Dance attempts API. Routes (registered in zpi_app/urls.py):

    GET     /api/attempts/                     list the current user's attempts
    GET     /api/attempts/{id}/                retrieve a single attempt
"""
from rest_framework import viewsets, mixins

from . import services
from .serializers import DanceAttemptDetailSerializer, DanceAttemptSerializer, DanceAttemptUploadSerializer


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
        """Returns the queryset of DanceAttempt objects for the current user, annotated with score differences."""
        return services.get_attempts_for_user_with_score_diffs(self.request.user)

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