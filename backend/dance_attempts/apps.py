from django.apps import AppConfig


class DanceAttemptsConfig(AppConfig):
    name = 'dance_attempts'

    def ready(self):
        from . import signals  # noqa: F401  connects the post_delete file cleanup
