from django.core import serializers
from rest_framework.exceptions import ValidationError


ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'mov', 'webm']

MAX_VIDEO_SIZE_MB = 500
MAX_VIDEO_SIZE_BYTES = MAX_VIDEO_SIZE_MB * 1024 * 1024

# --------------- FILE VALIDATION ---------------
def validate_filename(file):
    """The file name must end with an allowed video extension."""
    if file.name.rsplit('.', 1)[-1].lower() not in ALLOWED_VIDEO_EXTENSIONS:
        raise serializers.ValidationError(f"Allowed file types: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}.")

def validate_file_size(file):
    """The file must not be larger than MAX_VIDEO_SIZE_MB."""
    if file.size > MAX_VIDEO_SIZE_BYTES:
        raise serializers.ValidationError(f'File is too large (max {MAX_VIDEO_SIZE_MB} MB).')

def validate_video_file(file):
    """Shared by upload only (POST)"""
    validate_filename(file)
    validate_file_size(file)
    return file

# --------------- ID VALIDATION ---------------
def parse_positive_int_param(value, param_name="parameter"):
    """
    Safely parses a URL query parameter into a positive integer.
    Returns None if the parameter is missing.
    """
    if value in (None, ''):
        return None
        
    try:
        val = int(value)
        if val <= 0:
            raise ValueError
        return val
    except (ValueError, TypeError):
        raise ValidationError({param_name: "Must be a positive integer."})