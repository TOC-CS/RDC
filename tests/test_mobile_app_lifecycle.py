"""Bounded source qualification for owner-profile iOS application lifecycle."""
import copy
import json
import unittest
from types import SimpleNamespace
from rdc.errors import RDCError
from rdc.mobile import Mobile
from tests.test_mobile import IOS_XML

class FakeMobile(Mobile):
    def __init__(self, profiles):
        self.calls=[]; self.foreground=('org.example.first',11)
        self.apps={'org.example.first':4,'org.example.second':1}; self.fail_launch=False
        self.fail_terminate=False; self.invalid_state=False; self.false_terminate=False
        super().__init__(SimpleNamespace(mobile_profiles=profiles))
    def _http(self,profile,method,path,body=None,timeout=35):
        self.calls.append((method,path,copy.deepcopy(body)))
        if path=='/session': return {'sessionId':'private-driver','capabilities':body['capabilities']['alwaysMatch']}
        if path.endswith('/context'): return 'NATIVE_APP'
        if path.endswith('/window/rect'): return {'x':0,'y':0,'width':400,'height':800}
        if path.endswith('/source'): return IOS_XML
        if path.endswith('/execute/sync'):
            script=body['script']; args=body['args']
            if script=='mobile: activeAppInfo':return {'bundleId':self.foreground[0],'pid':self.foreground[1]}
            target=args[0]['bundleId']
            if script=='mobile: queryAppState':return 99 if self.invalid_state else self.apps[target]
            if script=='mobile: launchApp':
                if self.foreground[0] in self.apps:self.apps[self.foreground[0]]=3
                self.apps[target]=4;self.foreground=(target,22)
                if self.fail_launch:raise RDCError('mobile_unavailable','private failure')
                return None
            if script=='mobile: terminateApp':
                if self.false_terminate:return False
                self.apps[target]=1
                if self.foreground[0]==target:self.foreground=('com.apple.springboard',33)
                if self.fail_terminate:raise RDCError('mobile_unavailable','private failure')
                return True
            raise AssertionError('unexpected driver command')
        return None

class AppLifecycleTests(unittest.TestCase):
    def setUp(self):
        def profile(bundle,udid='owner-tablet',port=4723):
            return {'platformName':'iOS','automationName':'XCUITest','endpoint':f'http://127.0.0.1:{port}', 'capabilities':{'appium:udid':udid,'appium:bundleId':bundle,'appium:noReset':True}}
        self.mobile=FakeMobile({'first':profile('org.example.first'),'second':profile('org.example.second'),'wrong_device':profile('org.example.other','another-tablet'),'wrong_endpoint':profile('org.example.other',port=4724)})
        self.sid=self.mobile.call('rdc_mobile_start',{'profile':'first'})['session_id']
    def tearDown(self):self.mobile.close()
    def state(self,profile='second'):return self.mobile.call('rdc_mobile_app_state',{'session_id':self.sid,'profile':profile})
    def act(self,action,observation,profile='second'):
        return self.mobile.call('rdc_mobile_app_'+action,{'session_id':self.sid,'profile':profile,'app_observation_id':observation['app_observation_id']})
    def mutation_count(self):return sum(bool(b and b.get('script') in ('mobile: launchApp','mobile: terminateApp')) for _,_,b in self.mobile.calls)
    def test_open_switches_and_invalidates_old_controls(self):
        old=self.mobile.call('rdc_mobile_observe',{'session_id':self.sid}); result=self.act('open',self.state()); self.assertTrue(result['foreground_verified']);self.assertEqual('second',result['active_profile']); self.assertEqual(1,self.mutation_count());self.assertIsNone(result['observation_id']);self.assertNotIn('org.example',json.dumps(result));self.assertNotIn('private-driver',json.dumps(result))
        with self.assertRaises(RDCError):self.mobile.call('rdc_mobile_tap',{'session_id':self.sid,'observation_id':old['observation_id'],'handle':'c1'})
        self.assertTrue(self.mobile.call('rdc_mobile_observe',{'session_id':self.sid})['observation_id'])
    def test_close_and_reopen(self):
        self.act('open',self.state()); self.assertTrue(self.act('terminate',self.state())['terminated_verified']);self.assertEqual(2,self.mutation_count());
        with self.assertRaises(RDCError):self.mobile.call('rdc_mobile_observe',{'session_id':self.sid})
        self.assertTrue(self.act('open',self.state())['foreground_verified']);self.assertEqual(3,self.mutation_count())
    def test_cross_device_and_endpoint_refused_before_driver(self):
        before=len(self.mobile.calls)
        for name in ('wrong_device','wrong_endpoint','missing'):
            with self.assertRaises(RDCError):self.state(name)
        self.assertEqual(before,len(self.mobile.calls))
    def test_changed_foreground_blocks_before_mutation(self):
        o=self.state();self.mobile.foreground=('org.example.first',99)
        with self.assertRaises(RDCError) as e:self.act('open',o)
        self.assertEqual('stale_observation',e.exception.code);self.assertEqual(0,self.mutation_count())
    def test_single_use_ticket_no_replay(self):
        o=self.state();self.act('open',o)
        with self.assertRaises(RDCError):self.act('open',o)
        self.assertEqual(1,self.mutation_count())
    def test_lost_launch_response_blocks_input_until_exact_reobservation(self):
        o=self.state();self.mobile.fail_launch=True
        with self.assertRaises(RDCError) as e:self.act('open',o)
        self.assertEqual('mobile_app_outcome_unknown',e.exception.code);self.assertEqual(1,self.mutation_count())
        with self.assertRaises(RDCError):self.mobile.call('rdc_mobile_observe',{'session_id':self.sid})
        self.assertEqual('foreground',self.state()['app_state']);self.assertTrue(self.mobile.call('rdc_mobile_observe',{'session_id':self.sid})['observation_id']);self.assertEqual(1,self.mutation_count())
    def test_false_termination_is_not_success(self):
        self.act('open',self.state());self.mobile.false_terminate=True
        with self.assertRaises(RDCError):self.act('terminate',self.state())
        self.assertEqual(2,self.mutation_count())
    def test_invalid_state_refused(self):
        self.mobile.invalid_state=True
        with self.assertRaises(RDCError):self.state()
        self.assertEqual(0,self.mutation_count())
    def test_already_foreground_open_is_read_only(self):
        result=self.act('open',self.state('first'),'first');self.assertTrue(result['foreground_verified']);self.assertEqual(0,self.mutation_count())
    def test_privacy_latch_persists_across_switch(self):
        self.mobile._sessions[self.sid]['sensitive']=True;self.act('open',self.state());self.assertTrue(self.mobile.status()['sessions'][0]['privacy_sensitive'])
    def test_regular_observation_invalidates_lifecycle_ticket(self):
        o=self.state();self.mobile.call('rdc_mobile_observe',{'session_id':self.sid})
        with self.assertRaises(RDCError):self.act('open',o)
        self.assertEqual(0,self.mutation_count())
    def test_app_state_scope_rebind_only_exact_target(self):
        self.mobile.foreground=('com.apple.springboard',99);self.mobile.apps['org.example.first']=3;self.state()
        with self.assertRaises(RDCError):self.mobile.call('rdc_mobile_observe',{'session_id':self.sid})
        self.assertEqual(0,self.mutation_count())
