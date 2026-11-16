"""Exercise browser-fixture authorization and source-safe artifact routing."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import test_embedded_ui as embedded_ui


class UIFixtureContracts(unittest.TestCase):
    def test_real_worker_bridge_accepts_surface_open_and_refuses_dashboard_and_mutation(self):
        route = getattr(embedded_ui, 'real_worker_tool_result', None)
        self.assertTrue(callable(route), 'The real-worker fixture bridge needs a checked read-only dispatcher')
        from rdc.config import Settings
        from rdc.engine import Engine
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = Engine(Settings(state_dir=root/'state', roots=[root], browser_backend='disabled'))
            try:
                result = route(engine, {'name': 'rdc_preview_open', 'arguments': {}})
                self.assertFalse(result['isError'])
                self.assertTrue(result['structuredContent']['ok'])
                self.assertIsNone(result['structuredContent']['session_id'])
                with self.assertRaises(ValueError):
                    route(engine, {'name': 'rdc_preview_activity', 'arguments': {}})
                with self.assertRaises(ValueError):
                    route(engine, {'name': 'rdc_job_start', 'arguments': {}})
            finally:
                engine.close()

    def test_embedded_fixture_accepts_only_surface_reads(self):
        case = embedded_ui.EmbeddedPreviewTests('test_hide_reopen_and_host_teardown_preserve_worker_session')
        case.errors = []
        for name in ('rdc_preview_open', 'rdc_preview_frame', 'rdc_operation_status'):
            case.page = SimpleNamespace(evaluate=lambda expression, tool=name:
                [{'name': tool}] if expression == 'window.toolCalls' else True)
            case.assert_read_only()
        for name in ('rdc_job_start', 'rdc_browser_click', 'rdc_preview_unknown', 'rdc_preview_activity'):
            case.page = SimpleNamespace(evaluate=lambda expression, tool=name:
                [{'name': tool}] if expression == 'window.toolCalls' else True)
            with self.assertRaises(AssertionError): case.assert_read_only()

    def test_configured_screenshots_are_routed_outside_source(self):
        try:
            from tests.ui_artifacts import artifact_path
        except ImportError:
            self.fail('Source-safe screenshot routing is missing')
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/'nested'/'screenshots'
            with patch.dict('os.environ', {'RDC_TEST_ARTIFACT_DIR': str(destination)}):
                result = artifact_path('fixture.png')
                self.assertEqual(result, (destination/'fixture.png').resolve())
                self.assertTrue(destination.is_dir())
        source = Path(__file__).resolve().parents[1]
        with patch.dict('os.environ', {'RDC_TEST_ARTIFACT_DIR': str(source/'invalid-artifacts')}):
            with self.assertRaises(ValueError): artifact_path('fixture.png')
        self.assertFalse((source/'invalid-artifacts').exists())
