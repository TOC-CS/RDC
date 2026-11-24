"""Source-only contracts for privacy-checked, window-anchored visual input."""
import base64
import copy
import unittest
from unittest.mock import patch
from rdc.errors import RDCError
from tests.test_mobile import png
from tests.test_mobile_app_lifecycle import FakeMobile

WINDOW='<XCUIElementTypeWindow type="XCUIElementTypeWindow" enabled="true" visible="true" x="0" y="0" width="400" height="800" />'
TREE='<AppiumAUT><XCUIElementTypeApplication type="XCUIElementTypeApplication" visible="true" enabled="true" x="0" y="0" width="400" height="800">{}</XCUIElementTypeApplication></AppiumAUT>'
SECURE='<XCUIElementTypeSecureTextField type="XCUIElementTypeSecureTextField" visible="true" enabled="true" x="1" y="1" width="20" height="20" />'

class VisualDriver(FakeMobile):
    def __init__(self,profiles):
        self.xml=TREE.format(WINDOW);self.rect={'x':0,'y':0,'width':400,'height':800};self.failed=False
        super().__init__(profiles)
    def _http(self,profile,method,path,body=None,timeout=35):
        if path.endswith(('/source','/screenshot','/element','/rect','/actions')) and not path.endswith('/window/rect'):
            self.calls.append((method,path,copy.deepcopy(body)))
            if path.endswith('/source'):return self.xml
            if path.endswith('/screenshot'):return base64.b64encode(png(400,800)).decode()
            if path.endswith('/element'):return {'element-6066-11e4-a52e-4f735466cecf':'native-window'}
            if path.endswith('/rect'):return self.rect
            if method=='POST' and path.endswith('/actions') and self.failed:raise RDCError('mobile_unavailable','uncertain')
            return None
        return super()._http(profile,method,path,body,timeout)

class VisualInputTests(unittest.TestCase):
    def setUp(self):
        self.mobile=VisualDriver({'first':{'platformName':'iOS','automationName':'XCUITest','endpoint':'http://127.0.0.1:4723','capabilities':{'appium:udid':'owner-tablet','appium:bundleId':'org.example.first'}}});self.sid=self.mobile.call('rdc_mobile_start',{'profile':'first'})['session_id']
    def tearDown(self):self.mobile.close()
    def frame(self):return self.mobile.call('rdc_mobile_screenshot',{'session_id':self.sid,'include_observation':True})
    def act(self,o,touches=None):return self.mobile.call('rdc_mobile_visual_gesture',{'session_id':self.sid,'observation_id':o['observation_id'],'touches':touches or [{'start_x':20,'start_y':30,'end_x':40,'end_y':50}],'move_ms':50})
    def sent(self):return [b for m,p,b in self.mobile.calls if m=='POST' and p.endswith('/actions')]
    def test_verified_frame_allows_window_anchored_two_touch_without_accessible_controls(self):
        o=self.frame();self.assertEqual([],o['controls']);self.assertTrue(o['visual_gesture_available']);r=self.act(o,[{'start_x':20,'start_y':30,'end_x':40,'end_y':50,'hold_ms':50},{'start_x':200,'start_y':300,'end_x':210,'end_y':330,'hold_ms':100}]);self.assertEqual('visual_gesture',r['performed']);self.assertEqual(1,len(self.sent()));self.assertEqual(2,len(self.sent()[0]['actions']));self.assertEqual({'element-6066-11e4-a52e-4f735466cecf':'native-window'},self.sent()[0]['actions'][0]['actions'][0]['origin']);self.assertIsNone(r['observation_id'])
    def test_plain_observation_does_not_grant_visual_input(self):
        o=self.mobile.call('rdc_mobile_observe',{'session_id':self.sid});before=len(self.mobile.calls)
        with self.assertRaises(RDCError):self.act(o)
        self.assertEqual(before,len(self.mobile.calls));self.assertEqual([],self.sent())
    def test_duplicate_full_windows_refused(self):
        self.mobile.xml=TREE.format(WINDOW+WINDOW);o=self.frame();self.assertFalse(o['visual_gesture_available']);
        with self.assertRaises(RDCError):self.act(o)
        self.assertEqual([],self.sent())
    def test_nonfullscreen_window_refused(self):
        self.mobile.xml=TREE.format(WINDOW.replace('width="400"','width="399"'));o=self.frame();self.assertFalse(o['visual_gesture_available'])
    def test_secure_field_blocks_capture(self):
        self.mobile.xml=TREE.format(WINDOW+SECURE)
        with self.assertRaises(RDCError):self.frame()
        self.assertFalse(any(p.endswith('/screenshot') for _,p,_ in self.mobile.calls));self.assertEqual([],self.sent())
    def test_changed_native_geometry_refuses_before_dispatch(self):
        o=self.frame();self.mobile.rect['width']=399
        with self.assertRaises(RDCError):self.act(o)
        self.assertEqual([],self.sent())
    def test_changed_process_refuses_before_dispatch(self):
        o=self.frame();self.mobile.foreground=('org.example.first',99)
        with self.assertRaises(RDCError):self.act(o)
        self.assertEqual([],self.sent())
    def test_stale_visual_frame_refused(self):
        o=self.frame();self.mobile._sessions[self.sid]['visual_frame']['deadline']=0
        with self.assertRaises(RDCError):self.act(o)
        self.assertEqual([],self.sent())
    def test_outside_touch_refused(self):
        o=self.frame()
        with self.assertRaises(RDCError):self.act(o,[{'start_x':399,'start_y':2,'end_x':400,'end_y':2}])
        self.assertEqual([],self.sent())
    def test_failed_action_releases_once_and_ticket_cannot_replay(self):
        o=self.frame();self.mobile.failed=True
        with self.assertRaises(RDCError):self.act(o)
        with self.assertRaises(RDCError):self.act(o)
        self.assertEqual(1,len(self.sent()));self.assertEqual(1,sum(m=='DELETE' and p.endswith('/actions') for m,p,b in self.mobile.calls))
    def test_plain_preview_invalidates_old_visual_ticket(self):
        o=self.frame();self.mobile.call('rdc_mobile_screenshot',{'session_id':self.sid})
        with self.assertRaises(RDCError):self.act(o)
        self.assertEqual([],self.sent())
