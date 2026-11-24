"""Hybrid command routing reuses exact existing mobile contracts."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from rdc.errors import RDCError
from tests.test_mobile_app_lifecycle import FakeMobile

def profile():
    return {'platformName':'iOS','automationName':'XCUITest','endpoint':'http://127.0.0.1:4723','capabilities':{'appium:udid':'owner-tablet','appium:bundleId':'org.example.first'}}

class CommandEngineTests(unittest.TestCase):
    def setUp(self): self.m=FakeMobile({'first':profile()})
    def tearDown(self): self.m.close()
    def read(self,op,**args): return self.m.call('rdc_mobile_command_read',{'operation':op,'arguments':args})
    def execute(self,op,**args): return self.m.call('rdc_mobile_command_execute',{'operation':op,'arguments':args})
    def test_open_ready_combines_start_and_discovery(self):
        r=self.execute('open_ready',profile='first')
        self.assertTrue(r['ready']);self.assertEqual('device_api',r['command_route']);self.assertTrue(r['controls'])
        self.assertEqual(1,sum(p=='/session' and m=='POST' for m,p,b in self.m.calls))
    def test_read_dispatches_existing_observe(self):
        sid=self.execute('open_ready',profile='first')['session_id']
        r=self.read('observe',session_id=sid);self.assertEqual('structured_ui',r['command_route']);self.assertTrue(r['observation_id'])
    def test_visual_is_explicit_and_never_inferred_from_failure(self):
        sid=self.execute('open_ready',profile='first')['session_id']
        with patch.object(self.m,'_act',side_effect=RDCError('mobile_unavailable','uncertain')) as act:
            with self.assertRaises(RDCError):self.execute('tap',session_id=sid,observation_id='x',handle='c1')
            self.assertEqual(1,act.call_count)
    def test_read_cannot_mutate(self):
        with self.assertRaises(RDCError):self.read('open_ready',profile='first')
        self.assertFalse(self.m.calls)
    def test_reject_unknown_shell_target(self):
        with self.assertRaises(RDCError):self.execute('shell',argv=['whoami'])
        self.assertFalse(self.m.calls)
    def test_reject_nested_unrecognized_arguments(self):
        with self.assertRaises(RDCError):self.execute('open_ready',profile='first',endpoint='http://wrong')
        self.assertFalse(self.m.calls)
    def test_terminal_plan_has_explicit_location(self):
        for mode,route in [('local_terminal','mobile_sandbox'),('worker_terminal','worker_host'),('remote_ssh','remote_host')]:
            r=self.read('terminal_route',mode=mode)
            self.assertEqual(route,r['command_route']);self.assertFalse(r['executed'])
    def test_direct_launch_preserves_owner_review(self):
        r=self.read('terminal_route',mode='direct_device')
        self.assertEqual('device_api',r['command_route']);self.assertTrue(r['owner_review_required']);self.assertFalse(r['executed'])
    def test_no_arbitrary_driver_script(self):
        with self.assertRaises(RDCError):self.execute('execute_script',script='mobile: anything')
        self.assertFalse(self.m.calls)
    def test_close_routes_to_existing_close(self):
        sid=self.execute('open_ready',profile='first')['session_id']
        self.assertTrue(self.execute('close',session_id=sid)['closed'])
        self.assertEqual([],self.m.status()['sessions'])
