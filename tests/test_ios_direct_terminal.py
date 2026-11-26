import hashlib
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rdc.errors import RDCError
from rdc.ios_direct_terminal import DirectTerminal, COMPANION

def fixture_profile(bundle=COMPANION, udid='fixture-device-01', platform='iOS'):
    return {'platformName':platform, 'automationName':'XCUITest' if platform=='iOS' else 'UiAutomator2',
        'endpoint':'http://127.0.0.1:4723',
        'capabilities':{'appium:udid':udid,'appium:bundleId':bundle}}
class FakeTransport:
    def __init__(self):
        self.calls=[];self.payload=None;self.mode='normal';self.receipt=None
    def preflight(self,udid):
        self.calls.append('preflight')
        return self.mode!='wrong_version'
    def submit(self,udid,payload):
        self.calls.append('copy');self.payload=dict(payload)
        if self.mode=='copy_unknown':raise OSError()
        self.calls.append('launch')
        if self.mode=='launch_unknown':raise OSError()
        self.receipt={'schema':1,'request_id':payload['request_id'],'run_id':str(uuid.uuid4()),
            'command_sha256':payload['command_sha256'],'exit_code':0,'device_elapsed_ms':1.2,
            'output':'fixture','execution_location':'mobile_device'}
    def read(self,udid,request_id):
        self.calls.append('read')
        if self.mode=='missing':return None
        if self.mode=='wrong_digest' and self.receipt:return {**self.receipt,'command_sha256':'0'*64}
        return self.receipt

class DirectTerminalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.settings=SimpleNamespace(state_dir=Path(self.tmp.name),ios_direct_terminal_enabled=True)
        self.profiles={'one':fixture_profile(),'other':fixture_profile(udid='fixture-device-02'),
            'foreign':fixture_profile(bundle='org.example.other')}
        self.transport=FakeTransport()
        self.worker=DirectTerminal(self.settings,self.profiles,self.transport)
        self.ident=str(uuid.uuid4())
    def execute(self,command='echo fixture',profile='one',ident=None):
        return self.worker.execute(profile,ident or self.ident,command)
    def test_verified_submission_and_output(self):
        r=self.execute()
        self.assertTrue(r['execution_verified']);self.assertEqual('fixture',r['output'])
        self.assertEqual(['preflight','copy','launch','read'],self.transport.calls)
        self.assertEqual(hashlib.sha256(b'echo fixture').hexdigest(),r['command_sha256'])
    def test_disabled_by_default(self):
        self.settings.ios_direct_terminal_enabled=False
        w=DirectTerminal(self.settings,self.profiles,self.transport)
        with self.assertRaises(RDCError):w.execute('one',self.ident,'echo fixture')
        self.assertEqual([],self.transport.calls)
    def test_wrong_app_refused(self):
        with self.assertRaises(RDCError):self.execute(profile='foreign')
        self.assertEqual([],self.transport.calls)
    def test_duplicate_id_never_dispatches_again_after_restart(self):
        self.execute()
        self.worker=DirectTerminal(self.settings,self.profiles,self.transport)
        r=self.execute()
        self.assertTrue(r['execution_verified']);self.assertEqual(1,self.transport.calls.count('launch'));self.assertEqual(1,self.transport.calls.count('copy'))
    def test_changed_command_reusing_id_refused(self):
        self.execute()
        with self.assertRaises(RDCError):self.execute('echo changed')
        self.assertEqual(1,self.transport.calls.count('launch'))
    def test_wrong_device_recovery_refused(self):
        self.execute()
        with self.assertRaises(RDCError):self.worker.recover('other',self.ident)
        self.assertEqual(1,self.transport.calls.count('read'))
    def test_lost_copy_never_launches_and_blocks_new_request(self):
        self.transport.mode='copy_unknown';r=self.execute()
        self.assertFalse(r['execution_verified']);self.assertEqual('unknown',r['submission_status'])
        with self.assertRaises(RDCError):self.execute(ident=str(uuid.uuid4()))
        self.assertEqual(0,self.transport.calls.count('launch'))
        self.assertEqual(1,self.transport.calls.count('copy'))
    def test_lost_launch_recovery_only_reads(self):
        self.transport.mode='launch_unknown';r=self.execute()
        self.assertFalse(r['execution_verified'])
        self.transport.mode='normal'
        self.transport.receipt={'schema':1,'request_id':self.ident,'run_id':str(uuid.uuid4()),'command_sha256':hashlib.sha256(b'echo fixture').hexdigest(),'exit_code':0,'device_elapsed_ms':0.2,'output':'fixture','execution_location':'mobile_device'}
        self.assertTrue(self.worker.recover('one',self.ident)['execution_verified'])
        self.assertEqual(1,self.transport.calls.count('launch'));self.assertEqual(1,self.transport.calls.count('copy'))
    def test_bad_receipt_never_verified(self):
        self.transport.mode='wrong_digest';self.assertFalse(self.execute()['execution_verified'])
        self.assertEqual(1,self.transport.calls.count('launch'))
    def test_wrong_version_before_dispatch(self):
        self.transport.mode='wrong_version'
        with self.assertRaises(RDCError):self.execute()
        self.assertEqual(['preflight'],self.transport.calls)
    def test_invalid_command_refused_before_transport(self):
        for command in ('echo a\nnext','echo '+('é'*2001),'   '):
            with self.assertRaises(RDCError):self.execute(command)
        self.assertEqual([],self.transport.calls)
    def test_no_command_or_result_in_journal(self):
        self.execute()
        for f in Path(self.tmp.name).rglob('*.json'):
            self.assertNotIn('echo fixture',f.read_text())
            self.assertNotIn('"output"',f.read_text())
    def test_unknown_id_never_reads_arbitrary_container_path(self):
        with self.assertRaises(RDCError):self.worker.recover('one',str(uuid.uuid4()))
        self.assertEqual([],self.transport.calls)

    def test_verified_run_identity_cannot_change_on_recovery(self):
        self.execute()
        original_run=self.transport.receipt['run_id']
        self.transport.receipt['run_id']=str(uuid.uuid4())
        self.worker=DirectTerminal(self.settings,self.profiles,self.transport)
        with self.assertRaises(RDCError) as caught:
            self.worker.recover('one',self.ident)
        self.assertEqual('direct_terminal_recovery_required',caught.exception.code)
        self.transport.receipt['run_id']=original_run
        self.assertTrue(self.worker.recover('one',self.ident)['execution_verified'])
        self.assertEqual(1,self.transport.calls.count('launch'))
        self.assertEqual(1,self.transport.calls.count('copy'))

    def test_verified_output_cannot_change_after_restart(self):
        self.execute()
        journal=self.worker.root/(self.ident+'.json')
        original=journal.read_bytes()
        self.transport.receipt['output']='substituted'
        self.worker=DirectTerminal(self.settings,self.profiles,self.transport)
        with self.assertRaises(RDCError) as caught:
            self.worker.recover('one',self.ident)
        self.assertEqual('direct_terminal_recovery_required',caught.exception.code)
        self.assertEqual(original,journal.read_bytes())
        self.assertEqual(1,self.transport.calls.count('launch'))

    def test_matching_recovery_preserves_verified_journal(self):
        self.execute()
        journal=self.worker.root/(self.ident+'.json')
        before=journal.stat()
        self.transport.receipt=dict(reversed(list(self.transport.receipt.items())))
        result=self.worker.recover('one',self.ident)
        self.assertTrue(result['execution_verified'])
        self.assertEqual('fixture',result['output'])
        self.assertEqual((before.st_ino,before.st_mtime_ns),
                         (journal.stat().st_ino,journal.stat().st_mtime_ns))
        self.assertEqual(1,self.transport.calls.count('launch'))

    def test_legacy_verified_record_without_pin_fails_closed(self):
        import json
        self.execute()
        journal=self.worker.root/(self.ident+'.json')
        legacy=json.loads(journal.read_text())
        legacy.pop('receipt_sha256',None)
        journal.write_text(json.dumps(legacy))
        calls=list(self.transport.calls)
        self.worker=DirectTerminal(self.settings,self.profiles,self.transport)
        with self.assertRaises(RDCError) as caught:
            self.worker.recover('one',self.ident)
        self.assertEqual('direct_terminal_recovery_required',caught.exception.code)
        self.assertEqual(calls,self.transport.calls)

