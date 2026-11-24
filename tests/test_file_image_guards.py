"""Synthetic regressions for bounded WebP decoding and stable file grants."""
import base64
from contextlib import contextmanager
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from rdc.config import Settings
from rdc.errors import RDCError
from rdc.files import Files


class FileImageGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'workspace'
        self.root.mkdir()
        self.settings = Settings(self.base / 'state', [self.root])
        self.files = Files(self.settings)

    def fixture(self, name, *, mode='RGB', size=(80, 60), color=(12, 91, 156), **options):
        path = self.root / name
        with Image.new(mode, size, color) as image:
            image.save(path, **options)
        return path

    def decoded(self, result):
        return Image.open(io.BytesIO(base64.b64decode(result['data'], validate=True)))

    def test_webp_canvas_limit_precedes_decoder(self):
        # A small encoded container can declare a huge native canvas. The
        # allocation must be refused before Pillow constructs its WebP decoder.
        dimensions = (4999).to_bytes(3, 'little') * 2
        extended = b'VP8X' + (10).to_bytes(4, 'little') + bytes(4) + dimensions
        bits = 4999 | (4999 << 14)
        payload = b'\x2f' + bits.to_bytes(4, 'little')
        frame = b'VP8L' + len(payload).to_bytes(4, 'little') + payload + b'\0'
        body = b'WEBP' + extended + frame
        path = self.root / 'large-canvas.webp'
        path.write_bytes(b'RIFF' + len(body).to_bytes(4, 'little') + body)
        with patch('PIL.Image.open', side_effect=AssertionError('WebP decoder must not be created for an oversized canvas')) as opened:
            with self.assertRaises(RDCError) as error:
                self.files.read(str(path))
        self.assertEqual('image_too_large', error.exception.code)
        opened.assert_not_called()

    def test_parent_swap_refused(self):
        current = self.root / 'current'
        replacement = self.root / 'replacement'
        current.mkdir()
        replacement.mkdir()
        path = current / 'fixture.png'
        with Image.new('RGB', (80, 60), (12, 91, 156)) as image:
            image.save(path)
        # Prepare both links before inspection so the descriptor's inode,
        # content, timestamps and link count stay unchanged during the swap.
        os.link(path, replacement / path.name)
        original_open = self.files._open_regular

        class SwappingSource:
            def __init__(self, source):
                self.source = source
                self.swapped = False

            def __getattr__(self, name):
                return getattr(self.source, name)

            def read(self, amount=-1):
                data = self.source.read(amount)
                if amount > 16 and not self.swapped:
                    self.swapped = True
                    current.rename(self.root / 'retired')
                    replacement.rename(current)
                return data

        @contextmanager
        def swapping_open(open_path):
            with original_open(open_path) as source:
                proxy = SwappingSource(source)
                proxy.root = self.root
                yield proxy

        with patch.object(self.files, '_open_regular', swapping_open):
            with self.assertRaises(RDCError) as error:
                self.files.read(str(path))
        self.assertEqual('conflict', error.exception.code)

    def test_lossy_webp_preview(self):
        path = self.fixture('lossy.webp', format='WEBP', quality=80)
        raw = path.read_bytes()
        self.assertEqual(b'VP8 ', raw[12:16])
        result = self.files.read(str(path), mode='image')
        self.assertEqual('WEBP', result['source_format'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['sha256'])
        with self.decoded(result) as decoded:
            decoded.load()
            self.assertEqual((80, 60), decoded.size)

    def test_lossless_webp_preview(self):
        path = self.fixture('lossless.data', format='WEBP', lossless=True)
        self.assertEqual(b'VP8L', path.read_bytes()[12:16])
        result = self.files.read(str(path))
        self.assertEqual('WEBP', result['source_format'])
        self.assertFalse(result['first_frame_only'])
        with self.decoded(result) as decoded:
            self.assertEqual((12, 91, 156), decoded.convert('RGB').getpixel((0, 0)))

    def test_extended_webp_preview(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = 'synthetic metadata'
        path = self.fixture('extended.webp', mode='RGBA', color=(12, 91, 156, 128),
                            format='WEBP', lossless=True, exif=exif)
        self.assertEqual(b'VP8X', path.read_bytes()[12:16])
        result = self.files.read(str(path), mode='image')
        self.assertEqual((60, 80), (result['width'], result['height']))
        self.assertEqual('white', result['transparency_background'])
        with self.decoded(result) as decoded:
            self.assertFalse(decoded.getexif())
            self.assertNotIn('exif', decoded.info)

    def test_auto_missing_text_keeps_not_found(self):
        from rdc.engine import Engine
        engine = Engine(self.settings)
        try:
            result = engine.call('rdc_file_read', {'file_path': str(self.root / 'missing.txt')})
            self.assertFalse(result['ok'])
            self.assertEqual('not_found', result['error']['code'])
        finally:
            engine.close()

    def test_real_mcp_image_and_text_compatibility(self):
        import anyio
        from mcp import Client
        from PIL.PngImagePlugin import PngInfo
        from rdc.engine import Engine
        from rdc.server import create_mcp_server

        metadata = PngInfo()
        metadata.add_text('Comment', 'synthetic metadata')
        image_path = self.root / 'palette.png'
        with Image.new('P', (80, 60), 0) as image:
            image.putpalette([12, 91, 156] + [0] * 765)
            image.save(image_path, transparency=0, pnginfo=metadata)
        text_path = self.root / 'notes.txt'
        text_path.write_bytes(b'BM report: ordinary UTF-8 text')
        engine = Engine(self.settings)

        async def exchange():
            async with Client(create_mcp_server(engine)) as client:
                result = await client.call_tool('rdc_file_read', {'file_path': str(image_path)})
                images = [part for part in result.content if part.type == 'image']
                self.assertEqual(1, len(images))
                self.assertNotIn('data', result.structured_content)
                self.assertEqual('image', result.structured_content['kind'])
                self.assertNotIn(images[0].data, ''.join(part.text for part in result.content if part.type == 'text'))
                with Image.open(io.BytesIO(base64.b64decode(images[0].data, validate=True))) as decoded:
                    self.assertEqual((255, 255, 255), decoded.convert('RGB').getpixel((0, 0)))
                    self.assertNotIn('Comment', decoded.info)
                text = await client.call_tool('rdc_file_read', {
                    'file_path': str(text_path), 'mode': 'text', 'offset': 3, 'limit': 6})
                self.assertEqual('report', text.structured_content['text'])
                self.assertEqual(9, text.structured_content['next_offset'])
                self.assertTrue(all(part.type == 'text' for part in text.content))

        try:
            anyio.run(exchange)
        finally:
            engine.close()
