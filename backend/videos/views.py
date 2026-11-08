"""
Videos API. Routes (registered in zpi_app/urls.py):

    GET     /api/videos/                        list
    POST    /api/videos/                        create (multipart upload, queues the analysis)
    GET     /api/videos/{id}/                   retrieve
    PATCH   /api/videos/{id}/                   partial_update (title, description, song fields, difficulty, visibility (publish / unpublish))
    DELETE  /api/videos/{id}/                   destroy
    GET     /api/videos/{id}/stream/            stream
    GET     /api/videos/{id}/thumbnail/         thumbnail
    GET     /api/videos/{id}/analysis/          analysis (the whole json_analysis)

Views only deal with HTTP: find the video (owner-only), validate the request with a
serializer, call videos/services.py for any write, return a response.
"""

import mimetypes

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Video
from .serializers import VideoSerializer, VideoUploadSerializer
from .services import VideoServiceError
from .streaming import range_file_response


def not_implemented():
    return Response({'detail': 'Not implemented yet.'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class VideoViewSet(viewsets.ViewSet):
    lookup_value_regex = r'\d+'

    def get_video(self, pk):
        # Filtering by owner means another user's video gives 404, not 403,
        # so the API doesn't reveal that the id exists.
        return get_object_or_404(Video, pk=pk, owner=self.request.user)

    def list(self, request):
        # defer: json_analysis can be huge and the list doesn't show it.
        videos = Video.objects.filter(owner=request.user).defer('json_analysis')
        return Response(VideoSerializer(videos, many=True).data)

    def create(self, request):
        upload = VideoUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        # owner comes from the session, never from the form (the serializer has no owner field).
        video = services.upload_video(owner=request.user, **upload.validated_data)
        return Response(VideoSerializer(video).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        return Response(VideoSerializer(self.get_video(pk)).data)

    def partial_update(self, request, pk=None):
        video = self.get_video(pk)
        serializer = VideoSerializer(video, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # validated_data holds only writable fields that were sent (file_size etc. are dropped).
        try:
            video = services.update_video(video=video, **serializer.validated_data)
        except VideoServiceError as error:
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)

        return Response(VideoSerializer(video).data)

    def destroy(self, request, pk=None):
        services.delete_video(video=self.get_video(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True)
    def stream(self, request, pk=None):
        """The video file, for <video src=...>, with Range support so the player can seek.

        ?download=1 saves it as '<title>.<ext>' instead.
        """
        video = self.get_video(pk)
        file_name = video.path_to_resource.name
        content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        extension = file_name.rsplit('.', 1)[-1]
        # A plain Django response is fine here: DRF passes any HttpResponse through unchanged.
        return range_file_response(
            request,
            video.path_to_resource,
            content_type,
            as_attachment=request.query_params.get('download') == '1',
            filename=f'{video.title}.{extension}',
        )

    @action(detail=True)
    def thumbnail(self, request, pk=None):
        self.get_video(pk)
        # TODO: needs a thumbnail generated during analysis (not in the VIDEO table yet).
        return not_implemented()

    @action(detail=True)
    def analysis(self, request, pk=None):
        video = self.get_video(pk)
        # The frontend polls retrieve for analysis_status and asks for this once it's 'done'.
        if not video.is_analysed:
            return Response({'detail': 'Video is not analysed yet.'}, status=status.HTTP_409_CONFLICT)
        # TODO: the json_analysis format isn't decided yet (list of Frame vs DAN-35's ChoreoData);
        # it's returned as stored.
        return Response(video.json_analysis)


    # PUBLISH/UNPUBLISH endpoint - use regular PATCH for visibility
    #
    # @action(detail=True, methods=['post'])
    # def publish(self, request, pk=None):
    #     video = self.get_video(pk)
    #     try:
    #         services.publish_video(video=video)
    #     except VideoServiceError as error:
    #         return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)
    #     return Response(VideoSerializer(video).data)
    #
    # @action(detail=True, methods=['post'])
    # def unpublish(self, request, pk=None):
    #     video = self.get_video(pk)
    #     services.unpublish_video(video=video)
    #     return Response(VideoSerializer(video).data)