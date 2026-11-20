"""Tests for core/images.py. Pure Pillow, no DB: inputs are built in memory."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from core.images import ImageProcessingError, make_square_webp

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
TOLERANCE = 30   # WebP is lossy: colours are close, not equal


def upload(image, image_format='PNG', **save_options):
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, **save_options)
    return SimpleUploadedFile(f'in.{image_format.lower()}', buffer.getvalue())


def stripes(size, *, vertical):
    """Red | green | blue bands (left to right, or top to bottom when vertical).

    Green is the middle square (the part that survives the crop); red and blue are the cut-off edges.
    """
    image = Image.new('RGB', size)
    length, other = (size[1], size[0]) if vertical else (size[0], size[1])
    edge = (length - other) // 2
    for colour, start, end in [(RED, 0, edge), (GREEN, edge, length - edge), (BLUE, length - edge, length)]:
        image.paste(colour, (0, start, other, end) if vertical else (start, 0, end, other))
    return image


def open_result(content_file):
    return Image.open(io.BytesIO(content_file.read()))


class ImageTestCase(SimpleTestCase):
    def assertColour(self, pixel, expected):
        for got, want in zip(pixel, expected):
            self.assertAlmostEqual(got, want, delta=TOLERANCE, msg=f'{pixel} is not close to {expected}')


class MakeSquareWebpTests(ImageTestCase):
    def test_png_and_jpeg_become_512_webp(self):
        for image_format in ['PNG', 'JPEG']:
            with self.subTest(format=image_format):
                result = make_square_webp(upload(Image.new('RGB', (40, 30), RED), image_format),
                                          size=512, name='x.webp')
                self.assertEqual(result.name, 'x.webp')
                image = open_result(result)
                self.assertEqual(image.format, 'WEBP')
                self.assertEqual(image.size, (512, 512))

    def test_size_is_respected(self):
        image = open_result(make_square_webp(upload(Image.new('RGB', (40, 30), RED)), size=64, name='x.webp'))
        self.assertEqual(image.size, (64, 64))

    def test_landscape_keeps_the_middle(self):
        image = open_result(make_square_webp(upload(stripes((600, 300), vertical=False)), size=512, name='x.webp'))
        for x in (5, 256, 500):
            self.assertColour(image.convert('RGB').getpixel((x, 256)), GREEN)

    def test_portrait_keeps_the_middle(self):
        image = open_result(make_square_webp(upload(stripes((300, 600), vertical=True)), size=512, name='x.webp'))
        for y in (5, 256, 500):
            self.assertColour(image.convert('RGB').getpixel((256, y)), GREEN)

    def test_tiny_image_is_upscaled(self):
        image = open_result(make_square_webp(upload(Image.new('RGB', (8, 8), RED)), size=512, name='x.webp'))
        self.assertEqual(image.size, (512, 512))

    def test_exif_orientation_turns_image_upright(self):
        source = Image.new('RGB', (200, 100), RED)
        source.paste(BLUE, (100, 0, 200, 100))   # left half red, right half blue
        exif = Image.Exif()
        exif[0x0112] = 6                          # "rotate 90 degrees clockwise to display"
        image = open_result(make_square_webp(upload(source, 'JPEG', exif=exif), size=512, name='x.webp'))
        image = image.convert('RGB')
        self.assertColour(image.getpixel((256, 80)), RED)    # the left side is now on top
        self.assertColour(image.getpixel((256, 432)), BLUE)

    def test_exif_is_removed(self):
        exif = Image.Exif()
        exif[0x010F] = 'SomeCameraMaker'
        exif[0x0132] = '2026:01:01 10:00:00'
        source = upload(Image.new('RGB', (40, 40), RED), 'JPEG', exif=exif)
        self.assertTrue(Image.open(io.BytesIO(source.read())).getexif())   # the input really has EXIF
        source.seek(0)
        image = open_result(make_square_webp(source, size=64, name='x.webp'))
        self.assertEqual(len(image.getexif()), 0)

    def test_rgba_keeps_transparency(self):
        source = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        source.paste((255, 0, 0, 255), (40, 40, 60, 60))
        image = open_result(make_square_webp(upload(source), size=128, name='x.webp'))
        self.assertEqual(image.mode, 'RGBA')
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertGreater(image.getpixel((64, 64))[3], 200)

    def test_palette_png_with_transparency_becomes_rgba(self):
        source = Image.new('P', (20, 20), 0)
        source.putpalette([255, 0, 0] * 256)
        image = open_result(make_square_webp(upload(source, transparency=0), size=64, name='x.webp'))
        self.assertEqual(image.mode, 'RGBA')

    def test_other_modes_become_rgb(self):
        cases = [('L', 'PNG'), ('CMYK', 'JPEG')]
        for mode, image_format in cases:
            with self.subTest(mode=mode):
                result = make_square_webp(upload(Image.new(mode, (20, 20)), image_format), size=64, name='x.webp')
                self.assertEqual(open_result(result).mode, 'RGB')

    def test_broken_file_raises(self):
        data = upload(Image.new('RGB', (200, 200), RED)).read()
        broken = SimpleUploadedFile('in.png', data[:len(data) // 2])
        with self.assertRaises(ImageProcessingError):
            make_square_webp(broken, size=64, name='x.webp')
