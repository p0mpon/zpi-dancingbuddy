"""
Celery app: runs background jobs (video analysis) in a separate worker process.

Start a worker with `celery -A zpi_app worker` (docker compose does this in the
celery-worker service). Django puts a job on the Redis queue with task.delay(...);
the worker takes it from there and runs it.
https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html
"""

import os

from celery import Celery

# Same default as manage.py; .env overrides it.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zpi_app.settings.dev')

app = Celery('zpi_app')
# Every Django setting starting with CELERY_ configures Celery (CELERY_BROKER_URL -> broker_url).
app.config_from_object('django.conf:settings', namespace='CELERY')
# Finds tasks.py in every installed app (videos/tasks.py).
app.autodiscover_tasks()
