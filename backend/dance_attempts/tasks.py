import logging
from celery import shared_task
from videos.models import AnalysisStatus
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
    """Analyse one dance attempt. Queued by services.create_attempt()."""
    attempt = DanceAttempt.objects.filter(pk=attempt_id).first()
    if attempt is None:
        return

    started = services.set_attempt_result(
        attempt_id=attempt_id, 
        status=AnalysisStatus.PROCESSING, 
    )
    if not started:
        logger.info('Analysis of attempt %s skipped: deleted', attempt_id)
        return

    video = attempt.reference_video
    if video is None:
        logger.error('Analysis of attempt %s failed: reference video was deleted', attempt_id)
        services.set_attempt_result(
            attempt_id=attempt_id,
            status=AnalysisStatus.FAILED,
        )
        return

    try:
        score_details, score = run_score_analysis(
            video.json_analysis,
            attempt.json_analysis,
        )
    except Exception:
        logger.exception('Analysis of attempt %s failed', attempt_id)
        services.set_attempt_result(
            attempt_id=attempt_id, 
            status=AnalysisStatus.FAILED, 
        )
        return

    services.set_attempt_result(
        attempt_id=attempt_id, 
        status=AnalysisStatus.DONE, 
        score=score, 
        score_details=score_details, 
    )