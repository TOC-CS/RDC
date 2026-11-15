"""Private finite diagnostics, bounded producers, and safe local observation."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from rdc.diagnostics import Diagnostics, safe_record


@unittest.skipUnless(Diagnostics._supported(), 'Secure diagnostic storage requires POSIX descriptor operations')
class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name)
        self.state.chmod(0o700)
        self.recorders = []

    def tearDown(self):
        for recorder in self.recorders:
            recorder.close()
        self.temp.cleanup()

    def recorder(self, **kw):
        value = Diagnostics(self.state, **kw)
        self.recorders.append(value)
        return value

    def wait_written(self, recorder, count=1):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = recorder.snapshot()
            if result['retained_events'] >= count:
                return result
            time.sleep(.01)
        self.fail('writer did not persist expected finite events')

    def test_finite_schema_never_stores_input_or_unknown_text(self):
        recorder = self.recorder()
        secret = 'synthetic-password /private/user/page-content'
        recorder.record('worker', 'operation_failed', 'rdc_file_read')
        recorder.record(secret, secret, secret)
        recorder.record('worker', 'operation_failed', secret)
        report = self.wait_written(recorder, 2)
        self.assertEqual(report['events'][0]['tool'], 'other')
        self.assertEqual(report['events'][1]['tool'], 'files')
        self.assertNotIn(secret, json.dumps(report))
        recorder.close()
        self.assertNotIn(secret.encode(), (self.state / 'diagnostics' / 'events.sqlite3').read_bytes())
        self.assertEqual(report['invalid_events'], 1)
        self.assertEqual(set(report['events'][0]), {'time', 'component', 'event', 'severity', 'tool', 'recovery'})

    def test_queue_burst_and_shutdown_are_bounded(self):
        entered = threading.Event(); release = threading.Event()
        original = Diagnostics._persist
        def blocked(this, records):
            entered.set(); release.wait(3)
            return original(this, records)
        with patch.object(Diagnostics, '_persist', blocked):
            recorder = self.recorder()
            recorder.record('worker', 'operation_failed')
            self.assertTrue(entered.wait(1))
            started = time.monotonic()
            for _ in range(1000): recorder.record('worker', 'operation_failed')
            self.assertLess(time.monotonic() - started, .2)
            self.assertLessEqual(recorder._queue.qsize(), 256)
            self.assertGreater(recorder.snapshot()['dropped_events'], 0)
            started = time.monotonic(); recorder.close()
            self.assertLess(time.monotonic() - started, .5)
            self.assertTrue(recorder.snapshot()['incomplete'])
            release.set()

    def test_retention_and_report_limits(self):
        recorder = self.recorder()
        for _ in range(9):
            for _ in range(256): recorder.record('relay', 'connection_interrupted')
            deadline = time.monotonic() + 3
            while recorder._queue.unfinished_tasks and time.monotonic() < deadline: time.sleep(.01)
        report = recorder.snapshot()
        self.assertEqual(report['retained_events'], 2048)
        self.assertEqual(len(report['events']), 50)
        self.assertEqual(len(recorder.snapshot(1)['events']), 1)
        for value in (0, 51, True, 'secret'):
            with self.assertRaises(ValueError): recorder.snapshot(value)

    def test_writer_failure_and_reporter_failure_are_safe(self):
        with patch.object(Diagnostics, '_persist', side_effect=OSError('synthetic-password /private')):
            recorder = self.recorder()
            recorder.record('worker', 'unexpected_error')
            deadline = time.monotonic() + 1
            while not recorder._failed and time.monotonic() < deadline: time.sleep(.01)
            report = recorder.snapshot()
            self.assertFalse(report['available'])
            self.assertTrue(report['incomplete'])
            self.assertNotIn('synthetic-password', json.dumps(report))
            self.assertGreater(report['dropped_events'], 0)
        class Broken:
            def record(self, *a): raise RuntimeError('secret')
        safe_record(Broken(), 'worker', 'unexpected_error')

    def test_nonregular_and_replaced_symlink_are_refused(self):
        recorder = self.recorder()
        self.wait_written_after_record(recorder)
        path = self.state / 'diagnostics' / 'events.sqlite3'
        victim = self.state / 'private'; victim.write_text('must stay unchanged')
        path.unlink(); path.symlink_to(victim)
        recorder.record('worker', 'operation_failed')
        deadline = time.monotonic() + 1
        while not recorder._failed and time.monotonic() < deadline: time.sleep(.01)
        self.assertFalse(recorder.snapshot()['available'])
        self.assertEqual(victim.read_text(), 'must stay unchanged')
        path.unlink(); os.mkfifo(path, 0o600)
        started = time.monotonic()
        self.assertFalse(Diagnostics.read_status(self.state)['available'])
        self.assertLess(time.monotonic() - started, .2)

    def wait_written_after_record(self, recorder):
        recorder.record('relay', 'connection_interrupted')
        self.wait_written(recorder)

    def test_private_permissions_and_readonly_missing_does_not_create(self):
        report = Diagnostics.read_status(self.state)
        self.assertFalse(report['available'])
        self.assertEqual(list(self.state.iterdir()), [])
        recorder = self.recorder(); self.wait_written_after_record(recorder)
        for path in (self.state / 'diagnostics', self.state / 'diagnostics' / 'events.sqlite3'):
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertTrue(Diagnostics.read_status(self.state)['available'])

    def test_locked_storage_drops_without_blocking_producer(self):
        import fcntl
        recorder = self.recorder(); self.wait_written_after_record(recorder)
        with open(self.state / 'diagnostics' / 'events.lock', 'rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = time.monotonic(); recorder.record('relay', 'connection_interrupted')
            self.assertLess(time.monotonic() - started, .05)
            deadline = time.monotonic() + 1
            while not recorder._failed and time.monotonic() < deadline: time.sleep(.01)
            self.assertTrue(recorder.snapshot()['incomplete'])

    def test_failure_count_survives_next_successful_write_and_closed_record(self):
        recorder = self.recorder()
        with patch.object(recorder, '_persist', side_effect=OSError('secret')):
            recorder.record('worker', 'operation_failed')
            deadline = time.monotonic() + 1
            while not recorder._failed and time.monotonic() < deadline: time.sleep(.01)
        recorder.record('relay', 'reconnected')
        report = self.wait_written(recorder)
        self.assertTrue(report['incomplete'])
        self.assertEqual(report['dropped_events'], 1)
        self.assertEqual(Diagnostics.read_status(self.state)['dropped_events'], 1)
        recorder.close(); recorder.record('worker', 'unexpected_error')
        self.assertGreaterEqual(recorder.snapshot()['dropped_events'], 2)

    def test_untrusted_store_text_and_hardlinks_never_escape(self):
        recorder = self.recorder(); self.wait_written_after_record(recorder); recorder.close()
        path = self.state / 'diagnostics' / 'events.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute("UPDATE events SET event='synthetic-password /private'")
        report = recorder.snapshot()
        self.assertFalse(report['available'])
        self.assertNotIn('synthetic-password', json.dumps(report))
        os.link(path, self.state / 'linked')
        self.assertFalse(Diagnostics.read_status(self.state)['available'])

    def test_preexisting_symlink_directory_and_public_store_are_refused(self):
        victim = self.state / 'victim'; victim.mkdir(mode=0o700)
        (self.state / 'diagnostics').symlink_to(victim, target_is_directory=True)
        recorder = self.recorder(); recorder.record('worker', 'operation_failed'); recorder.close()
        self.assertFalse(recorder.snapshot()['available'])
        self.assertEqual(list(victim.iterdir()), [])
        (self.state / 'diagnostics').unlink()
        (self.state / 'diagnostics').mkdir(mode=0o700)
        path = self.state / 'diagnostics' / 'events.sqlite3'; path.touch(mode=0o644)
        second = self.recorder(); second.record('worker', 'operation_failed'); second.close()
        self.assertFalse(second.snapshot()['available'])
        self.assertEqual(path.read_bytes(), b'')

    def test_independent_process_aggregates_instead_of_replacing_history(self):
        import subprocess
        import sys
        recorder = self.recorder(); self.wait_written_after_record(recorder)
        result = subprocess.run([sys.executable, '-c',
            "from rdc.diagnostics import Diagnostics; import sys; d=Diagnostics(sys.argv[1]); "
            "d.record('relay','reconnected'); d.close()", str(self.state)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        report = recorder.snapshot()
        self.assertEqual(report['retained_events'], 2)
        self.assertEqual(report['totals']['reconnected'], 1)

    def test_recursive_store_schema_cannot_make_snapshot_unbounded(self):
        import subprocess
        import sys
        recorder = self.recorder(); self.wait_written_after_record(recorder); recorder.close()
        path = self.state / 'diagnostics' / 'events.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('ALTER TABLE events RENAME TO saved_events')
            db.execute("CREATE VIEW events AS WITH RECURSIVE x(id) AS (VALUES(1) UNION ALL SELECT id+1 FROM x) "
                       "SELECT id,id AS time,'relay' AS component,'reconnected' AS event,'info' AS severity,"
                       "'other' AS tool,'transport_restored' AS recovery FROM x")
        try:
            result = subprocess.run([sys.executable, '-c',
                "from rdc.diagnostics import Diagnostics; import sys; "
                "assert Diagnostics.read_status(sys.argv[1])['available'] is False", str(self.state)],
                capture_output=True, timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('malformed schema exceeded bounded diagnostic read')
        self.assertEqual(result.returncode, 0)

    def test_brief_reader_contention_does_not_discard_a_pending_event(self):
        import fcntl
        recorder = self.recorder(); self.wait_written_after_record(recorder)
        with open(self.state / 'diagnostics' / 'events.lock', 'rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            recorder.record('relay', 'reconnected')
            time.sleep(.02)
        report = self.wait_written(recorder, 2)
        self.assertEqual(report['totals']['reconnected'], 1)
        self.assertEqual(report['dropped_events'], 0)

    def test_multiple_process_recorders_aggregate(self):
        first = self.recorder(); first.record('relay', 'connection_interrupted'); self.wait_written(first)
        second = self.recorder(); second.record('relay', 'reconnected'); report = self.wait_written(second, 2)
        self.assertEqual(report['totals']['reconnected'], 1)
        self.assertEqual(report['totals']['connection_interrupted'], 1)

class WorkerDiagnosticTests(unittest.TestCase):
    def setUp(self):
        from rdc.config import Settings
        from rdc.engine import Engine
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / 'state'
        self.engine = Engine(Settings(state_dir=self.state, roots=[Path(self.temp.name)], approval_mode='review'))

    def tearDown(self):
        self.engine.close(); self.temp.cleanup()

    @unittest.skipUnless(Diagnostics._supported(), 'Secure diagnostic storage requires POSIX descriptor operations')
    def test_failed_worker_operation_records_only_finite_category(self):
        result = self.engine.call('rdc_file_read', {'file_path': str(Path(self.temp.name) / 'missing-secret')})
        self.assertFalse(result['ok'])
        self.engine.close()
        report = Diagnostics.read_status(self.state)
        self.assertEqual(report['totals']['operation_failed'], 1)
        self.assertNotIn('missing-secret', json.dumps(report))

    def test_reporter_failure_preserves_results_and_unknown_exceptions(self):
        with patch.object(self.engine.diagnostics, 'record', side_effect=RuntimeError('reporter failure')):
            self.assertEqual(self.engine.call('rdc_missing_secret')['error']['code'], 'unknown_tool')
            with patch.object(self.engine, '_invoke', side_effect=RuntimeError('synthetic-password /private')):
                with self.assertRaisesRegex(RuntimeError, 'synthetic-password'):
                    self.engine.call('rdc_system_status')
        self.engine.close()
        self.assertNotIn('synthetic-password', json.dumps(Diagnostics.read_status(self.state)))

    @unittest.skipUnless(Diagnostics._supported(), 'Secure diagnostic storage requires POSIX descriptor operations')
    def test_unknown_exception_recorded_without_message(self):
        with patch.object(self.engine, '_invoke', side_effect=RuntimeError('synthetic-password /private')):
            with self.assertRaises(RuntimeError): self.engine.call('rdc_system_status')
        self.engine.close()
        report = Diagnostics.read_status(self.state)
        self.assertEqual(report['totals']['unexpected_error'], 1)
        self.assertNotIn('synthetic-password', json.dumps(report))

    def test_read_only_tool_with_bounds_stays_available_while_paused(self):
        descriptor = next(item for item in self.engine.catalog() if item['name'] == 'rdc_diagnostics_status')
        self.assertTrue(descriptor['annotations']['readOnlyHint'])
        self.assertFalse(descriptor['x-rdc-mutating'])
        self.engine.pause()
        self.assertTrue(self.engine.call('rdc_diagnostics_status', {'limit': 1})['ok'])
        for args in ({'limit': True}, {'limit': 51}, {'action': 'repair'}, {'text': 'secret'}):
            self.assertEqual(self.engine.call('rdc_diagnostics_status', args)['error']['code'], 'invalid_arguments')
        self.assertEqual(self.engine.store.approvals(), [])

    def test_capture_start_failure_never_reports_live_capture_as_available(self):
        from rdc.config import Settings
        from rdc.engine import Engine
        self.engine.call('rdc_missing')
        self.engine.close()
        with patch('rdc.engine.Diagnostics', side_effect=RuntimeError('synthetic-password')):
            other = Engine(Settings(state_dir=self.state, roots=[Path(self.temp.name)]))
        try:
            report = other.call('rdc_diagnostics_status')
            self.assertTrue(report['ok'])
            self.assertFalse(report['available'])
            self.assertTrue(report['incomplete'])
            self.assertNotIn('synthetic-password', json.dumps(report))
        finally: other.close()

    def test_windows_missing_secure_descriptor_capability_is_reported_without_disrupting_operations(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from rdc.cli import main
        with patch.object(Diagnostics, '_supported', return_value=False):
            result = self.engine.call('rdc_missing')
            self.assertEqual(result['error']['code'], 'unknown_tool')
            self.engine.diagnostics.close()
            report = self.engine.call('rdc_diagnostics_status')
            self.assertTrue(report['ok'])
            self.assertEqual(report['storage_status'], 'unsupported_platform')
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(['diagnostics', '--state-dir', str(self.state)]), 0)
            self.assertFalse(json.loads(output.getvalue())['available'])
            self.assertNotIn('synthetic-password', output.getvalue())

    def test_cli_status_never_loads_config_or_creates_files(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from rdc.cli import main
        output = StringIO()
        selected = Path(self.temp.name) / 'missing-state'
        with redirect_stdout(output):
            self.assertEqual(main(['diagnostics', '--state-dir', str(selected)]), 0)
        self.assertFalse(json.loads(output.getvalue())['available'])
        self.assertFalse(selected.exists())
