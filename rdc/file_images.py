"""Bounded, read-only visual file inspection. Never forwards source metadata."""
import base64
import hashlib
import io
import os

from .errors import RDCError

MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_PIXELS = 24_000_000
MAX_OUTPUT_BYTES = 384 * 1024
FORMATS = ('PNG', 'JPEG', 'WEBP', 'GIF', 'BMP', 'TIFF')


def identify_image(header):
    """Identify permitted raster formats by magic bytes, not filename."""
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'PNG'
    if header.startswith(b'\xff\xd8\xff'):
        return 'JPEG'
    if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return 'WEBP'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'GIF'
    if (len(header) >= 14 and header.startswith(b'BM') and header[6:10] == bytes(4)
            and int.from_bytes(header[10:14], 'little') >= 14):
        return 'BMP'
    if header.startswith((b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+')):
        return 'TIFF'
    return None


def _fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _encode(image, output_limit):
    """Prefer lossless inspection; fall back to a bounded JPEG preview."""
    buf = io.BytesIO()
    image.save(buf, format='PNG', compress_level=3)
    if buf.tell() <= output_limit:
        return buf.getvalue(), 'image/png', image.size
    from PIL import Image
    for _ in range(7):
        for quality in (86, 72, 58):
            buf = io.BytesIO()
            image.save(buf, format='JPEG', quality=quality)
            if buf.tell() <= output_limit:
                return buf.getvalue(), 'image/jpeg', image.size
        w,h = image.size
        if max(w,h) <= 320:
            break
        scale = max(320/max(w,h), 0.7)
        image = image.resize((max(1,int(w*scale)),max(1,int(h*scale))),Image.Resampling.LANCZOS)
    raise RDCError('image_preview_too_large', 'Image preview exceeds the configured read limit.')


def read_image(source, path, info, detected, *, max_edge, output_limit):
    if detected not in FORMATS:
        raise RDCError('unsupported_image', 'Supported raster images: PNG, JPEG, WebP, GIF, BMP and TIFF.')
    if info.st_size > MAX_SOURCE_BYTES:
        raise RDCError('image_too_large', 'Image source exceeds the 32 MiB inspection limit.')
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        raise RDCError('image_decoder_unavailable', 'Install the RDC image decoder dependency (Pillow).') from None

    raw = source.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise RDCError('image_too_large', 'Image source exceeds the 32 MiB inspection limit.')
    if len(raw) != info.st_size or _fingerprint(os.fstat(source.fileno())) != _fingerprint(info):
        raise RDCError('conflict', 'Image changed during inspection. Read it again.')
    try:
        with Image.open(io.BytesIO(raw), formats=[detected]) as opened:
            if opened.format != detected:
                raise RDCError('invalid_image', 'Image signature and decoded format disagree.')
            source_size = opened.size
            if (min(source_size) <= 0 or source_size[0] * source_size[1] > MAX_SOURCE_PIXELS):
                raise RDCError('image_too_large', 'Image exceeds the 24 megapixel inspection limit.')
            # Only decode the first frame/page. Never enumerate all animation frames.
            multi_frame = bool(getattr(opened, 'is_animated', False))
            oriented = ImageOps.exif_transpose(opened)
            oriented.thumbnail((max_edge,max_edge), Image.Resampling.LANCZOS)
            # Flatten transparency onto white for a consistent visual preview.
            rgba = oriented.convert('RGBA')
            image = Image.new('RGB', rgba.size, 'white')
            image.paste(rgba, mask=rgba.getchannel('A'))
        data, mime_type, dimensions = _encode(image, min(output_limit, MAX_OUTPUT_BYTES))
    except RDCError:
        raise
    except Image.DecompressionBombError:
        raise RDCError('image_too_large', 'Image exceeds the safe decoding limit.') from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, OverflowError, TypeError):
        raise RDCError('invalid_image', 'Image could not be safely decoded.') from None
    return {
        'file_path': str(path), 'kind': 'image', 'mime_type': mime_type,
        'data': base64.b64encode(data).decode('ascii'),
        'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw),
        'source_format': detected, 'source_width': source_size[0], 'source_height': source_size[1],
        'width': dimensions[0], 'height': dimensions[1], 'preview_bytes': len(data),
        'preview': True, 'first_frame_only': multi_frame, 'metadata_removed': True,
        'transparency_background': 'white',
    }
