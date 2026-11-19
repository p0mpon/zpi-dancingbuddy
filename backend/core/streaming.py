"""
Sending a file with HTTP Range support, so a <video> player can seek.

The player doesn't ask for "second 30"; it reads the file's index, works out the byte
offset itself and sends `Range: bytes=12345678-`. We answer 206 Partial Content with
only those bytes. Django's FileResponse can't do this (it always sends the whole file).
https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests

Production: Django should only check permissions and let nginx send the bytes
(X-Accel-Redirect header); nginx handles Range itself and is much faster at it.
"""

from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header

CHUNK_SIZE = 64 * 1024  # bytes read from disk and sent per step


class RangeNotSatisfiable(Exception):
    """The requested range starts at or after the end of the file (answer 416)."""


def parse_range_header(header, size):
    """Turn a Range header into (start, end), both inclusive, for a file of `size` bytes.

        'bytes=0-99'   -> (0, 99)          first 100 bytes
        'bytes=100-'   -> (100, size - 1)  from byte 100 to the end
        'bytes=-100'   -> (size - 100, size - 1)  last 100 bytes

    Returns None when the header is missing, malformed or asks for several ranges:
    the caller then sends the whole file, which the HTTP spec allows.
    Raises RangeNotSatisfiable when the range starts past the end of the file.
    """
    if not header or not header.startswith('bytes='):
        return None
    value = header.removeprefix('bytes=').strip()
    if ',' in value:  # several ranges: rare, ignore
        return None
    start_text, dash, end_text = value.partition('-')
    if not dash:
        return None
    start_text, end_text = start_text.strip(), end_text.strip()

    if start_text == '':  # 'bytes=-N': the last N bytes
        if not end_text.isdecimal():
            return None
        suffix_length = int(end_text)
        if suffix_length == 0 or size == 0:
            raise RangeNotSatisfiable()
        return max(size - suffix_length, 0), size - 1

    if not start_text.isdecimal():
        return None
    start = int(start_text)
    if end_text == '':
        end = size - 1
    elif end_text.isdecimal():
        end = int(end_text)
    else:
        return None
    # Checked before end < start: for 'bytes=1000-' on a 1000-byte file, end defaults to 999.
    if start >= size:
        raise RangeNotSatisfiable()
    if end < start:
        return None
    return start, min(end, size - 1)  # an END past the file just means "to the end"


def read_chunks(file, start, end):
    """Yield bytes start..end (inclusive) of an open file, CHUNK_SIZE at a time, then close it."""
    with file:
        file.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = file.read(min(CHUNK_SIZE, remaining))
            if not chunk:  # file shorter than expected
                break
            remaining -= len(chunk)
            yield chunk


def range_file_response(request, file_field, content_type, *, as_attachment=False, filename=None):
    """Respond with the file of a FileField: 200 (whole file), 206 (one range) or 416."""
    size = file_field.size

    try:
        byte_range = parse_range_header(request.headers.get('Range'), size)
    except RangeNotSatisfiable:
        response = HttpResponse(status=416)
        response['Content-Range'] = f'bytes */{size}'  # tells the client the real size
        return response

    file = file_field.storage.open(file_field.name, 'rb')

    if byte_range is None:
        # No (usable) Range header: the whole file. FileResponse also streams in chunks.
        response = FileResponse(file, content_type=content_type, as_attachment=as_attachment, filename=filename)
    else:
        start, end = byte_range
        # A generator: only CHUNK_SIZE bytes are in memory at a time, never the whole file.
        response = StreamingHttpResponse(read_chunks(file, start, end), status=206, content_type=content_type)
        response['Content-Length'] = str(end - start + 1)
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
        disposition = content_disposition_header(as_attachment, filename)  # None without a filename
        if disposition:
            response['Content-Disposition'] = disposition

    # Tells the player it may send Range requests (needed for seeking).
    response['Accept-Ranges'] = 'bytes'
    return response
