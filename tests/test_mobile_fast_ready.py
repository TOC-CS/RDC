"""Owner-scoped app discovery, immediate control discovery, and fast-source contracts."""
import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from rdc.errors import RDCError
from rdc.mobile import validate_mobile_profiles
from tests.test_mobile_app_lifecycle import FakeMobile

def profile(bundle, fast=False, discover=False):
    caps={'appium:udid':'owner-tablet','appium:bundleId':bundle,'appium:noReset':True}
    if fast: caps['rdc:completeSource']=True
    if discover: caps['rdc:installedAppDiscovery']=True
    return {'platformName':'iOS','automationName':'XCUITest','endpoint':'http://127.0.0.1:4723','capabilities':caps}

class FastDriver(FakeMobile):
    def __init__(self, profiles):
        self.specs=[]; self.bad_source=False; self.protected=False; self.lose_source=False
        self.bad_settings=False; self.wrong_pid=False; self.inventory_calls=0
        super().__init__(profiles)
        self.apps['org.example.music']=1
    def _http(self,profile,method,path,body=None,timeout=35):
        script=body.get('script') if isinstance(body,dict) else None
        if path.endswith('/appium/settings'):
            self.calls.append((method,path,body))
            if method=='POST': return None
            return {'rdcCompleteSourceEnabled':not self.bad_settings,'useJSONSource':False,'pageSourceExcludedAttributes':'','includeHittableInPageSource':False,'includeNativeFrameInPageSource':False,'includeNativeAccessibilityElementInPageSource':False,'includeMinMaxValueInPageSource':False,'includeCustomActionsInPageSource':False,'enforceCustomSnapshots':False,'rdcBatchVisibilityAttributes':False,'snapshotMaxDepth':50,'snapshotMaxChildren':2147483647,'autoClickAlertSelector':'','defaultAlertAction':''}
        if script=='mobile: listApps':
            self.calls.append((method,path,body)); self.inventory_calls+=1
            return {'org.example.music':{'CFBundleDisplayName':'Music Fixture','ApplicationType':'User'},'org.example.second':{'CFBundleName':'Second Fixture','ApplicationType':'User'},'com.apple.springboard':{'CFBundleName':'SpringBoard','ApplicationType':'System'},'org.example.wda.xctrunner':{'CFBundleName':'Driver','ApplicationType':'User'}}
        if script=='mobile: rdcCompleteSource':
            self.calls.append((method,path,body)); spec=body['args'][0]['spec']; self.specs.append(dict(spec))
            if self.lose_source: raise RDCError('mobile_unavailable','private payload')
            bundle,pid=self.foreground
            root=ET.Element('AppiumAUT')
            app=ET.SubElement(root,'XCUIElementTypeApplication',{'type':'XCUIElementTypeApplication','bundleId':bundle,'processId':str(pid+1 if self.wrong_pid else pid),'visible':'true','enabled':'true','x':'0','y':'0','width':'400','height':'800'})
            ET.SubElement(app,'XCUIElementTypeButton',{'type':'XCUIElementTypeButton','label':'Play','visible':'true','enabled':'true','accessible':'true','x':'10','y':'10','width':'30','height':'30'})
            if self.protected: ET.SubElement(app,'XCUIElementTypeSecureTextField',{'type':'XCUIElementTypeSecureTextField','visible':'false','enabled':'true','value':'private_secret'})
            xml=ET.tostring(root,encoding='unicode'); raw=xml.encode(); n=len(list(root.iter()))
            return {'schema':1,'request_id':spec['request_id'],'sequence':spec['sequence'],'outcome':'complete','refusal_code':None,'recovery_required':False,'privacy_latched':False,'xml':xml,'xml_sha256':'0'*64 if self.bad_source else hashlib.sha256(raw).hexdigest(),'parameters_sha256':'b'*64,'metrics':{'total_ms':130,'foreground_before_ms':5,'wait_ms':5,'snapshot_ms':100,'validate_ms':2,'serialize_ms':10,'foreground_after_ms':5,'bulk_snapshot_calls':1,'source_single_calls':0,'source_batch_calls':0,'source_batch_fallbacks':0,'xml_bytes':len(raw),'xml_nodes':n,'xml_max_depth':3,'tree_nodes':n-1,'tree_max_depth':2,'snapshot_parameter_count':5}}
        return super()._http(profile,method,path,body,timeout)

