import logging
import random
from celery import shared_task
from videos.models import AnalysisStatus
from .models import DanceAttempt
from dance_attempts import services

logger = logging.getLogger(__name__)

def run_score_analysis(mediapipe_data):
    """
    Placeholder for the actual AI scoring logic.
    Accepts the parsed mediapipe_data list/dict from the frontend.
    Returns a tuple: (score, json_analysis, score_details)
    """
    # TODO: Integrate the parsing + comparator logic here.
    
    dummy_score = int(random.random() * 100)  # Random score between 0 and 100
    dummy_details = [{"timestamp": 0.0, "frames": []}]
    
    return dummy_score, dummy_details

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

    try:
        score, score_details = run_score_analysis(attempt.json_analysis)
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