"""Bounded, deterministic RDC inline-completion notification responsiveness."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rdc.jobs import Jobs

class FakeStore:
    def __init__(self, complete_after=4):
        self.calls=0
        self.complete_after=complete_after
    def job(self, identifier):
        self.calls+=1
        return {'id':identifier,'status':('completed' if self.calls>=self.complete_after
                                         else 'running')}

class InlineCompletionPollTests(unittest.TestCase):
    def make_jobs(self, complete_after=4):
        instance=Jobs.__new__(Jobs)
        instance.store=FakeStore(complete_after)
        instance.settings=SimpleNamespace(max_read_bytes=16384)
        instance.start=lambda *args,**kwargs: {'job':{'id':'original-claim',
                'status':'running'},'reused':False}
        instance.output=lambda *args,**kwargs: {'text':'exact original output'}
        return instance

    def test_short_job_checks_completed_state_within_four_milliseconds(self):
        jobs=self.make_jobs()
        sleeps=[]
        clock=[0.0]
        def sleep(seconds):
            sleeps.append(seconds)
            clock[0]+=seconds
        with patch('rdc.jobs.time.monotonic',side_effect=lambda:clock[0]), \
             patch('rdc.jobs.time.sleep',side_effect=sleep):
            result=jobs.run(['/bin/echo','readonly'],cwd='/fixture',wait_ms=200)
        self.assertTrue(result['complete'])
        self.assertEqual(result['job']['id'],'original-claim')
        self.assertEqual(result['output']['text'],'exact original output')
        self.assertGreaterEqual(len(sleeps),2)
        self.assertTrue(all(0 < value <= .004 for value in sleeps),sleeps)

    def test_short_wait_timeout_preserves_original_pending_job_without_replay(self):
        jobs=self.make_jobs(complete_after=1000)
        clock=[0.0]
        sleeps=[]
        def sleep(seconds):
            clock[0]+=seconds
            sleeps.append(seconds)
        with patch('rdc.jobs.time.monotonic',side_effect=lambda:clock[0]), \
             patch('rdc.jobs.time.sleep',side_effect=sleep):
            result=jobs.run(['/bin/echo','readonly'],cwd='/fixture',wait_ms=6)
        self.assertFalse(result['complete'])
        self.assertEqual(result['job']['id'],'original-claim')
        self.assertIsNone(result['output'])
        self.assertTrue(all(0 < value <= .004 for value in sleeps),sleeps)
        self.assertLessEqual(sum(sleeps), .006001)
