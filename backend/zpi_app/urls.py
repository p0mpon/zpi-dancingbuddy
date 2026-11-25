"""
URL configuration for zpi_app project: the whole API is routed from this file.

Resources (videos, ...) are ViewSets registered on one router; one-off actions
(login, logout, ...) get a plain path() to a function view.
https://www.django-rest-framework.org/api-guide/routers/
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from rest_framework.routers import DefaultRouter

from accounts.views import (
    CsrfView,
    LoginView,
    LogoutView,
    PasswordResetView,
    RegisterView,
    UserViewSet,
)
from dance_attempts.views import DanceAttemptViewSet
from videos.views import LibraryViewSet, VideoViewSet

router = DefaultRouter()
router.register('dance-attempts', DanceAttemptViewSet, basename='dance-attempt')
router.register('library', LibraryViewSet, basename='library')
router.register('videos', VideoViewSet, basename='video')
# /users/me/... (detail=False actions) are matched before /users/{nickname}/.
router.register('users', UserViewSet, basename='user')

auth_urls = [
    path('csrf/', CsrfView.as_view(), name='auth-csrf'),
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('password-reset/', PasswordResetView.as_view(), name='auth-password-reset'),
]

# @TODO static files and media files in django - django-storages

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include(auth_urls)),
    path('api/', include(router.urls)),
    # Login/logout pages for DRF's browsable API (handy for poking at /api/ in a browser).
    path('api-auth/', include('rest_framework.urls')),
]

# Dev only: serve avatars and video thumbnails so that `avatar_url` / `thumbnail_url` links open in the browser.
# Avatars are public by design. Thumbnails are small images with random file names (no user id in the path), served
# like avatars: a private video's thumbnail URL is only ever shown to its owner, but the URL itself is not protected.
# Only these two folders: videos/ and dance_attempt/ must NOT be served this way, because their access (private /
# public / owner only) is checked by the API endpoints (/stream/) and a plain file route would bypass it.
# Production needs a real file server (nginx) with the same restriction.
if settings.DEBUG:
    # lstrip: Django turns MEDIA_URL into '/media/', but URL patterns are matched without the leading slash.
    media_prefix = settings.MEDIA_URL.lstrip('/')
    urlpatterns += [
        # document_root is the folder itself, not MEDIA_ROOT: `serve` normalises the path, so a regex
        # prefix alone could be bypassed with `avatars/../videos/...`; with this root `..` can't leave the folder.
        re_path(rf'^{media_prefix}avatars/(?P<path>.*)$', serve,
                {'document_root': settings.MEDIA_ROOT / 'avatars'}),
        re_path(rf'^{media_prefix}thumbnails/videos/(?P<path>.*)$', serve,
                {'document_root': settings.MEDIA_ROOT / 'thumbnails' / 'videos'}),
    ]