class DirectTerminalCatalogTests(unittest.TestCase):
    def setUp(self):
        from rdc.config import Settings
        from rdc.engine import Engine
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.settings=Settings(root/'state',[root],approval_mode='trusted',allow_exec=False,
            desktop_mode='disabled',browser_backend='disabled',mobile_profiles={'one':fixture_profile()},
            ios_direct_terminal_enabled=True)
        self.engine=Engine(self.settings)
        self.addCleanup(self.engine.close)
        self.mobile=self.engine.adapters.mobile
        self.transport=FakeTransport()
        self.args={'profile':'one','request_id':str(uuid.uuid4()),'command':'echo fixture'}
    def test_catalog_and_owner_review_in_trusted_mode(self):
        tools={row['name']:row for row in self.engine.catalog()}
        self.assertTrue(tools['rdc_mobile_ios_direct_terminal_execute']['x-rdc-mutating'])
        self.assertFalse(tools['rdc_mobile_ios_direct_terminal_recover']['x-rdc-mutating'])
        self.mobile._direct_terminal.transport=self.transport
        r=self.engine.call('rdc_mobile_ios_direct_terminal_execute',self.args)
        self.assertEqual('pending_approval',r['status'])
        self.assertEqual([],self.transport.calls)
    def test_owner_execute_and_exact_read_only_recovery(self):
        self.mobile._direct_terminal.transport=self.transport
        r=self.engine.owner_call('rdc_mobile_ios_direct_terminal_execute',self.args)
        self.assertTrue(r['ok']);self.assertTrue(r['execution_verified'])
        recover={k:self.args[k] for k in ('profile','request_id')}
        r=self.engine.call('rdc_mobile_ios_direct_terminal_recover',recover)
        self.assertTrue(r['ok']);self.assertTrue(r['execution_verified'])
        self.assertEqual(1,self.transport.calls.count('launch'))
    def test_active_native_session_blocks_direct_transport(self):
        self.mobile._direct_terminal.transport=self.transport
        self.mobile._sessions['fixture']={'session_id':'fixture','backend':'appium','kind':'mobile',
            'profile':'one','platform':'iOS','automation':'XCUITest','title':'fixture',
            'width':400,'height':800,'observation_id':None,'cursor':{'x':0,'y':0},
            'sensitive':False,'handles':{}}
        try:
            r=self.engine.owner_call('rdc_mobile_ios_direct_terminal_execute',self.args)
            self.assertEqual('developer_preflight_conflict',r['error']['code'])
            self.assertEqual([],self.transport.calls)
        finally:self.mobile._sessions.clear()
    def test_invalid_settings_type_refused(self):
        from rdc.config import Settings
        with self.assertRaises(RDCError):
            Settings(Path(self.tmp.name)/'other',[Path(self.tmp.name)],ios_direct_terminal_enabled='true')
    def test_generic_router_cannot_bypass_owner_review(self):
        self.mobile._direct_terminal.transport=self.transport
        r=self.engine.owner_call('rdc_mobile_command_execute',{'operation':'ios_direct_terminal_execute','arguments':self.args})
        self.assertFalse(r['ok']);self.assertEqual([],self.transport.calls)
