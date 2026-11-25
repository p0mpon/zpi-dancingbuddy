"""
Videos API. Routes (registered in zpi_app/urls.py):

    GET     /api/videos/                        list (my uploads; filtered + paginated)
    POST    /api/videos/                        create (multipart upload, queues the analysis)
    GET     /api/videos/{id}/                   retrieve
    PATCH   /api/videos/{id}/                   partial_update (title, description, song fields, difficulty, visibility (publish / unpublish))
    DELETE  /api/videos/{id}/                   destroy
    GET     /api/videos/{id}/stream/            stream
    GET     /api/videos/{id}/analysis/          analysis (the whole json_analysis)
    POST    /api/videos/{id}/reanalyze/         reanalyze (a failed video, while it has runs left)

Library API (LibraryViewSet, at the bottom of this file):

    GET     /api/library/                       list (public videos + all my own; ?scope=all|mine)
    GET     /api/library/liked/                 liked (the videos I liked, newest like first)
    GET     /api/library/{id}/                  retrieve
    PUT     /api/library/{id}/like/             like
    DELETE  /api/library/{id}/like/             like (the same action, removes my like)

Views only deal with HTTP: find the video, validate the request with a serializer, call
videos/services.py for any write, return a response.

/api/videos/ is "my uploads": everything is owner-only, except stream and analysis, which also
work for another user's public video because the library page plays it (docs/api-decisions.md D4.4).
/api/library/ is "what I can dance": public videos of active users plus all my own (D0.1).

Who needs to be logged in (D7.6): everything, except the three routes a visitor needs to look
around: GET /api/library/, GET /api/library/{id}/ and GET /api/videos/{id}/stream/. A visitor gets
public videos only. Login is the project default (settings: DEFAULT_PERMISSION_CLASSES), so these
three opt out with AllowAny and nothing else has to say anything.
"""

import mimetypes

from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from likes.services import like_video, unlike_video

from . import services
from .filters import (
    LIKED_ORDERING,
    LibraryFilterParams,
    MyVideosFilterParams,
    VideoFilterParams,
    annotate_for_library,
    annotate_times_played,
    filter_videos,
    only_liked_by,
    validate_params,
)
from .models import Video
from .pagination import VideoPagination
from .serializers import LibraryVideoSerializer, VideoSerializer, VideoUploadSerializer
from .services import VideoServiceError
from core.streaming import range_file_response


