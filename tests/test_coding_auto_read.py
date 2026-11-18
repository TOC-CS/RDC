"""One-call source discovery and matched file reads, with isolated synthetic fixtures."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from rdc.config import Settings
from rdc.engine import Engine


class AutoReadMatchedSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-autoread-")
        self.base = Path(self.temp.name)
        self.root = self.base / "allowed"
        self.project = self.root / "source"
        self.project.mkdir(parents=True)
        self.state = self.base / "private-state"
        self.alpha = self.project / "alpha.py"
        self.beta = self.project / "beta.py"
        self.alpha.write_text("MATCH_KEY = True\nMATCH_KEY = False\n", encoding="utf-8")
        self.beta.write_text("# MATCH_KEY\n", encoding="utf-8")
        self.engine = Engine(Settings(
            state_dir=self.state, roots=[self.root], allow_exec=False,
            browser_backend="disabled", approval_mode="review",
        ))

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def context(self, **kwargs):
        return self.engine.call("rdc_code_context", {"path":str(self.project), **kwargs})

    def test_reads_first_distinct_matching_files_with_exact_hashes(self):
        output = self.context(query="MATCH_KEY", read_matches=2)
        self.assertTrue(output["ok"], output)
        self.assertEqual(output["auto_read_count"], 2)
        self.assertEqual([x["file_path"] for x in output["reads"]],
                         [str(self.alpha.resolve()), str(self.beta.resolve())])
        self.assertTrue(all(x["ok"] for x in output["reads"]))
        self.assertEqual(output["reads"][0]["sha256"], hashlib.sha256(self.alpha.read_bytes()).hexdigest())
        self.assertEqual(len(output["search"]["matches"]), 3, "repeated matching lines do not cause repeated reads")

    def test_explicit_paths_remain_first_without_duplicate_automatic_reads(self):
        output = self.context(query="MATCH_KEY", file_paths=["beta.py"], read_matches=2)
        self.assertTrue(output["ok"], output)
        self.assertEqual([x["file_path"] for x in output["reads"]],
                         [str(self.beta.resolve()), str(self.alpha.resolve())])
        self.assertEqual(output["auto_read_count"], 1)

    def test_nonzero_auto_reads_require_search_query(self):
        result = self.context(read_matches=1)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["code"], "invalid_arguments")

    def test_auto_read_bounds_and_no_matches(self):
        result = self.context(query="MATCH_KEY", read_matches=6)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["code"], "invalid_arguments")
        result = self.context(query="never_appears", read_matches=3)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["reads"], [])
        self.assertEqual(result["auto_read_count"], 0)
        existing = self.context(query="MATCH_KEY")
        self.assertTrue(existing["ok"])
        self.assertEqual(existing["reads"], [])

    def test_truncated_auto_read_includes_full_file_digest(self):
        large = self.project / "aardvark.py"
        data = b"# MATCH_KEY\n" + b"x" * 70000
        large.write_bytes(data)
        output = self.context(query="MATCH_KEY", read_matches=1)
        self.assertTrue(output["ok"], output)
        record = output["reads"][0]
        self.assertTrue(record["ok"])
        self.assertEqual(record["file_path"], str(large.resolve()))
        self.assertEqual(record["sha256"], hashlib.sha256(data).hexdigest())
        self.assertTrue(record["truncated"])
        self.assertLessEqual(record["next_offset"], 16384)

    def test_symlink_swap_after_search_never_auto_reads_other_project(self):
        self.engine.close()
        self.engine = Engine(Settings(
            state_dir=self.state, roots=[self.root], access_mode="full-host",
            allow_exec=False, browser_backend="disabled", approval_mode="review",
        ))
        external = self.root / "private-other-project.txt"
        external.write_text("SENSITIVE_EXTERNAL_MATCH_KEY", encoding="utf-8")
        alias = self.alpha
        try:
            probe = self.project / "symlink-probe"
            probe.symlink_to(external)
            probe.unlink()
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        real_search = self.engine.files.search

        def swap_after_discovery(*args, **kwargs):
            found = real_search(*args, **kwargs)
            alias.unlink()
            alias.symlink_to(external)
            return found

        with mock.patch.object(self.engine.files, "search", side_effect=swap_after_discovery):
            output = self.context(query="MATCH_KEY", read_matches=2)
        self.assertTrue(output["ok"], output)
        self.assertEqual(output["reads"][0]["ok"], False)
        self.assertEqual(output["reads"][0]["error"]["code"], "path_denied")
        self.assertTrue(output["reads"][1]["ok"])
        self.assertNotIn("SENSITIVE_EXTERNAL_MATCH_KEY", str(output))


if __name__ == "__main__":
    unittest.main()
