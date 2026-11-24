import base64
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from rdc.config import Settings
from rdc.errors import RDCError
from rdc.files import Files


class FileImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'workspace'
        self.root.mkdir()
        self.settings = Settings(self.base/'state', [self.root])
        self.files = Files(self.settings)

    def image(self, name='fixture.png', fmt='PNG', size=(80, 60), **options):
        path = self.root/name
        with Image.new('RGB',size,(12,91,156)) as image:
            image.save(path,format=fmt,**options)
        return path

    def test_01_automatic_png_visual_read(self):
        path=self.image()
        result=self.files.read(str(path))
        self.assertEqual('image/png',result['mime_type'])
        self.assertNotIn('text',result)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),result['sha256'])
        with Image.open(io.BytesIO(base64.b64decode(result['data'],validate=True))) as decoded:
            self.assertEqual((80,60),decoded.size)
            self.assertEqual((12,91,156),decoded.convert('RGB').getpixel((0,0)))


    def test_02_content_detection_ignores_extension(self):
        path=self.image('fixture.txt','JPEG')
        result=self.files.read(str(path))
        self.assertEqual(result['source_format'],'JPEG')
        self.assertEqual(result['kind'],'image')

    def test_03_ordinary_text_pagination_unchanged(self):
        path=self.root/'fixture.txt'
        path.write_bytes(b'BM report: ordinary UTF-8 text')
        result=self.files.read(str(path),offset=3,limit=6)
        self.assertEqual('report',result['text'])
        self.assertEqual(9,result['next_offset'])
        self.assertTrue(result['truncated'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),result['sha256'])

    def test_04_unsupported_explicit_image_is_rejected(self):
        path=self.root/'fixture.svg'
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        with self.assertRaises(RDCError) as err:
            self.files.read(str(path),mode='image')
        self.assertEqual('unsupported_image',err.exception.code)

    def test_05_malformed_raster_is_rejected(self):
        path=self.root/'corrupt.png'
        path.write_bytes(bytes.fromhex('89504e470d0a1a0a')+b'broken')
        with self.assertRaises(RDCError) as err:
            self.files.read(str(path))
        self.assertEqual('invalid_image',err.exception.code)

    def test_06_raster_pagination_does_not_leak_binary(self):
        path=self.image()
        with self.assertRaises(RDCError) as err:
            self.files.read(str(path),offset=4,limit=10)
        self.assertEqual('image_read_required',err.exception.code)
        with self.assertRaises(RDCError) as err:
            self.files.read(str(path),mode='image',limit=10)
        self.assertEqual('invalid_arguments',err.exception.code)

    def test_07_preview_size_and_aspect(self):
        path=self.image(size=(2400,1200))
        result=self.files.read(str(path),max_edge=640)
        self.assertEqual((2400,1200),(result['source_width'],result['source_height']))
        self.assertEqual((640,320),(result['width'],result['height']))
        self.assertEqual(path.stat().st_size,result['size'])

    def test_08_preserves_original_hash_and_strips_metadata(self):
        from PIL.PngImagePlugin import PngInfo
        meta=PngInfo()
        meta.add_text('Comment','synthetic metadata that must not be forwarded')
        path=self.image(pnginfo=meta)
        raw=path.read_bytes()
        result=self.files.read(str(path))
        with Image.open(io.BytesIO(base64.b64decode(result['data']))) as decoded:
            self.assertNotIn('Comment',decoded.info)
        self.assertTrue(result['metadata_removed'])
        self.assertEqual(raw,path.read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),result['sha256'])

    def test_09_oversized_source_refused_before_decode(self):
        path=self.root/'oversize.png'
        with path.open('wb') as handle:
            handle.write(bytes.fromhex('89504e470d0a1a0a'))
            handle.truncate(32*1024*1024+1)
        with self.assertRaises(RDCError) as err:
            self.files.read(str(path))
        self.assertEqual('image_too_large',err.exception.code)

    def test_10_pixel_limit_is_enforced(self):
        from unittest.mock import patch
        path=self.image(size=(100,100))
        with patch('rdc.file_images.MAX_SOURCE_PIXELS',9999):
            with self.assertRaises(RDCError) as err:
                self.files.read(str(path))
            self.assertEqual('image_too_large',err.exception.code)

    def test_11_gif_first_frame_explicitly_reported(self):
        path=self.root/'animation.gif'
        with Image.new('RGB',(40,30),'red') as first, Image.new('RGB',(40,30),'blue') as second:
            first.save(path,save_all=True,append_images=[second],duration=100,loop=0)
        result=self.files.read(str(path))
        self.assertTrue(result['first_frame_only'])
        with Image.open(io.BytesIO(base64.b64decode(result['data']))) as decoded:
            self.assertEqual((255,0,0),decoded.convert('RGB').getpixel((0,0)))

    def test_12_workspace_and_private_state_restrictions_apply(self):
        outside=self.base/'outside.png'
        Image.new('RGB',(10,10)).save(outside)
        self.settings.state_dir.mkdir(exist_ok=True)
        private=self.settings.state_dir/'private.png'
        Image.new('RGB',(10,10)).save(private)
        for path in (outside,private):
            with self.assertRaises(RDCError) as err:
                self.files.read(str(path))
            self.assertEqual('path_denied',err.exception.code)

    def test_13_output_is_bounded_and_valid(self):
        import random
        random_source=random.Random(21)
        path=self.root/'noise.png'
        with Image.frombytes('RGB',(900,900),random_source.randbytes(900*900*3)) as img:
            img.save(path)
        self.settings.max_read_bytes=32768
        result=self.files.read(str(path))
        data=base64.b64decode(result['data'],validate=True)
        self.assertLessEqual(len(data),32768)
        self.assertEqual('image/jpeg',result['mime_type'])
        with Image.open(io.BytesIO(data)) as decoded:
            decoded.load()
            self.assertEqual((result['width'],result['height']),decoded.size)

    def test_14_real_mcp_image_content_and_text(self):
        import anyio
        from mcp import Client
        from rdc.engine import Engine
        from rdc.server import create_mcp_server
        path=self.image()
        text=self.root/'ordinary.txt'
        text.write_text('ordinary text')
        engine=Engine(self.settings)
        async def exchange():
            async with Client(create_mcp_server(engine)) as client:
                result=await client.call_tool('rdc_file_read',{'file_path':str(path)})
                images=[part for part in result.content if part.type=='image']
                self.assertEqual(1,len(images))
                self.assertNotIn('data',result.structured_content)
                self.assertEqual('image',result.structured_content['kind'])
                self.assertNotIn(images[0].data,''.join(part.text for part in result.content if part.type=='text'))
                with Image.open(io.BytesIO(base64.b64decode(images[0].data))) as decoded:
                    self.assertEqual((80,60),decoded.size)
                result=await client.call_tool('rdc_file_read',{'file_path':str(text)})
                self.assertEqual('ordinary text',result.structured_content['text'])
                self.assertTrue(all(part.type=='text' for part in result.content))
        try:
            anyio.run(exchange)
        finally:
            engine.close()

    def test_15_jpeg_exif_orientation(self):
        from PIL import Image
        exif=Image.Exif()
        exif[274]=6
        path=self.image('rotate.jpg','JPEG',size=(80,40),exif=exif)
        result=self.files.read(str(path))
        self.assertEqual((80,40),(result['source_width'],result['source_height']))
        self.assertEqual((40,80),(result['width'],result['height']))
        with Image.open(io.BytesIO(base64.b64decode(result['data']))) as image:
            self.assertEqual((40,80),image.size)
            self.assertFalse(image.getexif())

    def test_16_webp_and_tiff_and_bmp(self):
        for fmt in ('WEBP','TIFF','BMP'):
            with self.subTest(format=fmt):
                path=self.image('fixture.'+fmt.lower(),fmt)
                result=self.files.read(str(path),mode='image')
                self.assertEqual(fmt,result['source_format'])
                self.assertEqual((80,60),(result['width'],result['height']))

    def test_17_batch_read_does_not_embed_image_bytes(self):
        from rdc.engine import Engine
        path=self.image()
        text=self.root/'ordinary.txt'
        text.write_text('ordinary')
        engine=Engine(self.settings)
        try:
            result=engine.call('rdc_file_read_many',{'file_paths':[str(path),str(text)]})
            self.assertTrue(result['ok'])
            self.assertFalse(result['results'][0]['ok'])
            self.assertEqual('image_read_required',result['results'][0]['error']['code'])
            self.assertEqual('ordinary',result['results'][1]['text'])
            self.assertNotIn('data',result['results'][0])
        finally:
            engine.close()
