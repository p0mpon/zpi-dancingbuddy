"""
Generic image helpers built on Pillow.

Pure: a file goes in, a ContentFile comes out. No DB, no storage, no request, no models.
Used by `accounts` (avatars) now and by `videos` (thumbnails) later; callers decide sizes and names.
"""

import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

DEFAULT_WEBP_QUALITY = 80

# What Pillow raises for files that passed header checks but can't be decoded / converted / encoded.
_PILLOW_ERRORS = (OSError, ValueError, Image.DecompressionBombError)


class ImageProcessingError(Exception):
    """The file passed Django's checks but Pillow couldn't decode or convert it."""


def load_image(file):
    """Reopen an uploaded image, turn it upright, convert to RGB / RGBA.

    Returns (image, icc_profile). Raises ImageProcessingError.
    """
    try:
        # Reopen: the Pillow object in `file.image` was used by verify() and can't read pixels any more.
        file.seek(0)
        image = Image.open(file)

        # Read the ICC profile before converting: conversion drops it.
        icc_profile = image.info.get('icc_profile')

        # Phones store "rotate me" in EXIF instead of rotating the pixels; without this
        # some images would come out sideways.
        image = ImageOps.exif_transpose(image)

        # Keep transparency (WebP supports it); everything else (L, P, CMYK, I;16, ...) becomes RGB.
        has_alpha = image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info)
        image = image.convert('RGBA' if has_alpha else 'RGB')
    except _PILLOW_ERRORS as error:
        raise ImageProcessingError('Image could not be processed.') from error
    return image, icc_profile


def save_webp(image, *, name, quality=DEFAULT_WEBP_QUALITY, icc_profile=None):
    """Encode as WebP without EXIF (it is simply not passed on). Returns a ContentFile called `name`."""
    options = {'format': 'WEBP', 'quality': quality}
    if icc_profile is not None:
        options['icc_profile'] = icc_profile
    buffer = io.BytesIO()
    try:
        image.save(buffer, **options)
    except _PILLOW_ERRORS as error:
        raise ImageProcessingError('Image could not be processed.') from error
    return ContentFile(buffer.getvalue(), name=name)


def make_square_webp(file, *, size, name, quality=DEFAULT_WEBP_QUALITY):
    """Centre-crop to a square, resize to size x size, save as WebP."""
    image, icc_profile = load_image(file)
    try:
        # fit() crops the largest centred square and resizes it in one call (also upscales small images).
        image = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS)
    except _PILLOW_ERRORS as error:
        raise ImageProcessingError('Image could not be processed.') from error
    return save_webp(image, name=name, quality=quality, icc_profile=icc_profile)
