"""
Every write for videos goes through here: creating/updating/deleting rows and the
files on disk. Views validate the request with a serializer, then call one of these.

Plain functions with keyword-only arguments, so a call reads like a sentence:
upload_video(owner=user, title='Salsa', file=f). They know nothing about HTTP.
"""

from .models import Video


def upload_video(*, owner, title, file, description=''):
    """Store the uploaded file and create its Video row. analysis_status defaults to pending."""
    # Saving the row writes the file first (FileField.pre_save -> storage.save, path from
    # video_upload_path), then runs the INSERT.
    # Known limitation: if the INSERT fails, the file stays on disk (orphaned).
    return Video.objects.create(
        owner=owner,
        title=title,
        description=description,
        path_to_resource=file,
        file_size=float(file.size),
    )
