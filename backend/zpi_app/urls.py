"""
URL configuration for zpi_app project: the whole API is routed from this file.

Resources (videos, ...) are ViewSets registered on one router; one-off actions
(login, logout, ...) get a plain path() to a function view.
https://www.django-rest-framework.org/api-guide/routers/
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from dance_attempts.views import DanceAttemptViewSet
from videos.views import VideoViewSet

router = DefaultRouter()
router.register('dance-attempts', DanceAttemptViewSet, basename='dance-attempt')
router.register('videos', VideoViewSet, basename='video')

# @TODO static files and media files in django - django-storages

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    # Login/logout pages for DRF's browsable API (handy for poking at /api/ in a browser).
    path('api-auth/', include('rest_framework.urls')),
]
