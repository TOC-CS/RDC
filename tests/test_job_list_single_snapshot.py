"""Original RDC durable job listing with one database snapshot."""
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import time
import unittest

from rdc.errors import RDCError
from rdc.store import Store


class JobListSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rdc-jobs-one-snapshot-')
        self.store=Store(Path(self.temp.name)/'state')
        self.now=time.time()
        self.device_id=self.store.device_id

    def tearDown(self):
        self.temp.cleanup()

    def insert(self,i,*,truncated=False,status='completed',timestamp=None):
        payload={'argv':['/bin/echo','private-fixture-'+str(i)],
                 'cwd':self.temp.name,'timeout':5,'max_output_bytes':4096}
        with self.store.connection() as db:
            db.execute('INSERT INTO jobs(id,fingerprint,client_key,spec,status,created_at,'
                       'bytes_written,truncated) VALUES (?,?,?,?,?,?,?,?)',
                       ('original-job-'+str(i),'fingerprint-'+str(i),
                        'key-'+str(i),json.dumps(payload),
                        status,self.now-i if timestamp is None else timestamp,
                        i+5, int(truncated)))

    def test_one_database_connection_for_entire_list(self):
        for i in range(11):
            self.insert(i)
        with patch.object(self.store,'connection',wraps=self.store.connection) as open_db:
            listed=self.store.jobs(limit=7)
        self.assertEqual(len(listed),7)
        self.assertLessEqual(open_db.call_count,1,
            'N+1 database opens on job listing remains the latency bottleneck')

    def test_original_list_order_and_field_shapes_preserved(self):
        for i in range(8):
            self.insert(i,truncated=bool(i%2))
        expected=[self.store.job('original-job-'+str(i)) for i in range(8)]
        current=self.store.jobs(limit=8)
        self.assertEqual(current,expected)
        self.assertEqual([v['id'] for v in current],
                         ['original-job-'+str(i) for i in range(8)])
        self.assertTrue(all(v['device_id']==self.device_id for v in current))
        self.assertTrue(all(type(v['truncated']) is bool for v in current))
        self.assertTrue(all('spec' not in v and 'fingerprint' not in v for v in current))
        self.assertEqual(self.store.jobs(limit=0),[])

    def test_existing_single_job_recovery_and_missing_identity(self):
        self.insert(1,status='running',truncated=True)
        response=self.store.job('original-job-1')
        self.assertEqual(response['status'],'running')
        self.assertTrue(response['truncated'])
        self.assertEqual(response['argv'],['/bin/echo','private-fixture-1'])
        self.assertEqual(self.store.jobs(limit=1),[response])
        with self.assertRaises(RDCError) as ctx:
            self.store.job('wrong-or-expired-original-identity')
        self.assertEqual(ctx.exception.code,'job_not_found')

    def test_queued_running_and_completed_are_detailed_without_mutating_work(self):
        for i,kind in enumerate(('queued','running','completed')):
            self.insert(i,status=kind)
        listed=self.store.jobs(limit=3)
        self.assertEqual([v['status'] for v in listed],
                         ['queued','running','completed'])
        with self.store.connection() as db:
            originals=db.execute('SELECT id,status,bytes_written,truncated FROM jobs '
                                 'ORDER BY created_at DESC').fetchall()
        self.assertEqual([row['status'] for row in originals],
                         ['queued','running','completed'])
        self.assertTrue(all(v['bytes_written']==i+5 for i,v in enumerate(listed)))


if __name__=='__main__':
    unittest.main()
