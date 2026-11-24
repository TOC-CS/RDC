"""The agent cannot take the owner's cursor merely because review is disabled."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rdc.config import Settings
from rdc.engine import Engine


class BackgroundInputTests(unittest.TestCase):
    def test_native_input_needs_one_owner_decision_in_all_configured_modes(self):
        for mode in ('shared', 'isolated'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                engine = Engine(Settings(state_dir=Path(directory)/'state', roots=[Path(directory)],
                                         desktop_mode=mode, approval_mode='trusted', background_only=False))
                try:
                    for name, args in (
                        ('rdc_desktop_pointer', {'x':12, 'y':34, 'action':'move'}),
                        ('rdc_desktop_keys', {'keys':'ENTER'}),
                        ('rdc_desktop_type', {'text':'sample'}),
                    ):
                        with patch.object(engine.adapters, 'call', return_value={'performed':name}) as perform:
                            result = engine.call(name, args)
                            self.assertEqual(result.get('status'), 'pending_approval')
                            perform.assert_not_called()
                            accepted = engine.decide(result['request_id'], True)
                            self.assertTrue(accepted['ok'], accepted)
                            perform.assert_called_once_with(name, args)
                            self.assertFalse(engine.decide(result['request_id'], True)['ok'])
                finally:
                    engine.close()

    def test_denial_and_pause_never_send_native_input(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = Engine(Settings(state_dir=Path(directory)/'state', roots=[Path(directory)],
                                     desktop_mode='shared', approval_mode='trusted', background_only=False))
            try:
                with patch.object(engine.adapters, 'call') as perform:
                    result = engine.call('rdc_desktop_type', {'text':'sample'})
                    self.assertEqual(engine.decide(result['request_id'], False)['status'], 'rejected')
                    engine.pause(True)
                    self.assertEqual(engine.call('rdc_desktop_type', {'text':'sample'})['error']['code'], 'paused')
                    perform.assert_not_called()
            finally:
                engine.close()

    def test_isolated_label_does_not_claim_verified_independent_input(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = Engine(Settings(state_dir=Path(directory)/'state', roots=[Path(directory)],
                                     desktop_mode='isolated', approval_mode='trusted', background_only=False))
            try:
                status = engine.adapters._desktop_status()
                self.assertFalse(status['independent_input'])
                self.assertTrue(status['owner_input_approval_required'])
            finally:
                engine.close()
