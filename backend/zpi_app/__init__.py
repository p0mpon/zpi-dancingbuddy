# Load the Celery app whenever Django starts, so task.delay() uses its config.
from .celery import app as celery_app

__all__ = ('celery_app',)
