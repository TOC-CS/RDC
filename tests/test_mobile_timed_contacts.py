"""Generic multi-contact trajectories; real worker compilation and validation."""
import unittest
from rdc.errors import RDCError
from rdc.mobile import ELEMENT_KEY
from tests.test_mobile_visual_input import VisualDriver, TREE, WINDOW, SECURE

ANCHOR={ELEMENT_KEY:'native-window'}
CONTACTS=[
    {'points':[{'at_ms':0,'x':40,'y':100},{'at_ms':200,'x':80,'y':100},{'at_ms':450,'x':80,'y':150}], 'release_ms':650},
    {'points':[{'at_ms':100,'x':240,'y':180},{'at_ms':300,'x':260,'y':180}], 'release_ms':400},
    {'points':[{'at_ms':350,'x':160,'y':300}], 'release_ms':500},
]

def interpret(sources,center=(200,400)):
    # Native chains sum their own durations; W3C ticks use the maximum per tick.
    # Verify both clocks independently, including staggered starts and releases.
    out={}; absolute={}; clock=0; offsets={s['id']:0 for s in sources}
    points={};active=set()
    for tick in range(max(len(s['actions']) for s in sources)):
        events=[(s['id'],s['actions'][tick]) for s in sources if tick<len(s['actions'])]
        for key,e in events:
            typ=e['type'];d=e.get('duration',0)
            if typ=='pointerMove':
                if isinstance(e['origin'],dict):p=(center[0]+e['x'],center[1]+e['y'])
                elif e['origin']=='pointer':p=(points[key][0]+e['x'],points[key][1]+e['y'])
                else:raise AssertionError('unexpected origin')
                points[key]=p
                if key in active:out[key]['moves'][clock+d]=p
            elif typ=='pointerDown':
                if key in active:raise AssertionError('duplicate down')
                if offsets[key]!=clock:raise AssertionError('misaligned down')
                out[key]={'start':clock,'initial':points[key],'moves':{},'end':None}
                active.add(key)
            elif typ=='pointerUp':
                if key not in active or offsets[key]!=clock:raise AssertionError('misaligned release')
                out[key]['end']=clock;out[key]['last']=points[key];active.remove(key)
            offsets[key]+=d
        clock+=max((e.get('duration',0) for _,e in events),default=0)
    if active:raise AssertionError('unreleased touch')
    return out

