"""
Settings shared by every environment (dev, prod, test).

Environment-specific modules (dev.py, prod.py, test.py) do `from .base import *`
and override only what differs. Anything secret or deployment-specific is read
from environment variables (see backend/.env.example), never hardcoded here.

https://docs.djangoproject.com/en/6.1/topics/settings/
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# backend/ — one more .parent than the startproject default, because this file
# now lives in zpi_app/settings/ instead of zpi_app/.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name, default=None):
    """Read an environment variable; fail loudly if it's required but missing."""
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Set the {name} environment variable.")
    return value


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# SECRET_KEY is set per environment: dev.py has an insecure fallback,
# prod.py requires DJANGO_SECRET_KEY.

DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    # Local
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'zpi_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'zpi_app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env("POSTGRES_DB"),
        'USER': env("POSTGRES_USER"),
        'PASSWORD': env("POSTGRES_PASSWORD"),
        'HOST': env("POSTGRES_HOST", "localhost"),
        'PORT': env("POSTGRES_PORT", "5432"),
        # We serve via ASGI, where Django's persistent connections (CONN_MAX_AGE)
        # are unsafe — each async request may run on a different thread and leak
        # connections. Instead each process keeps a psycopg connection pool:
        # connections are opened once and borrowed/returned per request.
        # https://docs.djangoproject.com/en/6.1/ref/databases/#connection-pool
        'CONN_MAX_AGE': 0,
        'OPTIONS': {
            'pool': {
                'min_size': 1,
                'max_size': int(env("POSTGRES_POOL_MAX_SIZE", "10")),
                # Fail a request after 10 s if no connection frees up, rather than hang.
                'timeout': 10,
            },
        },
    }
}


# Custom user model. Must be set before the first migration: swapping it later
# means rewriting the auth tables by hand.
# https://docs.djangoproject.com/en/6.1/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project

AUTH_USER_MODEL = 'accounts.User'


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'
# Where `collectstatic` gathers files for the web server in production.
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Media files (user uploads, e.g. dance videos)
# Stored on local disk for now; switching to S3 later only changes STORAGES.

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


# Django REST Framework
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    # Session auth = the browser's login cookie + CSRF token. Works with <video src>.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    # Secure by default: every endpoint requires login unless it opts out.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

# Real SMTP by default; dev.py swaps in the console backend.

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'OPTIONS': {
            'host': env("EMAIL_HOST", "localhost"),
            'port': int(env("EMAIL_PORT", "587")),
            'username': env("EMAIL_HOST_USER", ""),
            'password': env("EMAIL_HOST_PASSWORD", ""),
            'use_tls': env_bool("EMAIL_USE_TLS", True),
        },
    },
}
