"""Production preview source with the real pinned SDK and synthetic host wire."""
from pathlib import Path
import shutil
import subprocess
import unittest


SDK = Path(__file__).resolve().parents[1]/'rdc'/'embedded'/'node_modules'/'@modelcontextprotocol'/'ext-apps'/'dist'/'src'/'app.js'


@unittest.skipUnless(shutil.which('node') and SDK.is_file(),
    'Node and pinned SDK required; run npm ci --ignore-scripts in rdc/embedded')
class PreviewConsistencyContracts(unittest.TestCase):
    def check(self, name):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).parent/'fixtures'/'preview_consistency_contract.mjs'), name],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_host_confirmed_picture_in_picture_and_job_end_request_teardown(self): self.check('job-floating-supported')
    def test_host_without_floating_mode_hides_only_and_never_opens_external_window(self): self.check('job-floating-unsupported')
    def test_late_completion_result_cannot_reopen_but_new_job_can_rebind(self): self.check('job-next-task')
    def test_explicit_job_bound_floating_preview_running_keeps_work_visible(self): self.check('job-running')
    def test_verified_job_completion_clears_floating_view_without_stopping_worker(self): self.check('job-terminal')
    def test_other_completed_job_cannot_close_selected_floating_task(self): self.check('job-mismatch')
    def test_unknown_interruption_preserves_floating_view_for_inspection(self): self.check('job-unknown')

    def test_thirty_mounts_and_repeated_opens_keep_one_transport(self): self.check('repeated')
    def test_failed_initial_handshake_explicit_retry_preserves_selection(self): self.check('retry')
    def test_delayed_handshake_guards_concurrent_connect(self): self.check('delayed')
    def test_handshake_timeout_then_late_old_reply_does_not_complete_retry(self): self.check('timeout')
    def test_hide_resume_drops_late_frame_without_open_or_mutation(self): self.check('hide')
    def test_dispose_and_new_mount_ignore_old_frame_and_notification(self): self.check('dispose')
    def test_pending_open_keeps_original_id_across_hide_resume(self): self.check('pending')
    def test_late_host_context_after_dispose_cannot_reopen_view(self): self.check('late-context')
    def test_offline_bootstrap_keeps_last_known_state_and_retries_once_when_online(self): self.check('offline')
    def test_offline_notification_while_hidden_allows_retry_after_returning(self): self.check('offline-hidden')
    def test_busy_bootstrap_does_not_invent_sessions_or_start_polling(self): self.check('busy')
    def test_new_availability_fences_older_open_success_error_and_fallback(self): self.check('stale-open')
    def test_new_availability_keeps_inflight_original_pending_reference(self): self.check('stale-pending')
    def test_expired_open_recovers_structured_wrapped_and_safe_terminal_results(self): self.check('expired-open')
    def test_opaque_or_unmatched_expiry_retains_original_operation_on_manual_retry(self): self.check('expired-unknown')
    def test_repeated_expiry_bounds_automatic_refresh_and_allows_explicit_retry(self): self.check('expired-bounded')
    def test_expired_frame_refreshes_the_same_read_only_view(self): self.check('expired-frame')
    def test_hidden_view_defers_expiry_recovery_without_losing_original_identity(self): self.check('expired-hidden')
    def test_expired_host_bootstrap_requests_one_fresh_open(self): self.check('expired-bootstrap')
    def test_hidden_fresh_read_keeps_its_new_pending_identity(self): self.check('expired-fresh-hidden')
    def test_wrong_tool_or_operation_in_refresh_hint_cannot_replace_original(self): self.check('expired-wrong-hint')
    def test_host_wrapped_ended_session_never_selects_a_different_source(self): self.check('ended-wrapped')
    def test_retired_frame_identity_allows_a_scoped_fresh_observation(self): self.check('missing-observation')
    def test_unverified_missing_identity_errors_preserve_the_original_read(self): self.check('missing-unverified')

    def test_legacy_global_target_and_expired_unbound_read_never_choose_a_source(self): self.check('unbound')
    def test_result_for_another_source_cannot_replace_the_bound_view(self): self.check('other-source')
