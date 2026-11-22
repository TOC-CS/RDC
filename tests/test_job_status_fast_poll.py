"""Short terminal polling reads only status until the final durable snapshot."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rdc.errors import RDCError
from rdc.jobs import Jobs
from rdc.store import Store

class FastStatusTests(unittest.TestCase):
    def test_store_lightweight_job_state_requires_existing_job(self):
        with tempfile.TemporaryDirectory(prefix='rdc-fast-state-') as directory:
            store=Store(Path(directory)/'state')
            with store.connection() as db:
                db.execute('INSERT INTO jobs(id,fingerprint,spec,status,created_at) VALUES(?,?,?,?,?)',
                    ('original','f',json.dumps({'argv':['echo'], 'cwd':directory, 'timeout':3}), 'queued',1))
            self.assertEqual(store.job_state('original'),'queued')
            with store.connection() as db:
                db.execute("UPDATE jobs SET status='completed' WHERE id='original'")
            self.assertEqual(store.job_state('original'),'completed')
            with self.assertRaises(RDCError):store.job_state('absent')

    def test_inline_result_uses_one_full_record_after_multiple_light_checks(self):
        class FakeStore:
            light=0
            full=0
            def job_state(self, identifier):
                self.light+=1
                return 'completed' if self.light>=4 else 'running'
            def job(self, identifier):
                self.full+=1
                return {'id':identifier,'status':'completed','exit_code':0}
        store=FakeStore(); worker=Jobs.__new__(Jobs)
        worker.store=store; worker.settings=SimpleNamespace(max_read_bytes=8192)
        worker.start=lambda *args,**kwargs:{'job':{'id':'original','status':'running'},'reused':False}
        worker.output=lambda *args,**kwargs:{'text':'original-output'}
        clock=[0.0]
        with patch('rdc.jobs.time.monotonic',side_effect=lambda:clock[0]), \
             patch('rdc.jobs.time.sleep',side_effect=lambda t:clock.__setitem__(0,clock[0]+t)):
            result=worker.run(['echo'],'/fixture',wait_ms=100)
        self.assertTrue(result['complete']); self.assertEqual(result['output']['text'],'original-output')
        self.assertEqual(store.full,1); self.assertEqual(store.light,4)

    def test_timeout_uses_one_full_record_without_replaying_original_action(self):
        class PendingStore:
            light=0
            full=0
            def job_state(self,identifier):
                self.light+=1; return 'running'
            def job(self,identifier):
                self.full+=1; return {'id':identifier,'status':'running'}
        store=PendingStore(); worker=Jobs.__new__(Jobs)
        worker.store=store;worker.settings=SimpleNamespace(max_read_bytes=8192)
        launches=[]
        worker.start=lambda *args,**kwargs:(launches.append(1) or {'job':{'id':'original','status':'running'},'reused':False})
        worker.output=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('no premature output'))
        clock=[0.0]
        with patch('rdc.jobs.time.monotonic',side_effect=lambda:clock[0]), \
             patch('rdc.jobs.time.sleep',side_effect=lambda t:clock.__setitem__(0,clock[0]+t)):
            result=worker.run(['echo'],'/fixture',wait_ms=10)
        self.assertFalse(result['complete']);self.assertEqual(result['job']['id'],'original')
        self.assertEqual(len(launches),1);self.assertEqual(store.full,1)

if __name__=='__main__':unittest.main()