class TimelineTests(unittest.TestCase):
    def setUp(self):
        profile={'platformName':'iOS','automationName':'XCUITest','endpoint':'http://127.0.0.1:4723',
                 'capabilities':{'appium:udid':'fixture-device','appium:bundleId':'org.example.first'}}
        self.default_profile=profile
        self.mobile=VisualDriver({'first':{**profile,'capabilities':{**profile['capabilities'],'rdc:experimentalTimedContacts':True}},
                                  'second':{**profile,'capabilities':{**profile['capabilities'],'appium:bundleId':'org.example.second'}}})
        self.sid=self.mobile.call('rdc_mobile_start',{'profile':'first'})['session_id']
    def tearDown(self):self.mobile.close()
    def frame(self):return self.mobile.call('rdc_mobile_screenshot',{'session_id':self.sid,'include_observation':True})
    def send(self,f,contacts=CONTACTS,**kwargs):
        return self.mobile.call('rdc_mobile_command_execute',{'operation':'visual_timeline','arguments':{'session_id':self.sid,'observation_id':f['observation_id'],'contacts':contacts,**kwargs}})
    def sent(self):return [b for m,p,b in self.mobile.calls if m=='POST' and p.endswith('/actions')]
    def test_staggered_multicontact_path_is_single_native_dispatch(self):
        r=self.send(self.frame())
        self.assertEqual('visual_timeline',r['performed']);self.assertEqual(1,len(self.sent()))
        actions=self.sent()[0]['actions'];self.assertEqual(3,len(actions))
        result=interpret(actions)
        self.assertEqual((0,650,(40,100),(80,150)),(result['rdc-timed-1']['start'],result['rdc-timed-1']['end'],result['rdc-timed-1']['initial'],result['rdc-timed-1']['last']))
        self.assertEqual((100,400,(240,180),(260,180)),(result['rdc-timed-2']['start'],result['rdc-timed-2']['end'],result['rdc-timed-2']['initial'],result['rdc-timed-2']['last']))
        self.assertEqual((350,500,(160,300),(160,300)),(result['rdc-timed-3']['start'],result['rdc-timed-3']['end'],result['rdc-timed-3']['initial'],result['rdc-timed-3']['last']))
        self.assertEqual((80,100),result['rdc-timed-1']['moves'][200]);self.assertEqual((80,150),result['rdc-timed-1']['moves'][450])
        self.assertEqual([650,500,400],[result[x['id']]['end'] for x in actions])
        self.assertEqual(650,r['requested_duration_ms'])
    def test_same_time_release_keeps_unique_identity(self):
        c=[{'points':[{'at_ms':0,'x':10,'y':10}],'release_ms':100},{'points':[{'at_ms':0,'x':30,'y':10}],'release_ms':100}]
        r=self.send(self.frame(),c);out=interpret(self.sent()[0]['actions'])
        self.assertEqual({100},{v['end'] for v in out.values()});self.assertEqual(2,len(out))
    def test_all_later_points_must_be_in_bounds(self):
        c=[{'points':[{'at_ms':0,'x':20,'y':20},{'at_ms':100,'x':400,'y':20}],'release_ms':200}]
        with self.assertRaises(RDCError):self.send(self.frame(),c)
        self.assertEqual([],self.sent())
    def test_times_must_increase_strictly(self):
        c=[{'points':[{'at_ms':0,'x':20,'y':20},{'at_ms':0,'x':30,'y':20}],'release_ms':200}]
        with self.assertRaises(RDCError):self.send(self.frame(),c)
        self.assertEqual([],self.sent())
    def test_release_before_final_waypoint_refused(self):
        c=[{'points':[{'at_ms':0,'x':20,'y':20},{'at_ms':200,'x':30,'y':20}],'release_ms':100}]
        with self.assertRaises(RDCError):self.send(self.frame(),c)
        self.assertEqual([],self.sent())
    def test_delayed_first_contact_refused(self):
        c=[{'points':[{'at_ms':100,'x':20,'y':20}],'release_ms':200}]
        with self.assertRaises(RDCError):self.send(self.frame(),c)
        self.assertEqual([],self.sent())
    def test_plain_observation_cannot_authorize_timeline(self):
        with self.assertRaises(RDCError):self.send(self.mobile.call('rdc_mobile_observe',{'session_id':self.sid}))
        self.assertEqual([],self.sent())
    def test_secure_hierarchy_refuses_frame(self):
        self.mobile.xml=TREE.format(WINDOW+SECURE)
        with self.assertRaises(RDCError):self.frame()
        self.assertEqual([],self.sent())
    def test_changed_app_refuses_before_dispatch(self):
        f=self.frame();self.mobile.foreground=('org.example.first',99)
        with self.assertRaises(RDCError):self.send(f)
        self.assertEqual([],self.sent())
    def test_failed_input_releases_once_without_replay(self):
        f=self.frame();self.mobile.failed=True
        with self.assertRaises(RDCError):self.send(f)
        with self.assertRaises(RDCError):self.send(f)
        self.assertEqual(1,len(self.sent()))
        self.assertEqual(1,sum(m=='DELETE' and p.endswith('/actions') for m,p,b in self.mobile.calls))
    def test_post_frame_preserves_acknowledgement_and_reports_timings(self):
        r=self.send(self.frame(),post_frame_max_edge=640)
        self.assertEqual('captured',r['frame_status'])
        self.assertTrue(r['visual_gesture_available'])
        self.assertGreaterEqual(r['timings_ms']['action_to_frame'],r['timings_ms']['input_acknowledgement'])
        self.assertEqual(1,len(self.sent()))
    def test_excessive_contact_count_refused(self):
        with self.assertRaises(RDCError):self.send(self.frame(),CONTACTS+[CONTACTS[0]])
        self.assertEqual([],self.sent())
    def test_terminal_stationary_holds_do_not_resolve_redundant_coordinates(self):
        c=[
            {'points':[{'at_ms':0,'x':30,'y':40},{'at_ms':100,'x':50,'y':40}], 'release_ms':500},
            {'points':[{'at_ms':50,'x':240,'y':250},{'at_ms':250,'x':260,'y':250}], 'release_ms':350},
            {'points':[{'at_ms':200,'x':180,'y':300}], 'release_ms':400},
        ]
        self.send(self.frame(),c)
        sources=self.sent()[0]['actions'];by_id={s['id']:s for s in sources}
        # The third contact never moves after its initial anchor. Native
        # pause durations maintain its contact and exact release offset.
        self.assertEqual(1,sum(e['type']=='pointerMove' for e in by_id['rdc-timed-3']['actions']))
        out=interpret(sources)
        self.assertEqual((200,400,(180,300)),(out['rdc-timed-3']['start'],out['rdc-timed-3']['end'],out['rdc-timed-3']['last']))
        self.assertEqual((50,40),out['rdc-timed-1']['last'])
        self.assertEqual(500,out['rdc-timed-1']['end'])
    def test_stationary_before_future_movement_keeps_native_waypoint(self):
        c=[{'points':[{'at_ms':0,'x':30,'y':40},{'at_ms':100,'x':30,'y':40},{'at_ms':300,'x':60,'y':50}], 'release_ms':400}]
        self.send(self.frame(),c)
        out=interpret(self.sent()[0]['actions'])['rdc-timed-1']
        self.assertEqual((30,40),out['moves'][100])
        self.assertEqual((60,50),out['moves'][300])
        self.assertEqual(400,out['end'])
    def test_terminal_hold_reduces_native_coordinate_resolution_count(self):
        self.send(self.frame())
        s=self.sent()[0]['actions'];self.assertEqual(11,sum(e['type']=='pointerMove' for c in s for e in c['actions']))
        self.assertEqual(1,len(self.sent()))
    def test_unqualified_default_profile_refuses_before_native_io(self):
        self.mobile.close()
        self.mobile=VisualDriver({'first':self.default_profile})
        self.sid=self.mobile.call('rdc_mobile_start',{'profile':'first'})['session_id']
        f=self.frame()
        before=len(self.mobile.calls)
        with self.assertRaises(RDCError):self.send(f)
        self.assertEqual(before,len(self.mobile.calls));self.assertEqual([],self.sent())
    def test_experimental_opt_in_is_not_forwarded_to_appium(self):
        self.assertFalse(any('rdc:experimentalTimedContacts' in b['capabilities']['alwaysMatch'] for m,p,b in self.mobile.calls if m=='POST' and p=='/session'))
    def test_nonboolean_opt_in_is_rejected(self):
        from rdc.mobile import validate_mobile_profiles
        profile={**self.default_profile,'capabilities':{**self.default_profile['capabilities'],'rdc:experimentalTimedContacts':'true'}}
        with self.assertRaises(RDCError):validate_mobile_profiles({'fixture':profile})
    def test_other_app_does_not_inherit_original_qualification_grant(self):
        state=self.mobile.call('rdc_mobile_app_state',{'session_id':self.sid,'profile':'second'})
        self.mobile.call('rdc_mobile_app_open',{'session_id':self.sid,'profile':'second','app_observation_id':state['app_observation_id']})
        f=self.frame();before=len(self.mobile.calls)
        with self.assertRaises(RDCError):self.send(f)
        self.assertEqual(before,len(self.mobile.calls));self.assertEqual([],self.sent())
