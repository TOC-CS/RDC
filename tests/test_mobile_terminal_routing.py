"""One submitted device-local command, verified by its fresh result receipt."""
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rdc.mobile import Mobile
from rdc.errors import RDCError

COMPANION = 'org.tocministries.rdc.mobile'
RUN_ID = '11111111-1111-4111-8111-111111111111'
COMMAND = 'echo local-test'
DIGEST = hashlib.sha256(COMMAND.encode()).hexdigest()

def profile(bundle=COMPANION, platform='iOS'):
    caps={'appium:udid':'owner-device'}
    if platform=='iOS': caps['appium:bundleId']=bundle
    else: caps['appium:appPackage']=bundle
    return {'platformName':platform,'automationName':'XCUITest' if platform=='iOS' else 'UiAutomator2','endpoint':'http://127.0.0.1:4723','capabilities':caps}

def tree(session, *, receipt='', marker=True, enabled=True, secure=False):
    return {'session_id':session['session_id'],'observation_id':session['observation_id'],
            'text':('RDC device-local terminal\n' if marker else '')+receipt,
            'controls':[{'handle':'c1','can_fill':True,'editable':True,'secure':secure,'name':'Text field'},
                        {'handle':'c2','can_tap':enabled,'editable':False,'secure':False,'name':'Run local command'}],
            'text_truncated':False,'controls_truncated':False,'control_scan_truncated':False}

class TerminalRoutingTests(unittest.TestCase):
    def setUp(self):
        self.m=Mobile(SimpleNamespace(mobile_profiles={'device':profile()}))
        self.sid='mobile-11111111-1111-4111-8111-111111111111'
        self.s={'session_id':self.sid,'profile':'device','platform':'iOS','driver_id':'fixture',
                'observation_id':'obs1','handles':{},'sensitive':False,'width':400,'height':800,
                'backend':'appium','kind':'mobile','automation':'XCUITest','title':'fixture','cursor':{'x':0,'y':0}}
        self.m._sessions[self.sid]=self.s
        from rdc.mobile_command_engine import record_terminal_observation
        record_terminal_observation(self.s,tree(self.s))
        self.calls=[]
        self.reads=0
        self.receipt='RDC terminal result | device-local | run='+RUN_ID+' | command='+DIGEST+' | exit=0 | 0.12 ms\nlocal-test'
    def tearDown(self):
        self.m._sessions.clear();self.m.close()
    def act(self,s,action,args):
        self.calls.append(action)
        s['observation_id']=None
        return {'performed':action}
    def observe(self,s):
        self.reads+=1;s['observation_id']='obs'+str(self.reads+1)
        return tree(s,receipt=self.receipt if self.reads==2 else '')
    def run_command(self,**updates):
        args={'session_id':self.sid,'observation_id':'obs1','command':COMMAND};args.update(updates)
        with patch.object(self.m,'_act',side_effect=self.act),patch.object(self.m,'_observe',side_effect=self.observe):
            return self.m.call('rdc_mobile_command_execute',{'operation':'local_command','arguments':args})
    def test_verified_receipt_and_one_submission(self):
        r=self.run_command();self.assertEqual(self.calls,['fill','tap']);self.assertTrue(r['execution_verified']);self.assertEqual(r['exit_code'],0);self.assertEqual(r['command_route'],'mobile_sandbox')
    def test_wrong_bundle_refused(self):
        self.m._profiles['device']=profile('org.example.other')
        with self.assertRaises(RDCError):self.run_command()
        self.assertEqual([],self.calls)
    def test_stale_observation_refused(self):
        with self.assertRaises(RDCError):self.run_command(observation_id='old')
        self.assertEqual([],self.calls)
    def test_unverified_output_never_claims_execution(self):
        self.receipt=self.receipt.replace(DIGEST,'a'*64)
        r=self.run_command();self.assertFalse(r['execution_verified']);self.assertEqual(['fill','tap'],self.calls)
    def test_duplicate_receipt_refused(self):
        from rdc.mobile_command_engine import record_terminal_observation
        record_terminal_observation(self.s,tree(self.s,receipt=self.receipt))
        r=self.run_command();self.assertFalse(r['execution_verified']);self.assertEqual(['fill','tap'],self.calls)
    def test_lost_submit_response_is_unknown_no_retry(self):
        def lost(s,action,args):
            self.calls.append(action)
            if action=='tap':raise RDCError('mobile_unavailable','lost')
            return {'performed':action}
        self.act=lost
        r=self.run_command();self.assertEqual('unknown',r['submission_status']);self.assertFalse(r['execution_verified']);self.assertEqual(['fill','tap'],self.calls)
    def test_missing_marker_refused(self):
        from rdc.mobile_command_engine import record_terminal_observation
        record_terminal_observation(self.s,tree(self.s,marker=False))
        with self.assertRaises(RDCError):self.run_command()
        self.assertEqual([],self.calls)
    def test_control_character_refused(self):
        with self.assertRaises(RDCError):self.run_command(command='pwd\nwhoami')
        self.assertEqual([],self.calls)
    def test_android_exact_package_refusal(self):
        self.s['platform']='Android';self.m._profiles['device']=profile(platform='Android')
        with patch.object(self.m,'_wd',return_value='org.example.other'):
            with self.assertRaises(RDCError):self.run_command()
        self.assertEqual([],self.calls)
    def test_capabilities_exposes_concrete_schema(self):
        r=self.m.call('rdc_mobile_command_read',{'operation':'capabilities','arguments':{}})
        self.assertIn('local_command',r['execute']);self.assertIn('command',r['execute']['local_command']['input_schema']['properties'])
