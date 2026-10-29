"""
Videos API. Routes (registered in zpi_app/urls.py):

    GET     /api/videos/                        list
    POST    /api/videos/                        create (multipart upload)
    GET     /api/videos/{id}/                   retrieve
    PATCH   /api/videos/{id}/                   partial_update (rename)
    DELETE  /api/videos/{id}/                   destroy
    GET     /api/videos/{id}/stream/            stream
    GET     /api/videos/{id}/thumbnail/         thumbnail
    POST    /api/videos/{id}/analysis/          analysis (re-run)
    GET     /api/videos/{id}/analysis/frames/   analysis_frames

Views only deal with HTTP: find the video (owner-only), validate the request with a
serializer, call videos/services.py for any write, return a response.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Video
from .serializers import FramesQuerySerializer, VideoSerializer, VideoUploadSerializer


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
        # TODO: services.update_video(); nothing is saved yet
        return Response({**VideoSerializer(video).data, **serializer.validated_data})

    def destroy(self, request, pk=None):
        self.get_video(pk)
        # TODO: services.delete_video(); nothing is deleted yet
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True)
    def stream(self, request, pk=None):
        self.get_video(pk)
        # TODO: FileResponse of path_to_resource, with HTTP Range support so the player can seek.
        return not_implemented()

    @action(detail=True)
    def thumbnail(self, request, pk=None):
        self.get_video(pk)
        # TODO: needs a thumbnail generated during analysis (not in the VIDEO table yet).
        return not_implemented()

    @action(detail=True, methods=['post'])
    def analysis(self, request, pk=None):
        self.get_video(pk)
        # TODO: queue Celery task (separate ticket)
        return Response(status=status.HTTP_202_ACCEPTED)

    @action(detail=True, url_path='analysis/frames', url_name='analysis-frames')
    def analysis_frames(self, request, pk=None):
        video = self.get_video(pk)
        query = FramesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        if not video.is_analysed:
            return Response({'detail': 'Video is not analysed yet.'}, status=status.HTTP_409_CONFLICT)

        # TODO: the json_analysis format isn't decided yet (list of Frame dicts as below,
        # or DAN-35's ChoreoData); this slicing assumes a list of Frame dicts.
        frames = video.json_analysis
        start = query.validated_data['start']
        end = query.validated_data.get('end', float('inf'))
        joints = query.validated_data.get('joints')
        frames = [frame for frame in frames if start <= frame['timestamp'] <= end]
        if joints:
            frames = [
                {**frame, 'joints': {name: data for name, data in frame['joints'].items() if name in joints}}
                for frame in frames
            ]
        return Response(frames)