class VideoViewSet(viewsets.ViewSet):
    lookup_value_regex = r'\d+'

    def get_video(self, pk):
        """One of my own videos (retrieve, PATCH, DELETE, reanalyze)."""
        # Filtering by owner means another user's video gives 404, not 403,
        # so the API doesn't reveal that the id exists.
        return get_object_or_404(Video.objects.owned_by(self.request.user), pk=pk)

    def get_visible_video(self, pk):
        """A video I may watch: mine or public (stream, analysis). Someone's private video is 404.

        For a visitor who isn't logged in (stream only), visible_to() means public videos only.
        """
        return get_object_or_404(Video.objects.visible_to(self.request.user), pk=pk)

    def list(self, request):
        """My uploads, with the same filters as the library + ?analysis_status= and ?visibility=."""
        params = validate_params(MyVideosFilterParams, request.query_params)    # 400 on a wrong value

        videos = Video.objects.owned_by(request.user)
        # defer: json_analysis can be huge and the list doesn't show it.
        # times_played is not in VideoSerializer; it is only here so ?ordering=played can sort by it.
        videos = annotate_times_played(videos).defer('json_analysis')
        videos = filter_videos(videos, params)

        # This is a plain ViewSet, which knows nothing about pagination, so the paginator is called
        # by hand. These are the same two calls GenericViewSet makes inside ListModelMixin.list():
        # paginate_queryset reads ?limit= / ?offset= and fetches only that slice (plus a COUNT),
        # get_paginated_response wraps it as {count, next, previous, results}.
        paginator = VideoPagination()
        page = paginator.paginate_queryset(videos, request, view=self)
        return paginator.get_paginated_response(VideoSerializer(page, many=True, context={'request': request}).data)

    def create(self, request):
        upload = VideoUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        # owner comes from the session, never from the form (the serializer has no owner field).
        video = services.upload_video(owner=request.user, **upload.validated_data)
        return Response(VideoSerializer(video, context={'request': request}).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        return Response(VideoSerializer(self.get_video(pk), context={'request': request}).data)

    def partial_update(self, request, pk=None):
        video = self.get_video(pk)
        serializer = VideoSerializer(video, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        # validated_data holds only writable fields that were sent (file_size etc. are dropped).
        try:
            video = services.update_video(video=video, **serializer.validated_data)
        except VideoServiceError as error:
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)

        return Response(VideoSerializer(video, context={'request': request}).data)

    def destroy(self, request, pk=None):
        services.delete_video(video=self.get_video(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    # permission_classes here replaces the project default (IsAuthenticated) for this one action:
    # a visitor can watch a public video without an account (D7.6). Which video they get is still
    # decided by get_visible_video(), so a private one stays 404.
    @action(detail=True, permission_classes=[AllowAny])
    def stream(self, request, pk=None):
        """The video file, for <video src=...>, with Range support so the player can seek.

        ?download=1 saves it as '<title>.<ext>' instead.
        """
        video = self.get_visible_video(pk)
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

    @action(detail=True, methods=['post'])
    def reanalyze(self, request, pk=None):
        """Run the analysis again after it failed. 202: the work happens in the worker; poll retrieve."""
        video = self.get_video(pk)
        try:
            video = services.reanalyze_video(video=video)
        except VideoServiceError as error:      # not failed, or no runs left
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(VideoSerializer(video, context={'request': request}).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True)
    def analysis(self, request, pk=None):
        video = self.get_visible_video(pk)
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


class LibraryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Browse videos and like them. Read-only except for the like.

    GenericViewSet + the two mixins give `list` and `retrieve` ready-made. Both work the same way:
    take get_queryset(), then (list) cut out one page and serialize it with serializer_class, or
    (retrieve) find the row with the id from the URL, 404 if it isn't in the queryset.
    So all this class has to say is *which videos*: that is get_queryset().

    Browsing (list, retrieve) is open to visitors who aren't logged in; they see public videos
    only. The liked list and the like itself need a login (D7.6).
    """

    serializer_class = LibraryVideoSerializer
    pagination_class = VideoPagination
    # Digits only. Without this, /api/library/liked/ would be read as {id} = 'liked' (D5.2).
    lookup_value_regex = r'\d+'

    # The actions a visitor may call without logging in.
    OPEN_ACTIONS = ['list', 'retrieve']

    def get_permissions(self):
        """DRF calls this before every action and checks each permission it returns."""
        # A list of the open actions, not of the closed ones: an action added later needs a login
        # unless someone adds it here on purpose.
        if self.action in self.OPEN_ACTIONS:
            return [AllowAny()]
        return super().get_permissions()        # the project default: IsAuthenticated -> 401

    def get_queryset(self):
        """The videos for the current action. `self.action` is the name of the method being called."""
        # request.user is the logged-in User, or Django's AnonymousUser for a visitor.
        # visible_to() and annotate_for_library() handle both.
        user = self.request.user

        if self.action == 'list':
            params = validate_params(LibraryFilterParams, self.request.query_params)
            if params.get('scope') == LibraryFilterParams.SCOPE_MINE:
                if not user.is_authenticated:
                    # "My videos" of nobody. 401 tells the frontend to send the visitor to the
                    # login page; an empty list would look like "you have no videos".
                    raise NotAuthenticated()
                videos = Video.objects.owned_by(user)
            else:  # scope=all, or not sent
                videos = Video.objects.visible_to(user)
            return filter_videos(annotate_for_library(videos, user), params)

        if self.action == 'liked':
            # No `scope` here, so the base serializer is enough.
            params = validate_params(VideoFilterParams, self.request.query_params)
            # visible_to: a liked video that its owner unpublished is hidden (the like row stays).
            videos = annotate_for_library(Video.objects.visible_to(user), user)
            videos = only_liked_by(videos, user)
            return filter_videos(videos, params, default_ordering=LIKED_ORDERING)

        # retrieve: one video. The same annotations as the list, because it is the same DTO.
        return annotate_for_library(Video.objects.visible_to(user), user)

    @action(detail=False)
    def liked(self, request):
        """GET /api/library/liked/: the videos I liked."""
        # Exactly a list (paginate + serialize); only the queryset differs, see get_queryset().
        return self.list(request)

    @action(detail=True, methods=['put', 'delete'])
    def like(self, request, pk=None):
        """PUT = like, DELETE = remove my like. Both idempotent, both answer 200 with LikeState."""
        # likes.services doesn't check who may like what; deciding that is this view's job.
        # defer: the video row is only needed for its id, don't load the huge json_analysis.
        if request.method == 'PUT':
            # Only a public video can be liked, my own included. A private one (mine too) is 404.
            video = get_object_or_404(Video.objects.public().defer('json_analysis'), pk=pk)
            likes_count = like_video(user=request.user, video=video)
            liked_by_me = True
        else:
            # visible_to instead of public: I can still take my like off my own video after unpublishing it.
            video = get_object_or_404(Video.objects.visible_to(request.user).defer('json_analysis'), pk=pk)
            likes_count = unlike_video(user=request.user, video=video)
            liked_by_me = False

        # LikeState in docs/openapi.yaml. Two values, so a plain dict instead of a serializer.
        return Response({'likes_count': likes_count, 'liked_by_me': liked_by_me})