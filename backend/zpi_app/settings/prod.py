"""
Production settings (default for wsgi.py).

Run `python manage.py check --deploy --settings=zpi_app.settings.prod`
to have Django audit these.
https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/
"""

from .base import *  # noqa: F401,F403
from .base import env, env_bool, env_list

DEBUG = False

# No fallbacks here: a missing value should stop the server from starting.
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
# Needed when the site is served over HTTPS on a domain (Django checks Origin).
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# HTTPS hardening. If TLS terminates at a reverse proxy, it must send
# X-Forwarded-Proto so Django knows the original request was HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Start small; raise to a year (31536000) once HTTPS is confirmed working,
# because browsers cache this and refuse plain HTTP until it expires.
SECURE_HSTS_SECONDS = int(env("DJANGO_SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
