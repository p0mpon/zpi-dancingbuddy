"""
Celery tasks for videos. They run in the celery-worker container, not in the web request.

Two small tasks, one after the other:

  normalize_video_file   services.start_analysis() queues it. Starts the run (status 'processing',
                         analysis_runs + 1), re-encodes the file as the standard MP4 (once, core/ffmpeg.py),
                         then queues analyse_video. A timeout or an unexpected error is retried (Celery's
                         own retry, short waits, each try is a run); any other problem ends the run as
                         'failed' with an AnalysisError code (docs D3.8).
  analyse_video          makes the thumbnail (a failure is only logged), runs the analysis,
                         then 'done' + json_analysis, or 'failed' with code 5.

Like views, tasks don't write to the DB themselves; they call videos/services.py.
"""

import logging
import os
import tempfile
from pathlib import Path

from celery import shared_task
from django.core.files import File

from core.ffmpeg import (
    FFmpegError,
    FFmpegTimeout,
    extract_frame,
    normalize_video,
    probe_video,
    read_duration_seconds,
)
from core.images import make_fitted_webp
from full_analysis.choreo_analyzer import perform_full_analysis

from . import services
from .models import NORMALIZE_RETRY_DELAYS_SECONDS, AnalysisError, AnalysisStatus, Video

logger = logging.getLogger(__name__)

THUMBNAIL_MAX_SIDE = 720
THUMBNAIL_FALLBACK_SECONDS = 1.0    # where to take the frame when the duration is unknown


def run_analysis(file_path):
    """Analyse the video file at file_path and return the value for json_analysis."""
    frames = perform_full_analysis(file_path)
    return [frame.model_dump() for frame in frames]


def _fail(video_id, code, message=''):
    """End the run as 'failed' with an error code."""
    logger.error('Analysis of video %s failed: %s %s', video_id, code.label, message)
    services.set_analysis_result(video_id=video_id, status=AnalysisStatus.FAILED, error_code=code)


def _retry_or_fail(task, error, video_id, code):
    """Try again after a short wait, or end the run as failed when the tries are used up."""
    if task.request.retries >= task.max_retries:
        _fail(video_id, code, str(error))
        return
    raise task.retry(exc=error, countdown=NORMALIZE_RETRY_DELAYS_SECONDS[task.request.retries])


@shared_task(bind=True, max_retries=len(NORMALIZE_RETRY_DELAYS_SECONDS))
def normalize_video_file(self, video_id):
    """Start a run: normalize the file (if it isn't yet), then queue the analysis."""
    video = Video.objects.defer('json_analysis').filter(pk=video_id).first()
    if video is None:  # deleted before the worker got to it
        return

    if not services.mark_video_processing(video_id=video_id):
        logger.info('Analysis of video %s skipped: deleted', video_id)
        return

    try:
        path = video.path_to_resource.path      # .path works for local disk (FileSystemStorage)
        if not os.path.isfile(path):
            _fail(video_id, AnalysisError.FILE_MISSING)
            return

        if not video.is_normalized:
            info = probe_video(path)
            if info is None:
                # ffprobe can't read it, or there is no video stream: retrying won't help.
                _fail(video_id, AnalysisError.UNREADABLE)
                return

            with tempfile.TemporaryDirectory() as temp_dir:     # removed even if something raises
                output = Path(temp_dir) / 'normalized.mp4'
                normalize_video(path, output, has_audio=info.has_audio)     # the original is only read
                if services.update_video_file(video_id=video_id, new_path=output) is None:
                    logger.info('Analysis of video %s stopped: deleted', video_id)
                    return
    except FFmpegTimeout as error:      # a busy server can make a good file time out
        _retry_or_fail(self, error, video_id, AnalysisError.NORMALIZATION_TIMEOUT)
        return
    except FFmpegError as error:        # ffmpeg itself said no: the same file would fail again
        _fail(video_id, AnalysisError.NORMALIZATION_FAILED, str(error))
        return
    except Exception as error:
        logger.exception('Normalization of video %s failed unexpectedly', video_id)
        _retry_or_fail(self, error, video_id, AnalysisError.UNKNOWN)
        return

    analyse_video.delay(video_id)


def _make_thumbnail(video):
    """Frame from the middle of the (normalized) video as WebP. Never fails the analysis."""
    try:
        path = video.path_to_resource.path
        duration = read_duration_seconds(path)
        at_seconds = duration / 2 if duration else THUMBNAIL_FALLBACK_SECONDS
        with tempfile.TemporaryDirectory() as temp_dir:
            frame = Path(temp_dir) / 'frame.png'
            extract_frame(path, frame, at_seconds=at_seconds)
            with open(frame, 'rb') as frame_file:
                thumbnail = make_fitted_webp(File(frame_file), max_side=THUMBNAIL_MAX_SIDE, name='thumbnail.webp')
        services.set_video_thumbnail(video_id=video.pk, thumbnail=thumbnail)
    except Exception:
        # A video without a thumbnail is still a working video (docs D3.5).
        logger.warning('Thumbnail of video %s could not be made', video.pk, exc_info=True)


@shared_task
def analyse_video(video_id):
    """Thumbnail + analysis of a normalized video. Queued by normalize_video_file."""
    video = Video.objects.defer('json_analysis').filter(pk=video_id).first()
    if video is None:  # deleted meanwhile
        return

    if not video.thumbnail:
        _make_thumbnail(video)

    try:
        result = run_analysis(video.path_to_resource.path)
    except Exception:
        logger.exception('Analysis of video %s failed', video_id)
        services.set_analysis_result(
            video_id=video_id, status=AnalysisStatus.FAILED, error_code=AnalysisError.ANALYSIS_FAILED,
        )
        return

    services.set_analysis_result(video_id=video_id, status=AnalysisStatus.DONE, json_analysis=result)
