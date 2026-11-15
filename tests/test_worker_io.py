import builtins
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from rdc.store import Store
from rdc.worker import run


class WorkerInputFailures(unittest.TestCase):
    def run_input(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            store = Store(base / 'state')
            (store.directory / 'jobs').mkdir()
            job_id = 'stdin-test'
            text = 'complete-message 🙂\n'
            spec = dict(argv=[sys.executable, '-c',
                              'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'],
                        cwd=str(base), timeout=2, max_output_bytes=1024)
            with store.connection() as db:
                db.execute('INSERT INTO jobs (id,fingerprint,spec,status,created_at) VALUES (?,?,?,?,?)',
                           (job_id, 'test', json.dumps(spec), 'queued', time.time()))
                db.execute('INSERT INTO job_input (job_id,text,close_input) VALUES (?,?,?)',
                           (job_id, text, 1))
            real_popen = subprocess.Popen

            class StdinBoundary:
                def __init__(self, stream):
                    self.stream = stream
                    self.wrote = False

                def write(self, data):
                    if mode == 'stalled':
                        return 0
                    if mode == 'broken' and self.wrote:
                        raise OSError('input pipe failed after partial delivery')
                    self.wrote = True
                    return self.stream.write(data[:2])

                def flush(self):
                    self.stream.flush()

                def close(self):
                    self.stream.close()

            def with_stdin_boundary(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                process.stdin = StdinBoundary(process.stdin)
                return process

            with patch('rdc.worker.subprocess.Popen', side_effect=with_stdin_boundary), \
                 patch('threading.excepthook') as thread_error:
                run(store.directory, job_id)
            thread_error.assert_not_called()
            with store.connection() as db:
                delivered = db.execute('SELECT delivered FROM job_input').fetchone()[0]
            return store.job(job_id), (store.directory / 'jobs' / f'{job_id}.output').read_bytes(), delivered, text.encode()

    def test_partial_stdin_writes_deliver_every_byte_before_acknowledgement(self):
        job, output, delivered, expected = self.run_input('partial')
        self.assertEqual(output, expected)
        self.assertEqual(delivered, 1)
        self.assertEqual(job['status'], 'completed')
        self.assertIsNone(job['error'])

    def test_failed_stdin_delivery_stays_unacknowledged_and_reports_incomplete_input(self):
        for mode in ('stalled', 'broken'):
            with self.subTest(mode=mode):
                job, output, delivered, expected = self.run_input(mode)
                self.assertEqual(delivered, 0)
                self.assertEqual(job['status'], 'failed')
                self.assertEqual(job['exit_code'], 0)
                self.assertIn('Input delivery failed', job['error'])
                self.assertIn('not replayed', job['error'])
                self.assertNotEqual(output, expected)


class WorkerOutputFailures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.store = Store(self.base / 'state')
        (self.store.directory / 'jobs').mkdir()
        self.children = []
        self.child_wait_timeouts = []

    def tearDown(self):
        try:
            for process in self.children:
                try:
                    if process.poll() is None:
                        process.kill()
                finally:
                    try:
                        process.wait(timeout=5)
                    finally:
                        for stream in (process.stdin, process.stdout):
                            if stream is not None:
                                stream.close()
        finally:
            self.temp.cleanup()

    def run_job(self, script, destination=None, max_output_bytes=1024, timeout=2):
        job_id = 'capture-test'
        spec = dict(argv=[sys.executable, '-c', script], cwd=str(self.base),
                    timeout=timeout, max_output_bytes=max_output_bytes)
        with self.store.connection() as db:
            db.execute('INSERT INTO jobs (id,fingerprint,spec,status,created_at) VALUES (?,?,?,?,?)',
                       (job_id, 'test', json.dumps(spec), 'queued', time.time()))
        real_open = builtins.open
        real_popen = subprocess.Popen

        def track_child(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            if args[0] == spec['argv']:
                self.children.append(process)
                real_wait = process.wait

                def wait(timeout=None):
                    self.child_wait_timeouts.append(timeout)
                    return real_wait(timeout=timeout)

                process.wait = wait
            return process

        def output_open(path, *args, **kwargs):
            if str(path).endswith('.output'):
                if destination is None:
                    raise OSError('capture disk full')
                return destination(real_open(path, *args, **kwargs))
            return real_open(path, *args, **kwargs)

        with patch('builtins.open', side_effect=output_open), \
             patch('rdc.worker.subprocess.Popen', side_effect=track_child), \
             patch('threading.excepthook') as thread_error:
            run(self.store.directory, job_id)
        thread_error.assert_not_called()
        return self.store.job(job_id)

    def assert_capture_failed(self, job, message):
        self.assertEqual(job['status'], 'failed', job)
        self.assertEqual(job['exit_code'], 0, job)
        self.assertIn('Output capture failed', job['error'])
        self.assertIn('output is incomplete', job['error'])
        self.assertIn(message, job['error'])

    def test_open_failure_is_durable_even_when_command_succeeds(self):
        self.assert_capture_failed(self.run_job('print("marker")'), 'capture disk full')

    def test_open_failure_keeps_draining_output_larger_than_pipe(self):
        job = self.run_job('import sys; sys.stdout.buffer.write(b"x" * 2000000)')
        self.assert_capture_failed(job, 'capture disk full')
        self.assertEqual(job['bytes_written'], 0)

    def test_file_failure_does_not_stop_child_after_normal_output_eof(self):
        job = self.run_job('import os,time; os.close(1); os.close(2); time.sleep(.4); '
                           'open("finished-side-effect", "w").write("done")')
        self.assert_capture_failed(job, 'capture disk full')
        self.assertEqual((self.base / 'finished-side-effect').read_text(), 'done')

    def test_write_and_close_failures_are_durable(self):
        class BrokenDestination:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

            def write(self, data):
                raise OSError('write failed')

            def close(self):
                self.file.close()
                raise OSError('close failed')

        job = self.run_job('import sys; sys.stdout.buffer.write(b"x" * 2000000)', BrokenDestination)
        self.assert_capture_failed(job, 'write failed')
        self.assertIn('close failed', job['error'])

    def test_close_failure_is_durable_after_successful_write(self):
        class BrokenClose:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

            def write(self, data):
                return self.file.write(data)

            def close(self):
                self.file.close()
                raise OSError('close failed')

        job = self.run_job('import sys; sys.stdout.buffer.write(b"marker\\n")', BrokenClose)
        self.assert_capture_failed(job, 'close failed')
        self.assertEqual(job['bytes_written'], len(b'marker\n'))

    def test_normal_capture_limit_still_drains_and_completes(self):
        job = self.run_job('import sys; sys.stdout.buffer.write(b"x" * 2000000)', lambda file: file)
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['exit_code'], 0)
        self.assertIsNone(job['error'])
        self.assertTrue(job['truncated'])
        self.assertEqual(job['bytes_written'], 1024)
        self.assertEqual((self.store.directory / 'jobs' / 'capture-test.output').read_bytes(), b'x' * 1024)

    def test_partial_file_writes_preserve_output(self):
        class PartialWrites:
            def __init__(self, file):
                self.file = file

            def write(self, data):
                return self.file.write(data[:2])

            def close(self):
                self.file.close()

        job = self.run_job('import sys; sys.stdout.buffer.write(b"marker\\n")', PartialWrites)
        self.assertEqual(job['status'], 'completed')
        self.assertIsNone(job['error'])
        self.assertFalse(job['truncated'])
        self.assertEqual(job['bytes_written'], len(b'marker\n'))
        self.assertEqual((self.store.directory / 'jobs' / 'capture-test.output').read_bytes(), b'marker\n')

    def test_capture_error_survives_command_timeout(self):
        job = self.run_job('import time; time.sleep(10)', timeout=.1)
        self.assertEqual(job['status'], 'timed_out')
        self.assertIn('capture disk full', job['error'])
        self.assertIn('output is incomplete', job['error'])
        self.assert_owned_child_reaped(job)

    def assert_owned_child_reaped(self, job):
        self.assertEqual(len(self.children), 1)
        process = self.children[0]
        # Check before poll()/test cleanup can reap a child the worker abandoned.
        self.assertIsNotNone(process.returncode)
        self.assertEqual(job['exit_code'], process.returncode)
        if os.name != 'nt':
            with self.assertRaises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)

    def test_cleanup_reaps_after_termination_signals_then_raises(self):
        calls = []

        def signal_then_fail(process):
            self.assertIs(process, self.children[0])
            calls.append(process)
            if len(calls) == 1:
                process.terminate()
                raise OSError('termination backend failed after signaling owned child')
            # Both cleanup attempts fail, without a second poll masking a missing wait.
            raise RuntimeError('secondary termination failure')

        with patch('rdc.worker.terminate_tree', side_effect=signal_then_fail):
            job = self.run_job('import time; time.sleep(60)', timeout=.1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.child_wait_timeouts, [10])
        self.assertEqual(job['status'], 'timed_out')
        self.assertIn('termination backend failed after signaling owned child', job['error'])
        self.assertNotIn('secondary termination failure', job['error'])
        self.assertIn('capture disk full', job['error'])
        self.assertIn('output is incomplete', job['error'])
        self.assert_owned_child_reaped(job)
        if os.name != 'nt':
            self.assertEqual(job['exit_code'], -signal.SIGTERM)
        else:
            self.assertNotEqual(job['exit_code'], 0)

    def test_cleanup_wait_is_bounded_when_termination_fails_with_child_alive(self):
        calls = []

        def fail_without_signaling(process):
            self.assertIs(process, self.children[0])
            calls.append(process)
            if len(calls) == 1:
                raise OSError('termination backend unavailable')
            raise RuntimeError('secondary termination failure')

        with patch('rdc.worker.terminate_tree', side_effect=fail_without_signaling):
            # Keep the child live without leaving a reader blocked on its pipes.
            job = self.run_job('import os,time; os.close(1); os.close(2); time.sleep(60)', timeout=.1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.child_wait_timeouts, [10])
        self.assertEqual(job['status'], 'timed_out')
        self.assertIsNone(job['exit_code'])
        self.assertIn('termination backend unavailable', job['error'])
        self.assertNotIn('secondary termination failure', job['error'])
        self.assertIn('Owned child exit could not be confirmed after cleanup.', job['error'])
        self.assertIn('capture disk full', job['error'])
        self.assertIn('output is incomplete', job['error'])
        self.assertEqual(len(self.children), 1)
        self.assertIsNone(self.children[0].poll())
        # An uncertain terminal job must not become runnable again.
        with patch('rdc.worker.subprocess.Popen') as replay:
            run(self.store.directory, job['id'])
        replay.assert_not_called()


if __name__ == '__main__':
    unittest.main()
