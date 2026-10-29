"""Local development settings (default for manage.py and wsgi.py)."""

from .base import *  # noqa: F401,F403
from .base import env, env_list

DEBUG = True

# Falls back to an insecure key so a fresh checkout runs; never used in prod.
SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-only-key")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")

# Print emails (e.g. password resets) to the console instead of sending them.
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}
