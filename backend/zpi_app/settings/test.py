"""Settings for the test suite: `python manage.py test --settings=zpi_app.settings.test`."""

from .dev import *  # noqa: F401,F403
from .base import BASE_DIR

# Fast password hashing: the default (PBKDF2) is deliberately slow.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Keep uploaded test files out of the real media folder.
MEDIA_ROOT = BASE_DIR / 'test_media'

# No Redis in tests: an in-memory cache (holds the rate-limit counters; tests clear it in setUp).
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

# Run tasks right away in the test process (no Redis, no worker needed).
CELERY_TASK_ALWAYS_EAGER = True
