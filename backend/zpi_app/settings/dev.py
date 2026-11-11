"""Local development settings (default for manage.py and wsgi.py)."""

from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK, env, env_list

DEBUG = True

# Falls back to an insecure key so a fresh checkout runs; never used in prod.
SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-only-key")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:3000" )

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:3000"
)

# Print emails (e.g. password resets) to the console instead of sending them.
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

# Dev only: Basic Auth lets Postman send username/password on each request,
# without logging in and copying the CSRF token. Never enable this in prod.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 20,
}
