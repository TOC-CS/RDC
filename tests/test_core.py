import hashlib
import json
import os
from pathlib import Path
import select
import sys
import subprocess
import tempfile
import time
import unittest
import uuid

from rdc.config import Settings
from rdc.engine import Engine


class CoreContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'workspace'
        self.root.mkdir()
        self.settings = Settings(state_dir=self.base / 'state', roots=[self.root],
                                 approval_mode='trusted', allow_exec=True)
        self.engine = Engine(self.settings)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def call(self, name, **args):
        result = self.engine.call(name, args)
        self.assertTrue(result['ok'], result)
        return result

    def wait_job(self, job_id, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.call('rdc_job_status', job_id=job_id)['job']
            if job['status'] not in ('queued', 'running', 'cancelling'):
                return job
            time.sleep(.04)
        self.fail(f'Job {job_id} failed to finish: {job}')

    def test_schema_correct_edit_and_conflict_precondition(self):
        path = str(self.root / 'unicode-α.txt')
        self.call('rdc_file_write', file_path=path, content='first\nsecond\n')
        read = self.call('rdc_file_read', file_path=path)
        self.call('rdc_file_edit', file_path=path, old_text='second', new_text='changed',
                  expected_sha256=read['sha256'])
        conflict = self.engine.call('rdc_file_edit', dict(file_path=path, old_text='first',
                                    new_text='lost', expected_sha256=read['sha256']))
        self.assertFalse(conflict['ok'])
        self.assertEqual(conflict['error']['code'], 'conflict')
        self.assertEqual(Path(path).read_text(), 'first\nchanged\n')
        wrong = self.engine.call('rdc_file_edit', {'path':path, 'old_text':'first', 'new_text':'x'})
        self.assertFalse(wrong['ok'])
        self.assertEqual(wrong['error']['code'], 'invalid_arguments')

    def test_path_escape_symlink_and_private_state_denied(self):
        outside = self.base / 'outside.txt'
        outside.write_text('private')
        result = self.engine.call('rdc_file_read', {'file_path': str(outside)})
        self.assertEqual(result['error']['code'], 'path_denied')
        try:
            (self.root / 'link.txt').symlink_to(outside)
        except OSError:
            self.skipTest('Symlinks require platform permission')
        self.assertFalse(self.engine.call('rdc_file_read', {'file_path':str(self.root/'link.txt')})['ok'])
        full = Engine(Settings(state_dir=self.base/'full-state', roots=[self.base], access_mode='full-host'))
        try:
            self.assertFalse(full.call('rdc_file_read', {'file_path':str(self.base/'full-state'/'rdc.sqlite3')})['ok'])
        finally:
            full.close()

    def test_system_directory_alias_above_granted_root_is_allowed(self):
        # macOS exposes /private/var through /var. Such an ancestor alias must
        # not disable the entire explicitly granted directory beneath it.
        alias = self.base/'system-alias'
        try:
            alias.symlink_to(self.base, target_is_directory=True)
        except OSError:
            self.skipTest('Symlinks require platform permission')
        (self.root/'alias-test.txt').write_text('alias-ok')
        self.assertEqual(self.call('rdc_file_read',file_path=str(alias/'workspace'/'alias-test.txt'))['text'],'alias-ok')
        (self.root/'internal-link').symlink_to(self.root/'alias-test.txt')
        self.assertFalse(self.engine.call('rdc_file_read',{'file_path':str(self.root/'internal-link')})['ok'])

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX FIFO contract')
    def test_fifo_is_rejected_without_blocking_worker(self):
        fifo = self.root/'named-pipe'
        os.mkfifo(fifo)
        script = '''import json,sys
from pathlib import Path
from rdc.config import Settings
from rdc.engine import Engine
engine=Engine(Settings(state_dir=Path(sys.argv[1]),roots=[Path(sys.argv[2])],approval_mode='trusted'))
print('ready',flush=True)
try:
    if sys.stdin.readline().strip() != 'read':
        raise RuntimeError('Missing FIFO read trigger')
    print(json.dumps(engine.call('rdc_file_read',{'file_path':sys.argv[3]})),flush=True)
finally:
    engine.close()
'''
        process = subprocess.Popen([sys.executable,'-c',script,str(self.base/'fifo-state'),str(self.root),str(fifo)],
                                   stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

        def read_line(deadline, timeout_message):
            line = bytearray()
            while len(line) <= 65536:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([process.stdout],[],[],remaining)[0]:
                    self.fail(timeout_message)
                byte = os.read(process.stdout.fileno(),1)
                if not byte:
                    self.fail('FIFO fixture exited before returning a complete readiness or result line')
                if byte == b'\n':
                    return bytes(line)
                line.extend(byte)
            self.fail('FIFO fixture response exceeded its bounded line size')

        try:
            # Import and Engine startup have their own budget. Only the triggered
            # FIFO operation must produce its result within the original two seconds.
            ready = read_line(time.monotonic()+10,'FIFO fixture startup exceeded 10 seconds')
            self.assertEqual(ready,b'ready')
            deadline = time.monotonic()+2
            process.stdin.write(b'read\n')
            process.stdin.flush()
            result = read_line(deadline,'Reading a named pipe blocked instead of returning not_regular_file')
            self.assertEqual(json.loads(result)['error']['code'],'not_regular_file')
            try:
                _, errors = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                self.fail('FIFO fixture did not exit within its 5-second cleanup budget')
            self.assertEqual(process.returncode,0,errors.decode('utf-8',errors='replace'))
        finally:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            finally:
                for stream in (process.stdin,process.stdout,process.stderr):
                    stream.close()

    def test_review_survives_restart_and_revalidates_content(self):
        path = self.root / 'review.txt'
        path.write_text('original')
        settings = Settings(state_dir=self.base/'review-state', roots=[self.root], approval_mode='review')
        first = Engine(settings)
        digest = hashlib.sha256(b'original').hexdigest()
        queued = first.call('rdc_file_edit', {'file_path':str(path), 'old_text':'original',
                            'new_text':'approved', 'expected_sha256':digest})
        self.assertEqual(queued['status'], 'pending_approval')
        first.close()
        path.write_text('changed outside RDC')
        second = Engine(settings)
        try:
            decided = second.decide(queued['request_id'], True)
            self.assertFalse(decided['ok'])
            self.assertEqual(decided['error']['code'], 'conflict')
            self.assertEqual(path.read_text(), 'changed outside RDC')
            self.assertFalse(second.decide(queued['request_id'], True)['ok'])
            self.assertNotIn('rdc_approve', [x['name'] for x in second.catalog()])
        finally:
            second.close()

    def test_job_survives_engine_disconnect_and_retry_deduplicates(self):
        args = {'argv':[sys.executable, '-c', 'import sys,time;time.sleep(.25);sys.stdout.buffer.write(b"durable-marker\\n")'],
                'cwd':str(self.root), 'idempotency_key':'durable-contract'}
        started = self.call('rdc_job_start', **args)
        again = self.call('rdc_job_start', **args)
        self.assertEqual(started['job']['id'], again['job']['id'])
        self.engine.close()
        self.engine = Engine(self.settings)
        job = self.wait_job(started['job']['id'])
        self.assertEqual(job['status'], 'completed')
        chunk = self.call('rdc_job_output', job_id=job['id'], offset=0, limit=5)
        self.assertEqual(chunk['text'], 'durab')
        self.assertEqual(chunk, self.call('rdc_job_output', job_id=job['id'], offset=0, limit=5))
        rest = self.call('rdc_job_output', job_id=job['id'], offset=chunk['next_offset'], limit=100)
        self.assertEqual(rest['text'], 'le-marker\n')
        conflict = self.engine.call('rdc_job_start', {**args,'argv':[sys.executable,'-c','print("other")']})
        self.assertEqual(conflict['error']['code'], 'idempotency_conflict')

    def test_fast_failure_retains_stderr_and_exit_status(self):
        job = self.call('rdc_job_start', argv=[sys.executable,'-c',
                        'import sys;print("precise-error",file=sys.stderr);sys.exit(7)'], cwd=str(self.root))['job']
        end = self.wait_job(job['id'])
        self.assertEqual(end['status'], 'failed')
        self.assertEqual(end['exit_code'], 7)
        self.assertIn('precise-error', self.call('rdc_job_output', job_id=job['id'])['text'])

    def test_job_cancel_timeout_and_bounded_output(self):
        job = self.call('rdc_job_start', argv=[sys.executable,'-c','import time;time.sleep(30)'], cwd=str(self.root))['job']
        self.call('rdc_job_cancel', job_id=job['id'])
        self.assertEqual(self.wait_job(job['id'])['status'], 'cancelled')
        job = self.call('rdc_job_start', argv=[sys.executable,'-c','import time;time.sleep(30)'],
                        cwd=str(self.root), timeout=.2)['job']
        self.assertEqual(self.wait_job(job['id'])['status'], 'timed_out')
        small = Engine(Settings(state_dir=self.base/'small-state', roots=[self.root], approval_mode='trusted',
                                allow_exec=True, max_output_bytes=1024))
        try:
            started = small.call('rdc_job_start', {'argv':[sys.executable,'-c','print("x"*10000)'], 'cwd':str(self.root)})
            deadline = time.monotonic()+10
            while time.monotonic()<deadline:
                result = small.call('rdc_job_status', {'job_id':started['job']['id']})['job']
                if result['status'] in ('completed','failed'): break
                time.sleep(.05)
            self.assertTrue(result['truncated'])
            output = small.call('rdc_job_output', {'job_id':result['id']})
            self.assertEqual(output['next_offset'],1024)
        finally:
            small.close()

    def test_job_stdin_is_delivered_and_search_bounded(self):
        job=self.call('rdc_job_start', argv=[sys.executable,'-u','-c','print(input())'],cwd=str(self.root))['job']
        self.call('rdc_job_input',job_id=job['id'],text='stdin-marker\n',close=True)
        self.assertEqual(self.wait_job(job['id'])['status'],'completed')
        self.assertIn('stdin-marker',self.call('rdc_job_output',job_id=job['id'])['text'])
        (self.root/'match.txt').write_text('needle\nneedle\nneedle\n')
        found=self.call('rdc_file_search',path=str(self.root),query='needle',limit=2)
        self.assertEqual(len(found['matches']),2)
        self.assertTrue(found['truncated'])

    def test_disabled_exec_and_unknown_arguments_fail(self):
        locked=Engine(Settings(state_dir=self.base/'locked-state',roots=[self.root]))
        try:
            result=locked.call('rdc_job_start',{'argv':[sys.executable,'-c','print(1)'],'cwd':str(self.root)})
            self.assertEqual(result['error']['code'],'capability_disabled')
        finally:
            locked.close()
        self.assertFalse(self.engine.call('rdc_system_status', {'unadvertised':True})['ok'])

    def test_pending_stdin_limit_counts_utf8_bytes(self):
        small=Engine(Settings(state_dir=self.base/'input-state',roots=[self.root],max_read_bytes=1024,approval_mode='trusted'))
        identifier=str(uuid.uuid4())
        try:
            with small.store.connection() as db:
                db.execute('INSERT INTO jobs(id,fingerprint,spec,status,created_at) VALUES (?,?,?,?,?)',
                           (identifier,'fixture',json.dumps({'argv':['fixture'],'cwd':str(self.root),'timeout':1}), 'queued',time.time()))
            self.assertTrue(small.call('rdc_job_input',{'job_id':identifier,'text':'🙂'*256})['ok'])
            result=small.call('rdc_job_input',{'job_id':identifier,'text':'x'*768})
            self.assertFalse(result['ok'])
            self.assertEqual(result['error']['code'],'input_too_large')
        finally:
            small.close()


if __name__ == '__main__':
    unittest.main()
