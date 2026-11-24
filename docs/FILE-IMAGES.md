# Visual file inspection

The existing `rdc_file_read` tool recognizes supported raster images by their
file signature, regardless of filename extension. Compatible MCP hosts receive
a real image content block and separate structured metadata, rather than
replacement-character text or duplicated base64 text.

## Calls

- `{"file_path":"photo.jpg"}` automatically selects raster inspection.
- `{"file_path":"photo.jpg","mode":"image","max_edge":1600}` explicitly
  requests visual inspection.
- `{"file_path":"notes.txt","offset":0,"limit":4096}` preserves UTF-8 text
  pagination. Use `mode:"text"` to explicitly select the text reader.

Image reads support PNG, JPEG, WebP, GIF, BMP and TIFF. Animated or multi-page
files produce the first frame only. Unsupported formats (including SVG, HEIC
and PDF) are not decoded by this feature.

Image previews use a maximum edge of 320–1600 pixels (default 1280), preserve
aspect ratio and honor EXIF orientation. They flatten transparency onto white
and remove source metadata. The reader prefers lossless PNG, using a bounded
JPEG preview when necessary. Source files are never modified. The response
includes original SHA-256, source size and dimensions, preview dimensions and
MIME type.

The source limit is 32 MiB and 24 megapixels. Encoded preview bytes are capped
at the configured read-byte limit and 384 KiB, whichever is smaller. Larger
or invalid files produce explicit errors. Image reads use the same authorized
workspace and private-state restrictions as text reads. An image that changes
during inspection is rejected.

Read images individually. Text batch reads and project context reads report
an image-specific error instead of embedding image bytes in a text batch.
Image inspection requires Pillow, now included in the worker's core
dependencies. Upgrade the paired worker and refresh the MCP tool catalog before
using the new optional arguments.
