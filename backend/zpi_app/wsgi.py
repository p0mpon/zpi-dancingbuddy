"""
WSGI config for zpi_app project.

Only used by `manage.py runserver` in development (via WSGI_APPLICATION).
Production runs on ASGI — see asgi.py.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zpi_app.settings.dev')

application = get_wsgi_application()
