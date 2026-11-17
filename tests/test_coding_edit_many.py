"""Project-scoped multi-file coding edits with strict per-file SHA preconditions."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from rdc.config import Settings
from rdc.engine import Engine


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CodeEditManyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rdc-code-edits-")
        self.home = Path(self.temporary.name)
        self.root = self.home / "allowed"
        self.project = self.root / "project"
        self.project.mkdir(parents=True)
        self.first = self.project / "first.py"
        self.second = self.project / "second.py"
        self.first.write_text("return a - b\n", encoding="utf-8")
        self.second.write_text("return x - y\n", encoding="utf-8")
        self.engine = Engine(Settings(state_dir=self.home / "private-state",
                                      roots=[self.root], approval_mode="trusted",
                                      browser_backend="disabled", allow_exec=False))

    def tearDown(self):
        self.engine.close()
        self.temporary.cleanup()

    def edit(self, edits):
        return self.engine.call("rdc_code_edit_many", {
            "path": str(self.project), "edits": edits})

    @staticmethod
    def entry(path, original, replacement, expected_hash=None):
        return {"file_path": path, "old_text": original, "new_text": replacement,
                "expected_sha256": expected_hash or sha(original), "expected_count": 1}

    def test_two_surgical_edits_in_one_durable_operation(self):
        first = self.entry("first.py", "return a - b", "return a + b",
                           sha("return a - b\n"))
        second = self.entry("second.py", "return x - y", "return x + y",
                            sha("return x - y\n"))
        result = self.edit([first, second])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["applied"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(x["ok"] for x in result["results"]))
        self.assertEqual(self.first.read_text(), "return a + b\n")
        self.assertEqual(self.second.read_text(), "return x + y\n")
        self.assertEqual(result["results"][0]["sha256"], sha("return a + b\n"))
        catalog = next(t for t in self.engine.catalog() if t["name"] == "rdc_code_edit_many")
        self.assertEqual(catalog["inputSchema"]["properties"]["edits"]["maxItems"], 10)
        self.assertTrue(catalog["x-rdc-mutating"])

    def test_stale_file_reports_explicit_partial_results_without_replay(self):
        first = self.entry("first.py", "return a - b", "return a + b",
                           "0" * 64)
        second = self.entry("second.py", "return x - y", "return x + y",
                            sha("return x - y\n"))
        result = self.edit([first, second])
        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"])
        self.assertEqual((result["applied"], result["failed"]), (1, 1))
        self.assertEqual(result["results"][0]["error"]["code"], "conflict")
        self.assertEqual(result["results"][1]["ok"], True)
        self.assertEqual(self.first.read_text(), "return a - b\n")
        self.assertEqual(self.second.read_text(), "return x + y\n")

    def test_outside_project_path_and_duplicate_alias_rejected_before_any_edit(self):
        sibling = self.root / "sibling.py"
        sibling.write_text("return external\n", encoding="utf-8")
        first = self.entry("first.py", "return a - b", "return a + b",
                           sha("return a - b\n"))
        crossing = self.entry("../sibling.py", "return external", "changed",
                              sha("return external\n"))
        denied = self.edit([first, crossing])
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"]["code"], "path_denied")
        self.assertEqual(self.first.read_text(), "return a - b\n")
        self.assertEqual(sibling.read_text(), "return external\n")
        duplicate = self.entry("./first.py", "return a - b", "return a * b",
                               sha("return a - b\n"))
        rejected = self.edit([first, duplicate])
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["error"]["code"], "invalid_arguments")
        self.assertEqual(self.first.read_text(), "return a - b\n")

    def test_owner_review_mode_queues_batch_without_writing(self):
        self.engine.close()
        self.engine = Engine(Settings(state_dir=self.home / "private-review",
                                      roots=[self.root], approval_mode="review",
                                      browser_backend="disabled", allow_exec=False))
        first = self.entry("first.py", "return a - b", "return a + b",
                           sha("return a - b\n"))
        queued = self.edit([first])
        self.assertTrue(queued["ok"], queued)
        self.assertEqual(queued["status"], "pending_approval")
        self.assertEqual(self.first.read_text(), "return a - b\n")

    def test_full_host_symlink_swap_after_admission_remains_in_project(self):
        from unittest import mock
        self.engine.close()
        self.engine = Engine(Settings(state_dir=self.home / "private-full-host",
                                      roots=[self.root], access_mode="full-host",
                                      approval_mode="trusted", browser_backend="disabled",
                                      allow_exec=False))
        outside = self.root / "other-project-source.py"
        outside.write_text("return private-data\n", encoding="utf-8")
        alias = self.project / "alias.py"
        try:
            alias.symlink_to(self.first)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this platform")
        original_validate = self.engine._validate

        def swap_after_admission(name, args):
            original_validate(name, args)
            if name == "rdc_code_edit_many":
                alias.unlink()
                alias.symlink_to(outside)

        with mock.patch.object(self.engine, "_validate", side_effect=swap_after_admission):
            result = self.edit([self.entry("alias.py", "return a - b",
                                           "return a + b", sha("return a - b\n"))])
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["results"][0]["error"]["code"], "path_denied")
        self.assertEqual(self.first.read_text(), "return a - b\n")
        self.assertEqual(outside.read_text(), "return private-data\n")

    def test_final_file_becomes_symlink_at_edit_entry_and_cannot_escape_project(self):
        from unittest import mock
        self.engine.close()
        self.engine = Engine(Settings(state_dir=self.home / "private-swap-entry",
                                      roots=[self.root], access_mode="full-host",
                                      approval_mode="trusted", browser_backend="disabled",
                                      allow_exec=False))
        outside = self.root / "same-content-outside-project.py"
        outside.write_text("return a - b\n", encoding="utf-8")
        original_edit = self.engine.files.edit
        swapped = [False]

        def swap_at_edit_entry(**arguments):
            if not swapped[0]:
                swapped[0] = True
                self.first.rename(self.project / "first-original.py")
                self.first.symlink_to(outside)
            return original_edit(**arguments)

        with mock.patch.object(self.engine.files, "edit", side_effect=swap_at_edit_entry):
            result = self.edit([self.entry("first.py", "return a - b",
                                           "return a + b", sha("return a - b\n"))])
        self.assertTrue(swapped[0])
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["results"][0]["error"]["code"], "path_denied")
        self.assertEqual(outside.read_text(), "return a - b\n")

    def test_schema_rejects_oversized_batch(self):
        item = self.entry("first.py", "return a - b", "return a + b", sha("return a - b\n"))
        response = self.edit([item] * 11)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_arguments")
        self.assertEqual(self.first.read_text(), "return a - b\n")


if __name__ == "__main__":
    unittest.main()
