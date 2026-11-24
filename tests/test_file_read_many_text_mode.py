"""Focused text-batch compatibility regressions for RDC, by TOC Ministries."""
import base64
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

import anyio
from mcp import Client
from PIL import Image

from rdc.config import Settings
from rdc.engine import Engine
from rdc.server import create_mcp_server


class FileReadManyTextModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "workspace"
        self.root.mkdir()
        self.engine = Engine(Settings(
            self.base / "state", [self.root], allow_exec=False,
            desktop_mode="disabled", browser_backend="disabled",
        ))
        self.addCleanup(self.engine.close)

    def test_read_many_preserves_signature_prefixed_utf8_text(self):
        text = "GIF89a is the signature discussed in this text.\nUTF-8: caf\u00e9.\n"
        raw = text.encode("utf-8")
        path = self.root / "signature-notes.txt"
        path.write_bytes(raw)

        result = self.engine.call("rdc_file_read_many", {"file_paths": [str(path)]})

        self.assertTrue(result["ok"])
        self.assertEqual(1, len(result["results"]))
        row = result["results"][0]
        self.assertTrue(row["ok"], row)
        self.assertEqual(text, row["text"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])
        self.assertEqual(0, row["offset"])
        self.assertEqual(len(raw), row["next_offset"])
        self.assertEqual(len(raw), row["size"])
        self.assertEqual("utf-8", row["encoding"])
        self.assertEqual("bytes", row["offset_unit"])
        self.assertFalse(row["truncated"])
        self.assertNotIn("data", row)

    def test_file_path_only_auto_image_returns_native_image(self):
        path = self.root / "synthetic.png"
        with Image.new("RGB", (16, 12), (31, 67, 109)) as source:
            source.save(path, format="PNG")
            expected_pixels = source.tobytes()

        async def exchange():
            async with Client(create_mcp_server(self.engine)) as client:
                return await client.call_tool(
                    "rdc_file_read", {"file_path": str(path)}
                )

        result = anyio.run(exchange)
        self.assertFalse(result.is_error)
        images = [part for part in result.content if part.type == "image"]
        texts = [part.text for part in result.content if part.type == "text"]
        self.assertEqual(1, len(images))
        self.assertEqual(1, len(texts))
        self.assertEqual("image/png", images[0].mime_type)
        self.assertNotIn("data", result.structured_content)
        self.assertNotIn(images[0].data, texts[0])
        raw = base64.b64decode(images[0].data, validate=True)
        with Image.open(io.BytesIO(raw)) as preview:
            preview.load()
            self.assertEqual((16, 12), preview.size)
            self.assertEqual(expected_pixels, preview.convert("RGB").tobytes())


if __name__ == "__main__":
    unittest.main()
