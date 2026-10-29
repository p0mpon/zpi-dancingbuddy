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

STUB: handlers work on videos.stub_data instead of the database; nothing is saved.
Each TODO says what replaces the stub.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from . import services, stub_data
from .serializers import FramesQuerySerializer, VideoSerializer, VideoUploadSerializer


def not_implemented():
    return Response({'detail': 'Not implemented yet.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

# @TODO Django ninja

class VideoViewSet(viewsets.ViewSet):
    lookup_value_regex = r'\d+'

    def get_video(self, pk):
        # TODO: get_object_or_404(Video, pk=pk, user=self.request.user)
        video = stub_data.find_video(pk)
        if video is None:
            raise NotFound()
        return video

    def list(self, request):
        # TODO: Video.objects.filter(user=request.user)
        return Response(VideoSerializer(stub_data.VIDEOS, many=True).data)

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
        # TODO: serializer.save() once VideoSerializer is a ModelSerializer
        return Response(VideoSerializer({**video, **serializer.validated_data}).data)

    def destroy(self, request, pk=None):
        self.get_video(pk)
        # TODO: delete the file at path_to_resource, then video.delete()
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
        # TODO: clear big_ass_json and queue the analysis again
        return Response(status=status.HTTP_202_ACCEPTED)

    @action(detail=True, url_path='analysis/frames', url_name='analysis-frames')
    def analysis_frames(self, request, pk=None):
        video = self.get_video(pk)
        query = FramesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        frames = video['big_ass_json']
        if frames is None:
            return Response({'detail': 'Video is not analysed yet.'}, status=status.HTTP_409_CONFLICT)

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
