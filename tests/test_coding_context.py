"""Bounded one-request source context for coding agents.

All paths and output are synthetic; no real repositories or cloud calls.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest

from rdc.config import Settings
from rdc.engine import Engine


class CodingContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-code-context-test-")
        self.home = Path(self.temp.name)
        self.root = self.home / "allowed"
        self.root.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.a = self.project / "app.py"
        self.a.write_text("def add(a,b):\n    return a + b\n", encoding="utf-8")
        self.b = self.project / "README.md"
        self.b.write_text("TOC RDC synthetic coding fixture\n", encoding="utf-8")
        self.extra = self.home / "private-external.txt"
        self.extra.write_text("PRIVATE-NO-CODE-CONTEXT", encoding="utf-8")
        self.engine = Engine(Settings(
            state_dir=self.home / "private-worker-state",
            roots=[self.root],
            browser_backend="disabled",
            approval_mode="review",
            allow_exec=False,
        ))

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def context(self, **options):
        return self.engine.call("rdc_code_context", {
            "path": str(self.project), **options
        })

    def test_single_readonly_call_lists_searches_and_reads_with_hashes(self):
        response = self.context(
            query="return a + b",
            file_paths=[str(self.a), str(self.b)],
            list_limit=10,
            search_limit=10,
            max_files=30,
        )
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["path"], str(self.project.resolve()))
        self.assertEqual({x["name"] for x in response["listing"]["entries"]}, {"app.py", "README.md"})
        self.assertFalse(response["listing"]["truncated"])
        self.assertEqual(len(response["search"]["matches"]), 1)
        self.assertEqual(response["search"]["matches"][0]["line"], 2)
        self.assertEqual(len(response["reads"]), 2)
        self.assertTrue(all(x["ok"] for x in response["reads"]))
        self.assertEqual(response["reads"][0]["text"], self.a.read_text())
        self.assertEqual(response["reads"][0]["sha256"],
                         hashlib.sha256(self.a.read_bytes()).hexdigest())
        self.assertFalse(response.get("mutating", False))
        self.assertFalse(any(self.home.rglob("*.approval")))

    def test_outside_read_and_directory_escape_fail_before_partial_output(self):
        wrong = self.context(query="PRIVATE", file_paths=[str(self.extra)])
        self.assertFalse(wrong["ok"])
        self.assertEqual(wrong["error"]["code"], "path_denied")
        self.assertNotIn("PRIVATE-NO-CODE-CONTEXT", str(wrong))
        unrelated = self.root / "unrelated.txt"
        unrelated.write_text("AUTHORISED-BUT-UNRELATED", encoding="utf-8")
        wrong = self.context(file_paths=[str(unrelated)])
        self.assertFalse(wrong["ok"])
        self.assertEqual(wrong["error"]["code"], "path_denied")
        wrong = self.engine.call("rdc_code_context", {
            "path": str(self.extra.parent),
        })
        self.assertFalse(wrong["ok"])
        self.assertEqual(wrong["error"]["code"], "path_denied")

    def test_per_file_error_stays_bounded_and_does_not_block_other_reads(self):
        missing = self.project / "missing.py"
        response = self.context(file_paths=[str(self.a), str(missing)])
        self.assertTrue(response["ok"], response)
        self.assertEqual(len(response["reads"]), 2)
        self.assertTrue(response["reads"][0]["ok"])
        self.assertFalse(response["reads"][1]["ok"])
        self.assertEqual(response["reads"][1]["error"]["code"], "not_found")
        self.assertIsNone(response["search"])
        self.assertEqual(response["listing"]["path"], str(self.project.resolve()))

    def test_schema_limits_and_readonly_admission(self):
        info = next(t for t in self.engine.catalog() if t["name"] == "rdc_code_context")
        self.assertFalse(info.get("x-rdc-mutating", False))
        self.assertFalse(self.engine.call("rdc_code_context", {
            "path": str(self.project), "list_limit": 201,
        })["ok"])
        self.assertFalse(self.engine.call("rdc_code_context", {
            "path": str(self.project), "file_paths": [str(self.a)] * 21,
        })["ok"])
        self.engine.store.set("paused", "true")
        self.assertTrue(self.context(query="return")["ok"],
                        "Owner pause must allow read-only inspection")


if __name__ == "__main__":
    unittest.main()
