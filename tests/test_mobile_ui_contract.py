"""Source-function UI contracts; no browser or device access."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is required for UI source-function contracts')
class MobileUIContracts(unittest.TestCase):
    def check(self, name):
        script = Path(__file__).parent/'fixtures'/'mobile_ui_contract.mjs'
        result = subprocess.run([shutil.which('node'), str(script), name], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_owner_configured_profile_and_device_notice(self): self.check('owner-profile')
    def test_owner_native_controls_do_not_offer_browser_credentials(self): self.check('owner-controls')
    def test_owner_privacy_refusal_keeps_worker_connected(self): self.check('owner-privacy')
    def test_owner_capture_failure_keeps_worker_connected(self): self.check('owner-capture-failed')
    def test_owner_ended_device_stops_capture_and_keeps_exact_close(self): self.check('owner-ended')
    def test_owner_actions_use_native_logical_coordinates_and_ids(self): self.check('owner-actions')
    def test_owner_unconfigured_cleanup_and_disconnected_states(self): self.check('owner-disabled')
    def test_embedded_mobile_label_notice_and_preserved_selection(self): self.check('embedded-mobile')
    def test_embedded_privacy_refusal_keeps_session_and_jobs(self): self.check('embedded-privacy')
    def test_embedded_capture_failure_hides_stale_image(self): self.check('embedded-capture-failed')
    def test_embedded_uncertain_creation_selection_and_refresh_do_not_capture(self): self.check('embedded-uncertain-creation')
    def test_embedded_ended_device_stops_polling_until_explicit_retry(self): self.check('embedded-ended')