class FastReadyTests(unittest.TestCase):
    def setUp(self): self.m=FastDriver({'first':profile('org.example.first',True,True),'second':profile('org.example.second')}); self.sid=None
    def tearDown(self): self.m.close()
    def start(self, ready=True):
        r=self.m.call('rdc_mobile_start',{'profile':'first','include_observation':ready}); self.sid=r['session_id']; return r
    def open(self, alias='second'):
        o=self.m.call('rdc_mobile_app_state',{'session_id':self.sid,'profile':alias})
        return self.m.call('rdc_mobile_app_open',{'session_id':self.sid,'profile':alias,'app_observation_id':o['app_observation_id'],'include_observation':True})
    def test_start_ready_avoids_duplicate_context_geometry(self):
        r=self.start(); self.assertTrue(r['ready']); self.assertEqual('Play',r['controls'][0]['name'])
        self.assertEqual(1,len(self.m.specs)); self.assertEqual(1,sum(p.endswith('/context') for _,p,_ in self.m.calls)); self.assertEqual(1,sum(p.endswith('/window/rect') for _,p,_ in self.m.calls))
        self.assertNotIn('rdc:completeSource',json.dumps(self.m.calls[0][2])); self.assertNotIn('rdc:installedAppDiscovery',json.dumps(self.m.calls[0][2]))
        self.assertGreaterEqual(r['timings_ms']['launch_to_ready'],r['timings_ms']['control_discovery'])
    def test_open_ready_uses_new_app_identity(self):
        self.start(); r=self.open(); self.assertTrue(r['ready']); self.assertEqual('second',r['active_profile'])
        self.assertEqual([1,2],[s['sequence'] for s in self.m.specs]); self.assertEqual('org.example.second',self.m.specs[-1]['expected_bundle_id']); self.assertEqual(22,self.m.specs[-1]['expected_pid'])
    def test_read_failure_preserves_launch_ack_and_no_replay(self):
        self.start(); self.m.lose_source=True; r=self.open(); self.assertFalse(r['ready']); self.assertTrue(r['foreground_verified']); self.assertEqual('cleanup_required',r['setup_status'])
        self.assertEqual(1,sum(bool(b and b.get('script')=='mobile: launchApp') for _,_,b in self.m.calls))
    def test_wrong_identity_refuses(self):
        self.m.wrong_pid=True; r=self.start(); self.assertFalse(r['ready']); self.assertIsNone(r['observation_id']); self.assertEqual('cleanup_required',r['setup_status'])
    def test_bad_digest_refuses_no_legacy_fallback(self):
        self.m.bad_source=True; r=self.start(); self.assertFalse(r['ready']); self.assertEqual(1,len(self.m.specs)); self.assertFalse(any(p.endswith('/source') for _,p,_ in self.m.calls))
    def test_protected_field_latches(self):
        self.m.protected=True; r=self.start(); self.assertFalse(r['ready']); self.assertTrue(r['privacy_sensitive']); self.assertNotIn('private_secret',json.dumps(r))
    def test_unsupported_settings_prevents_source(self):
        self.m.bad_settings=True
        with self.assertRaises(RDCError): self.start()
        self.assertEqual([],self.m.specs); self.assertEqual([],self.m.status()['sessions'])
    def test_inventory_returns_only_scoped_opaque_selectors(self):
        self.start(); r=self.m.call('rdc_mobile_app_discover',{'session_id':self.sid})
        self.assertEqual(1,self.m.inventory_calls); self.assertEqual({'Music Fixture','Second Fixture'},{a['name'] for a in r['apps']}); self.assertNotIn('org.example.music',json.dumps(r))
        alias=next(a['profile'] for a in r['apps'] if a['name']=='Music Fixture'); out=self.open(alias)
        self.assertTrue(out['ready']); self.assertEqual(alias,out['active_profile']); self.assertEqual('org.example.music',self.m.specs[-1]['expected_bundle_id'])
    def test_discovery_requires_owner_opt_in(self):
        m=FastDriver({'first':profile('org.example.first')}); sid=m.call('rdc_mobile_start',{'profile':'first'})['session_id']
        try:
            with self.assertRaises(RDCError): m.call('rdc_mobile_app_discover',{'session_id':sid})
            self.assertEqual(0,m.inventory_calls)
        finally: m.close()
    def test_guessed_bundle_refused_without_driver_io(self):
        self.start(); before=len(self.m.calls)
        with self.assertRaises(RDCError): self.m.call('rdc_mobile_app_state',{'session_id':self.sid,'profile':'org.example.music'})
        self.assertEqual(before,len(self.m.calls))
    def test_invalid_opt_in_refused(self):
        for key in ('rdc:completeSource','rdc:installedAppDiscovery'):
            p=profile('org.example.first'); p['capabilities'][key]='true'
            with self.assertRaises(RDCError): validate_mobile_profiles({'first':p})
    def test_legacy_ready_one_source_and_no_private_driver_fields(self):
        m=FastDriver({'first':profile('org.example.first')})
        try:
            r=m.call('rdc_mobile_start',{'profile':'first','include_observation':True})
            self.assertTrue(r['ready']); self.assertEqual(1,sum(p.endswith('/source') for _,p,_ in m.calls)); self.assertNotIn('private-driver',json.dumps(r))
        finally: m.close()
