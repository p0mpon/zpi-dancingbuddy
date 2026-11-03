"""
Celery tasks for videos. They run in the celery-worker container, not in the web request.

Flow: services.start_analysis() -> analyse_video.delay(id) puts a message on Redis ->
the worker runs analyse_video(id) -> status 'processing' -> run_analysis() ->
status 'done' + json_analysis, or 'failed'.
Like views, tasks don't write to the DB themselves; they call videos/services.py.
"""

import logging

from celery import shared_task

from . import services
from .models import AnalysisStatus, Video

logger = logging.getLogger(__name__)


def run_analysis(file_path):
    """Analyse the video file at file_path and return the value for json_analysis."""
    # TODO: connect the analysis entry point here (pose detection with MediaPipe, ...).
    # It gets the absolute path of the video file and must return JSON-serialisable data.
    # The format isn't decided yet (list of Frame vs DAN-35's ChoreoData).
    # Until then every analysis ends as 'failed'.
    raise NotImplementedError('Video analysis is not connected yet.')


@shared_task
def analyse_video(video_id):
    """Analyse one video. Queued by services.start_analysis() after an upload or a new file."""
    video = Video.objects.filter(pk=video_id).first()
    if video is None:  # deleted before the worker got to it
        return

    # Remember which file is analysed: if PATCH replaces it meanwhile, every write
    # below is skipped, so a result for the old file never lands on the new one.
    file_name = video.path_to_resource.name
    started = services.set_analysis_result(
        video_id=video_id, file_name=file_name, status=AnalysisStatus.PROCESSING,
    )
    if not started:
        # Not an error: deleted or given a new file (which queued its own task) in the meantime.
        logger.info('Analysis of video %s skipped: deleted or file replaced', video_id)
        return

    try:
        # .path works for files on local disk (FileSystemStorage); S3 would need a download first.
        result = run_analysis(video.path_to_resource.path)
    except Exception:
        logger.exception('Analysis of video %s failed', video_id)
        services.set_analysis_result(video_id=video_id, file_name=file_name, status=AnalysisStatus.FAILED)
        return

    services.set_analysis_result(
        video_id=video_id, file_name=file_name, status=AnalysisStatus.DONE, json_analysis=result,
    )
