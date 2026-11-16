"""Owner setup tests replace only the OS boundary, never the permission policy."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rdc.cli import main


class MacSetupTests(unittest.TestCase):
    def run_setup(self, *arguments, allowed=False):
        with tempfile.TemporaryDirectory() as directory:
            from rdc.config import Settings
            state = Path(directory)
            Settings(state_dir=state, roots=[state], desktop_mode='shared').save(state/'config.json')
            out = io.StringIO()
            with patch('rdc.macos_setup.sys.platform', 'darwin'), \
                 patch('rdc.macos_setup.MacWindowBackend') as backend, contextlib.redirect_stdout(out):
                backend.return_value.return_value = {'ok':True, 'screen_recording':True, 'accessibility':allowed}
                result = main(['setup-macos', '--state-dir', directory, *arguments])
                calls = list(backend.return_value.call_args_list)
            return result, out.getvalue(), calls

    def test_status_has_exact_helper_and_independent_permissions_without_prompt(self):
        code, output, calls = self.run_setup('--json')
        report = json.loads(output)
        self.assertEqual(code, 0)
        self.assertTrue(report['screen_recording'])
        self.assertFalse(report['accessibility'])
        self.assertFalse(report['ready'])
        self.assertTrue(report['helper_path'].endswith('/RDC Window Preview.app'))
        self.assertEqual([c.args[0] for c in calls], ['permissions'])

    def test_explicit_request_does_not_claim_an_async_prompt_granted_access(self):
        code, output, calls = self.run_setup('--request', 'accessibility', '--json')
        report = json.loads(output)
        self.assertEqual(code, 0)
        self.assertFalse(report['ready'])
        self.assertFalse(report['accessibility'])
        self.assertEqual(calls[0].args, ('request_permission',))
        self.assertEqual(calls[0].kwargs, {'permission':'accessibility'})
        self.assertEqual(calls[-1].args, ('permissions',))

    def test_walkthrough_names_missing_helper_and_manual_add(self):
        code, output, _ = self.run_setup()
        self.assertEqual(code, 0)
        self.assertIn('RDC Window Preview', output)
        self.assertIn('Accessibility', output)
        self.assertIn('Add', output)
        self.assertIn('setup-macos', output)

    def test_ready_only_after_permission_readback(self):
        _, output, _ = self.run_setup('--json', allowed=True)
        self.assertTrue(json.loads(output)['ready'])
