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


def _invalid_webp():
    raise RDCError('invalid_image', 'WebP container is incomplete or inconsistent.')


def _webp_chunks(raw, start, end):
    """Walk padded RIFF chunks without copying payloads or decoding pixels."""
    view = memoryview(raw)
    while start < end:
        if end - start < 8:
            _invalid_webp()
        size = int.from_bytes(view[start + 4:start + 8], 'little')
        stop = start + 8 + size
        padded = stop + (size & 1)
        if padded > end or (size & 1 and view[stop] != 0):
            _invalid_webp()
        yield bytes(view[start:start + 4]), view[start + 8:stop]
        # Each iteration consumes at least eight of the bounded source bytes.
        start = padded


def _webp_size(width, height):
    if min(width, height) <= 0:
        _invalid_webp()
    if width * height > MAX_SOURCE_PIXELS:
        raise RDCError('image_too_large', 'Image exceeds the 24 megapixel inspection limit.')
    return width, height


def _webp_bitstream_size(kind, payload):
    if kind == b'VP8 ':
        if len(payload) < 10 or payload[0] & 1 or payload[3:6] != b'\x9d\x01\x2a':
            _invalid_webp()
        return _webp_size(int.from_bytes(payload[6:8], 'little') & 0x3fff,
                          int.from_bytes(payload[8:10], 'little') & 0x3fff)
    if kind == b'VP8L':
        if len(payload) < 5 or payload[0] != 0x2f:
            _invalid_webp()
        bits = int.from_bytes(payload[1:5], 'little')
        if bits >> 29:  # The lossless bitstream version must be zero.
            _invalid_webp()
        return _webp_size((bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1)
    _invalid_webp()


def _webp_canvas(raw):
    """Bound the actual WebP canvas before its native decoder allocates it.

    Container rules: https://developers.google.com/speed/webp/docs/riff_container
    Pixel decoding remains Pillow's job. RIFF lengths, frame bounds and the
    corresponding VP8/VP8L dimensions are checked without allocating a canvas.
    """
    if (len(raw) < 20 or raw[:4] != b'RIFF' or raw[8:12] != b'WEBP'
            or int.from_bytes(raw[4:8], 'little') + 8 != len(raw)):
        _invalid_webp()
    chunks = _webp_chunks(raw, 12, len(raw))
    first, header = next(chunks)
    if first in (b'VP8 ', b'VP8L'):
        canvas = _webp_bitstream_size(first, header)
        if next(chunks, None) is not None:
            _invalid_webp()
        return canvas
    if first != b'VP8X' or len(header) < 10:
        _invalid_webp()
    canvas = _webp_size(int.from_bytes(header[4:7], 'little') + 1,
                        int.from_bytes(header[7:10], 'little') + 1)
    animated = bool(header[0] & 2)
    animation_header = False
    frames = 0
    for kind, payload in chunks:
        if kind == b'VP8X':
            _invalid_webp()
        if kind == b'ANIM':
            # The specification ignores ANIM when the animation flag is off.
            if animated:
                if animation_header or frames or len(payload) < 6:
                    _invalid_webp()
                animation_header = True
        elif kind == b'ANMF':
            if not animated or not animation_header or len(payload) < 16:
                _invalid_webp()
            x = int.from_bytes(payload[0:3], 'little') * 2
            y = int.from_bytes(payload[3:6], 'little') * 2
            frame = _webp_size(int.from_bytes(payload[6:9], 'little') + 1,
                               int.from_bytes(payload[9:12], 'little') + 1)
            if x + frame[0] > canvas[0] or y + frame[1] > canvas[1]:
                _invalid_webp()
            bitstreams = 0
            for subkind, subdata in _webp_chunks(payload, 16, len(payload)):
                if subkind in (b'VP8 ', b'VP8L'):
                    if bitstreams or _webp_bitstream_size(subkind, subdata) != frame:
                        _invalid_webp()
                    bitstreams += 1
            if bitstreams != 1:
                _invalid_webp()
            frames += 1
        elif kind in (b'VP8 ', b'VP8L'):
            if animated or frames or _webp_bitstream_size(kind, payload) != canvas:
                _invalid_webp()
            frames += 1
    if not frames or (animated and not animation_header):
        _invalid_webp()
    return canvas


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


def read_image(source, path, info, detected, *, max_edge, output_limit, guard=None):
    if detected not in FORMATS:
        raise RDCError('unsupported_image', 'Supported raster images: PNG, JPEG, WebP, GIF, BMP and TIFF.')
    if info.st_size > MAX_SOURCE_BYTES:
        raise RDCError('image_too_large', 'Image source exceeds the 32 MiB inspection limit.')
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        raise RDCError('image_decoder_unavailable', 'Install the RDC image decoder dependency (Pillow).') from None

    if guard is not None:
        guard()
    raw = source.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise RDCError('image_too_large', 'Image source exceeds the 32 MiB inspection limit.')
    if len(raw) != info.st_size or _fingerprint(os.fstat(source.fileno())) != _fingerprint(info):
        raise RDCError('conflict', 'Image changed during inspection. Read it again.')
    if guard is not None:
        guard()
    expected_canvas = _webp_canvas(raw) if detected == 'WEBP' else None
    try:
        with Image.open(io.BytesIO(raw), formats=[detected]) as opened:
            if opened.format != detected:
                raise RDCError('invalid_image', 'Image signature and decoded format disagree.')
            source_size = opened.size
            if expected_canvas is not None and source_size != expected_canvas:
                _invalid_webp()
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
    if guard is not None:
        guard()
    return {
        'file_path': str(path), 'kind': 'image', 'mime_type': mime_type,
        'data': base64.b64encode(data).decode('ascii'),
        'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw),
        'source_format': detected, 'source_width': source_size[0], 'source_height': source_size[1],
        'width': dimensions[0], 'height': dimensions[1], 'preview_bytes': len(data),
        'preview': True, 'first_frame_only': multi_frame, 'metadata_removed': True,
        'transparency_background': 'white',
    }
