"""Input acknowledgement and structured post-action readback are distinct."""
import copy
import unittest
from rdc.errors import RDCError
from tests.test_mobile_app_lifecycle import FakeMobile
from tests.test_mobile import IOS_XML

class FixtureDriver(FakeMobile):
    def __init__(self):
        self.xml=IOS_XML
        self.fail_click=False
        self.fail_read=False
        self.fail_after_click=False
        super().__init__({'fixture':{'platformName':'iOS','automationName':'XCUITest',
            'endpoint':'http://127.0.0.1:4723','capabilities':
            {'appium:udid':'fixture-device','appium:bundleId':'org.example.first'}}})
    def _http(self,profile,method,path,body=None,timeout=35):
        if path.endswith('/source'):
            self.calls.append((method,path,copy.deepcopy(body)))
            if self.fail_read:raise RDCError('observation_failed','fixture')
            return self.xml
        if path.endswith('/element'):
            self.calls.append((method,path,copy.deepcopy(body)))
            return {'element-6066-11e4-a52e-4f735466cecf':'fixture-element'}
        if path.endswith('/click'):
            self.calls.append((method,path,copy.deepcopy(body)))
            if self.fail_click:raise RDCError('mobile_unavailable','fixture')
            self.xml=self.xml.replace('label="Save"','label="Saved"').replace('name="Save"','name="Saved"')
            if self.fail_after_click:self.fail_read=True
            return None
        return super()._http(profile,method,path,body,timeout)

class ActionObserveTests(unittest.TestCase):
    def setUp(self):
        self.mobile=FixtureDriver()
        self.sid=self.mobile.call('rdc_mobile_start',{'profile':'fixture'})['session_id']
        self.observed=self.mobile.call('rdc_mobile_observe',{'session_id':self.sid})
        self.args={'session_id':self.sid,'observation_id':self.observed['observation_id'],'handle':next(c['handle'] for c in self.observed['controls'] if c['name']=='Save')}
    def tearDown(self):self.mobile.close()
    def clicks(self):return sum(m=='POST' and p.endswith('/click') for m,p,b in self.mobile.calls)
    def test_tap_returns_fresh_controls_and_separate_timings(self):
        r=self.mobile.call('rdc_mobile_tap',{**self.args,'post_observation':True})
        self.assertEqual('tap',r['performed'])
        self.assertEqual('observed',r['observation_status'])
        self.assertIn('Saved',[c['name'] for c in r['controls']])
        self.assertNotEqual(self.observed['observation_id'],r['observation_id'])
        self.assertGreaterEqual(r['timings_ms']['action_to_observation'],r['timings_ms']['input_acknowledgement'])
        self.assertEqual(1,self.clicks())
        self.assertFalse(any(p.endswith('/screenshot') for _,p,_ in self.mobile.calls))
    def test_acknowledgement_preserved_if_readback_fails(self):
        self.mobile.fail_after_click=True
        r=self.mobile.call('rdc_mobile_tap',{**self.args,'post_observation':True})
        self.assertEqual('tap',r['performed'])
        self.assertEqual('unavailable',r['observation_status'])
        self.assertIsNone(r['observation_id'])
        self.assertEqual(1,self.clicks())
        with self.assertRaises(RDCError):self.mobile.call('rdc_mobile_tap',{**self.args,'post_observation':True})
        self.assertEqual(1,self.clicks())
    def test_uncertain_input_does_not_trigger_post_observe_or_replay(self):
        self.mobile.fail_click=True
        before=sum(p.endswith('/source') for _,p,_ in self.mobile.calls)
        with self.assertRaises(RDCError):self.mobile.call('rdc_mobile_tap',{**self.args,'post_observation':True})
        self.assertEqual(1,self.clicks())
        self.assertEqual(before+1,sum(p.endswith('/source') for _,p,_ in self.mobile.calls))
    def test_default_remains_backward_compatible(self):
        r=self.mobile.call('rdc_mobile_tap',self.args)
        self.assertNotIn('observation_status',r)
        self.assertIsNone(r['observation_id'])
        self.assertEqual(1,self.clicks())
    def test_combined_request_rejects_conflicting_frame_before_dispatch(self):
        with self.assertRaises(RDCError):
            self.mobile.call('rdc_mobile_gesture',{'session_id':self.sid,
                'observation_id':self.observed['observation_id'],'anchor_handle':self.args['handle'],
                'touches':[{'start_x':20,'start_y':140,'end_x':30,'end_y':150}],
                'post_frame_max_edge':640,'post_observation':True})
        self.assertFalse(any(p.endswith('/actions') for _,p,_ in self.mobile.calls))
    def test_router_preserves_combined_input_contract(self):
        r=self.mobile.call('rdc_mobile_command_execute',{'operation':'tap','arguments':{**self.args,'post_observation':True}})
        self.assertEqual('observed',r['observation_status'])
        self.assertIn('Saved',[c['name'] for c in r['controls']])
        self.assertEqual(1,self.clicks())
