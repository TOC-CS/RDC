"""Fast RDC system summaries must preserve jobs/approval semantics."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest

from rdc.engine import Engine
from rdc.jobs import Jobs
from rdc.store import Store


class StatusFastCountsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rdc-status-fast-count-')
        self.store=Store(Path(self.temp.name)/'state')

    def tearDown(self):
        self.temp.cleanup()

    def job(self, number, *, status='completed', old=False):
        now=time.time()
        spec=json.dumps({'argv':['/bin/echo',str(number)],'cwd':self.temp.name,
                         'timeout':5,'max_output_bytes':4096})
        with self.store.connection() as db:
            db.execute('INSERT INTO jobs(id,fingerprint,spec,status,created_at) '
                       'VALUES (?,?,?,?,?)',
                       (f'job-{number}','fixture-'+str(number),spec,status,
                        now-400 if old else now-number))

    def approval(self, number, *, expired=False):
        now=time.time()
        with self.store.connection() as db:
            db.execute('INSERT INTO approvals('
                       'id,name,arguments,digest,status,created_at,expires_at) '
                       'VALUES(?,?,?,?,?,?,?)',
                       (f'appr-{number}','rdc_example',json.dumps({'number':number}),
                        'digest-'+str(number),'pending',now-number,
                        now-2 if expired else now+300))

    def test_summary_avoids_materializing_jobs_and_approval_arguments(self):
        def forbidden():
            raise AssertionError('Summary must not materialize detailed rows')
        engine=Engine.__new__(Engine)
        engine.jobs=SimpleNamespace(count=lambda:4,list=forbidden)
        engine.store=SimpleNamespace(
            approvals_count=lambda:3,approvals=forbidden,
            device_id='fixture-device',get=lambda name:'false')
        engine.settings=SimpleNamespace(public=lambda:{'access_mode':'workspace'})
        engine.adapters=None
        value=Engine.status(engine,summary=True)
        self.assertEqual(value['job_count'],4)
        self.assertEqual(value['pending_approvals'],3)
        self.assertNotIn('jobs',value)
        self.assertNotIn('approvals',value)
        self.assertEqual(value['paused'],False)

    def test_sql_counts_match_original_capped_lists(self):
        for i in range(8):
            self.job(i)
        for i in range(7):
            self.approval(i)
        jobs=Jobs.__new__(Jobs)
        jobs.store=self.store
        self.assertEqual(self.store.job_count(limit=5),len(self.store.jobs(limit=5)))
        self.assertEqual(self.store.approvals_count(limit=5),
                         len(self.store.approvals(limit=5)))
        self.assertEqual(jobs.count(limit=5),5)

    def test_approval_expiration_remains_authoritative(self):
        self.approval(1)
        self.approval(2)
        self.approval(3,expired=True)
        self.assertEqual(self.store.approvals_count(),2)
        self.assertEqual(len(self.store.approvals()),2)
        with self.store.connection() as db:
            row=db.execute('SELECT status FROM approvals WHERE id=?',
                           ('appr-3',)).fetchone()
        self.assertEqual(row['status'],'expired')

    def test_job_reconcile_and_detailed_status_still_work(self):
        self.job(1,status='queued',old=True)
        jobs=Jobs.__new__(Jobs)
        jobs.store=self.store
        self.assertEqual(jobs.count(),1)
        with self.store.connection() as db:
            row=db.execute('SELECT status FROM jobs WHERE id=?',('job-1',)).fetchone()
        self.assertEqual(row['status'],'interrupted')
        engine=Engine.__new__(Engine)
        original_jobs=[{'id':'fixture-original','status':'interrupted'}]
        original_approvals=[{'id':'fixture-approval'}]
        def no_count():
            raise AssertionError('Detailed status must use original lists')
        engine.jobs=SimpleNamespace(count=no_count,list=lambda:{'jobs':original_jobs})
        engine.store=SimpleNamespace(
            approvals_count=no_count,approvals=lambda:original_approvals,
            device_id='fixture-device',get=lambda key:'false')
        engine.settings=SimpleNamespace(public=lambda:{})
        engine.adapters=None
        engine.credentials=SimpleNamespace(owner_snapshot=lambda:{'configured':False})
        detailed=Engine.status(engine,summary=False)
        self.assertEqual(detailed['jobs'],original_jobs)
        self.assertEqual(detailed['approvals'],original_approvals)
        self.assertIn('credentials',detailed)


if __name__=='__main__':
    unittest.main()
