"""
Celery tasks for dance attempts (run by the celery-worker). Two independent tasks, queued together
by services.create_attempt():
  analyse_attempt              compares the attempt's MediaPipe JSON with the reference video's JSON
  normalize_attempt_recording  re-encodes the recording as the standard MP4 (core/ffmpeg.py)
The score doesn't need the recording, so neither task waits for the other. If normalization fails,
the attempt keeps its score and the original recording (is_normalized stays False).
"""

import logging
import tempfile
from pathlib import Path

from celery import shared_task

from core.ffmpeg import FFmpegError, FFmpegTimeout, normalize_video, probe_video
from videos.models import NORMALIZE_RETRY_DELAYS_SECONDS, AnalysisError, AnalysisStatus
from .models import DanceAttempt
from dance_attempts import services
from video_analysis.raw_frame_processor import process_raw_frames
from full_analysis.choreo_comparator import compare_choreos
from full_analysis.choreo_data_model import ChoreoFrame

logger = logging.getLogger(__name__)


def run_score_analysis(
    reference_video_data: list[dict],
    mediapipe_data: list[dict],
) -> tuple[list[dict], int]:
    """
    Processes the raw frames from mediapipe, then compares them to the reference video
    using the scoring algorithm. Returns a tuple of (score, score_details).
    Args:
        reference_video_data (list[dict]): List of choreo frames with joint data and weights from the reference video.
        mediapipe_data (list[RawFrame]): List of frames with joint data from the MediaPipe model.
    Returns:
        tuple[list[dict], int]: Serialized score details and the overall score.
    """
    if (not reference_video_data or not mediapipe_data):
        logger.error("Reference video data or mediapipe data is empty.")
        raise ValueError("Reference video data or mediapipe data is empty.")
    
    reference_frames = [
        frame if isinstance(frame, ChoreoFrame)
        else ChoreoFrame.model_validate(frame)
        for frame in reference_video_data
    ]
    processed_frames = process_raw_frames(mediapipe_data)
    scored_frames, score = compare_choreos(reference_frames, processed_frames)
    return [frame.model_dump() for frame in scored_frames], score


@shared_task
def analyse_attempt(attempt_id: int):
    """Score one dance attempt. Queued by services.create_attempt() and reanalyze."""
    attempt = DanceAttempt.objects.select_related('reference_video').filter(pk=attempt_id).first()
    if attempt is None:
        return

    if not services.mark_attempt_processing(attempt_id=attempt_id):
        logger.info('Analysis of attempt %s skipped: deleted', attempt_id)
        return

    video = attempt.reference_video
    try:
        if video is None:
            raise ValueError('The reference video was deleted.')
        score_details, score = run_score_analysis(video.json_analysis, attempt.json_analysis)
    except Exception:
        logger.exception('Analysis of attempt %s failed', attempt_id)
        services.set_attempt_result(
            attempt_id=attempt_id, status=AnalysisStatus.FAILED, error_code=AnalysisError.ANALYSIS_FAILED,
        )
        return

    services.set_attempt_result(
        attempt_id=attempt_id, status=AnalysisStatus.DONE, score=score, score_details=score_details,
    )


@shared_task(bind=True, max_retries=len(NORMALIZE_RETRY_DELAYS_SECONDS))
def normalize_attempt_recording(self, attempt_id: int):
    """Normalize the recording into a temp file, then let the service move it to dance_attempt/normalized/.
    Timeouts and unexpected errors are retried."""
    attempt = DanceAttempt.objects.defer('json_analysis', 'score_details').filter(pk=attempt_id).first()
    if attempt is None or not attempt.recording or attempt.is_normalized:
        return

    delay = NORMALIZE_RETRY_DELAYS_SECONDS[min(self.request.retries, len(NORMALIZE_RETRY_DELAYS_SECONDS) - 1)]
    try:
        raw_path = attempt.recording.path   # .path works for local disk (FileSystemStorage)
        info = probe_video(raw_path)        # also None when the file is missing
        if info is None:
            logger.error('Recording of attempt %s is not readable', attempt_id)
            return
        with tempfile.TemporaryDirectory() as temp_dir:     # removed even if something raises
            output = Path(temp_dir) / 'normalized.mp4'
            normalize_video(raw_path, output, has_audio=info.has_audio)     # the raw file is only read
            services.update_attempt_recording(attempt_id=attempt_id, new_path=output)
    except FFmpegTimeout as error:      # a busy server: worth another try
        raise self.retry(exc=error, countdown=delay)
    except FFmpegError:                 # ffmpeg refused the file: the same file would fail again
        logger.exception('Recording of attempt %s could not be normalized', attempt_id)
    except Exception as error:
        logger.exception('Normalization of attempt %s failed unexpectedly', attempt_id)
        raise self.retry(exc=error, countdown=delay)
