from django.http import Http404


class VideoNotReadyError(Exception):
    """Raised when a video is not ready for analysis."""

class AttemptNotFailedError(Exception):
    """Raised when trying to reanalyze an attempt that hasn't failed."""

class VideoNotFoundError(Http404):
    """Raised when a video is not found or is not accessible."""