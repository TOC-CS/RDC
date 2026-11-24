"""Background preview must remain observational, never authorize resizing."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rdc.config import Settings
from rdc.engine import Engine

class BackgroundPreviewWindowGrantTests(unittest.TestCase):
    def test_background_rejects_resize_grant_before_approval(self):
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(state_dir=Path(d)/"state", roots=[Path(d)], desktop_mode="shared", approval_mode="review")
            engine=Engine(settings)
            try:
                with patch.object(engine, "_invoke", return_value={}) as dispatch:
                    result=engine.call("rdc_window_open", {"target_id":"test-target", "resize_to_view":True})
                    self.assertEqual(result.get("error",{}).get("code"), "background_required", result)
                    dispatch.assert_not_called()
                    self.assertEqual(engine.store.approvals(), [])
            finally: engine.close()

    def test_background_keeps_observational_preview(self):
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(state_dir=Path(d)/"state", roots=[Path(d)], desktop_mode="shared", approval_mode="trusted")
            engine=Engine(settings)
            try:
                with patch.object(engine, "_invoke", return_value={"session_id":"test-view"}) as dispatch:
                    args={"target_id":"test-target", "resize_to_view":False}
                    result=engine.call("rdc_window_open", args)
                    self.assertTrue(result["ok"], result)
                    dispatch.assert_called_once_with("rdc_window_open", args)
            finally: engine.close()

    def test_explicit_foreground_keeps_existing_approval_path(self):
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(state_dir=Path(d)/"state", roots=[Path(d)], desktop_mode="shared", approval_mode="review", background_only=False)
            engine=Engine(settings)
            try:
                with patch.object(engine, "_queue", return_value={"pending":True}) as queue:
                    args={"target_id":"test-target", "resize_to_view":True}
                    result=engine.call("rdc_window_open", args)
                    self.assertEqual(result, {"pending":True})
                    queue.assert_called_once_with("rdc_window_open", args)
            finally: engine.close()
