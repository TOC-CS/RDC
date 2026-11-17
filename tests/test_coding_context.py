"""Bounded one-request source context for coding agents.

All paths and output are synthetic; no real repositories or cloud calls.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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
        self.a.write_bytes(b"def add(a,b):\n    return a + b\n")
        self.b = self.project / "README.md"
        self.b.write_bytes(b"TOC RDC synthetic coding fixture\n")
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
        self.assertEqual(self.a.read_bytes(), b"def add(a,b):\n    return a + b\n")
        self.assertEqual(self.b.read_bytes(), b"TOC RDC synthetic coding fixture\n")
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

    def test_symlink_swap_after_admission_cannot_escape_selected_project(self):
        # Live full-host access permits symlinks; the new tool must still
        # confine each requested file to its explicitly selected project.
        self.engine.close()
        self.engine = Engine(Settings(
            state_dir=self.home / "private-worker-state",
            roots=[self.root],
            access_mode="full-host",
            browser_backend="disabled",
            approval_mode="review",
            allow_exec=False,
        ))
        # An in-project alias changes before the actual read phase.
        other_project = self.root / "other-project"
        other_project.mkdir()
        private = other_project / "secret.txt"
        private.write_text("SYNTHETIC-OTHER-PROJECT-PRIVATE", encoding="utf-8")
        alias = self.project / "alias.txt"
        try:
            alias.symlink_to(self.a)
        except (OSError, NotImplementedError):
            self.skipTest("File symlinks require platform permission")
        original_list = self.engine.files.list

        def swap_after_validation(*args, **kwargs):
            result = original_list(*args, **kwargs)
            alias.unlink()
            alias.symlink_to(private)
            return result

        with mock.patch.object(self.engine.files, "list", side_effect=swap_after_validation):
            response = self.context(file_paths=[str(alias)])
        self.assertTrue(response["ok"], response)
        self.assertEqual(len(response["reads"]), 1)
        self.assertFalse(response["reads"][0]["ok"], response)
        self.assertEqual(response["reads"][0]["error"]["code"], "path_denied")
        self.assertNotIn("SYNTHETIC-OTHER-PROJECT-PRIVATE", str(response))

    def test_search_stays_in_project_if_subdirectory_becomes_symlink(self):
        # A directory can be replaced after os.walk enumerates its filenames.
        # A full-host worker must still not return content from the new target.
        self.engine.close()
        self.engine = Engine(Settings(
            state_dir=self.home / "private-worker-state",
            roots=[self.root], access_mode="full-host",
            browser_backend="disabled", approval_mode="review", allow_exec=False,
        ))
        nested = self.project / "nested"
        nested.mkdir()
        (nested / "SOURCE.txt").write_text("original project content", encoding="utf-8")
        other = self.root / "other-project"
        other.mkdir()
        (other / "SOURCE.txt").write_text("SYNTHETIC-EXTERNAL-SCOPE-MATCH", encoding="utf-8")
        probe = self.project / "symlink-capability-probe"
        try:
            probe.symlink_to(other, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks require platform permission")
        else:
            probe.unlink()
        original_walk = os.walk

        def swap_after_scan(path, *args, **kwargs):
            for parent, directories, names in original_walk(path, *args, **kwargs):
                if Path(parent).resolve() == nested.resolve():
                    nested.rename(self.project / "nested-original")
                    nested.symlink_to(other, target_is_directory=True)
                yield parent, directories, names

        with mock.patch("rdc.files.os.walk", side_effect=swap_after_scan):
            response = self.context(query="SYNTHETIC-EXTERNAL-SCOPE-MATCH")
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["search"]["matches"], [])
        self.assertNotIn("SYNTHETIC-EXTERNAL-SCOPE-MATCH", str(response))

    def test_relative_reads_are_project_scoped_and_ordered(self):
        result = self.context(file_paths=["app.py", "./README.md"])
        self.assertTrue(result["ok"], result)
        self.assertEqual([r["file_path"] for r in result["reads"]],
                         [str(self.a.resolve()), str(self.b.resolve())])
        self.assertEqual([r["text"] for r in result["reads"]],
                         [self.a.read_text(), self.b.read_text()])
        self.assertTrue(all(item["ok"] for item in result["reads"]))
        outside = self.root / "SIBLING.txt"
        outside.write_text("SIBLING_SHOULD_STAY_PRIVATE", encoding="utf-8")
        denied = self.context(file_paths=["../SIBLING.txt"])
        self.assertFalse(denied["ok"], denied)
        self.assertEqual(denied["error"]["code"], "path_denied")
        self.assertNotIn("SIBLING_SHOULD_STAY_PRIVATE", str(denied))

    def test_source_search_skips_generated_trees_and_all_mode_restores_them(self):
        marker = "RDC-SEARCH-SOURCE-STRING"
        source = self.project / "module.py"
        source.write_text("# " + marker + "\\n", encoding="utf-8")
        excluded = (".git", "node_modules", ".venv", "__pycache__",
                    ".next", "dist", "build", "target")
        for directory in excluded:
            path = self.project / directory / "vendor-file.py"
            path.parent.mkdir(parents=True)
            path.write_text("# " + marker + "\\n", encoding="utf-8")
        fast = self.context(query=marker)
        self.assertTrue(fast["ok"], fast)
        self.assertEqual(len(fast["search"]["matches"]), 1)
        self.assertEqual(fast["search"]["matches"][0]["file_path"], str(source.resolve()))
        self.assertEqual(fast["search"]["files_scanned"], 3)
        complete = self.context(query=marker, search_mode="all")
        self.assertTrue(complete["ok"], complete)
        self.assertEqual(len(complete["search"]["matches"]), 1 + len(excluded))
        self.assertGreater(complete["search"]["files_scanned"], fast["search"]["files_scanned"])
        # Generic file_search still covers all paths by default.
        ordinary = self.engine.call("rdc_file_search", {
            "path": str(self.project), "query": marker})
        self.assertEqual(len(ordinary["matches"]), 1 + len(excluded))

    def test_source_search_requires_no_executable_command_permission(self):
        with mock.patch("subprocess.run", side_effect=AssertionError("external process forbidden")):
            result = self.context(query="return a + b", file_paths=["app.py"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["reads"][0]["text"], self.a.read_text())

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
