"""Bounded host journal coverage for the private warm USB terminal candidate."""
import asyncio
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rdc.errors import RDCError
from rdc.ios_direct_terminal import DirectTerminal, COMPANION
from rdc.ios_warm_terminal import WarmDirectTerminal, WarmSessionTransport, WARM_COMPANION
from tests.test_ios_direct_terminal import FakeTransport, fixture_profile

SESSION='11111111-1111-4111-8111-111111111111'
REQUEST='22222222-2222-4222-8222-222222222222'
OTHER='33333333-3333-4333-8333-333333333333'
RUN='44444444-4444-4444-8444-444444444444'

class FakeUSB:
    def __init__(self, expiry):
        self.expiry=expiry; self.calls=[]; self.request=None; self.fail=False
        self.binding=('fixture-device-01',SESSION,expiry)
    async def open(self):
        self.calls.append('open')
        return {'session_id':SESSION,'expires_at_ms':self.expiry,'next_sequence':1,
                'bundle_id':WARM_COMPANION,'status':'ready','schema':1}
    async def submit(self, request, *, before_mutation):
        await before_mutation(request.identity)
        self.calls.append('write')
        self.request=request
        if self.fail: raise OSError('unknown')
    async def read(self, identity):
        self.calls.append('read')
        return {'schema':1,'request_id':identity.request_id,'run_id':RUN,
            'command_sha256':identity.command_sha256,'exit_code':0,'device_elapsed_ms':1,
            'output':'fixture','execution_location':'mobile_device',
            'session_id':identity.session_id,'sequence':identity.sequence,
            'request_sha256':identity.request_sha256}
    async def close(self): self.calls.append('close')

class WarmHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.settings=SimpleNamespace(state_dir=Path(self.tmp.name),
             ios_direct_terminal_enabled=True,ios_warm_terminal_enabled=True)
        self.profiles={'cold':fixture_profile(),'warm':fixture_profile(bundle=WARM_COMPANION)}
    def warm(self, transport=None):
        return WarmDirectTerminal(self.settings,self.profiles,transport or FakeTransport())
    def test_warm_requires_independent_opt_in(self):
        self.settings.ios_warm_terminal_enabled=False
        fake=FakeTransport();worker=self.warm(fake)
        with self.assertRaises(RDCError):worker.execute('warm',REQUEST,'echo fixture')
        self.assertEqual([],fake.calls)
    def test_exact_warm_target_keeps_cold_bundle_separate(self):
        fake=FakeTransport();worker=self.warm(fake)
        with self.assertRaises(RDCError):worker.execute('cold',REQUEST,'echo fixture')
        self.assertEqual([],fake.calls)
        result=worker.execute('warm',REQUEST,'echo fixture')
        self.assertTrue(result['execution_verified'])
        self.assertEqual('mobile_sandbox_warm_usb',result['command_route'])
    def test_unknown_warm_command_fences_cold_on_same_device(self):
        warm=FakeTransport();warm.mode='copy_unknown'
        self.assertFalse(self.warm(warm).execute('warm',REQUEST,'echo fixture')['execution_verified'])
        cold=FakeTransport()
        with self.assertRaises(RDCError) as caught:
            DirectTerminal(self.settings,self.profiles,cold).execute('cold',OTHER,'echo next')
        self.assertEqual('direct_terminal_unknown',caught.exception.code)
        self.assertEqual([],cold.calls)
    def test_unknown_cold_command_fences_warm_on_same_device(self):
        cold=FakeTransport();cold.mode='copy_unknown'
        DirectTerminal(self.settings,self.profiles,cold).execute('cold',REQUEST,'echo fixture')
        warm=FakeTransport()
        with self.assertRaises(RDCError) as caught:self.warm(warm).execute('warm',OTHER,'echo next')
        self.assertEqual('direct_terminal_unknown',caught.exception.code)
        self.assertEqual([],warm.calls)
    def test_recovery_preserves_receipt_pin_without_resubmit(self):
        fake=FakeTransport();worker=self.warm(fake)
        worker.execute('warm',REQUEST,'echo fixture')
        self.assertTrue(self.warm(fake).recover('warm',REQUEST)['execution_verified'])
        fake.receipt['output']='replacement'
        with self.assertRaises(RDCError):self.warm(fake).recover('warm',REQUEST)
        self.assertEqual(1,fake.calls.count('copy'))
    def transport(self, *, fresh=True):
        expiry=int(time.time()*1000)+60000
        usb=FakeUSB(expiry)
        transport=WarmSessionTransport(self.settings.state_dir, 'fixture-device-01',
            SESSION,b'B'*32,expiry,usb,fresh_session=fresh)
        self.addCleanup(transport.close)
        return transport,usb
    def test_one_open_multiple_commands_and_durable_mapping_before_write(self):
        transport,usb=self.transport();transport.open()
        worker=self.warm(transport)
        self.assertTrue(worker.execute('warm',REQUEST,'echo fixture')['execution_verified'])
        self.assertTrue(worker.execute('warm',OTHER,'echo next')['execution_verified'])
        self.assertEqual(['open','write','read','write','read'],usb.calls)
        paths=list((self.settings.state_dir/'warm-terminal-v1').glob('request-*.json'))
        self.assertEqual(2,len(paths))
        for path in paths:
            raw=path.read_text()
            self.assertNotIn('echo ',raw);self.assertNotIn('secret',raw)
            self.assertEqual(0,path.stat().st_mode & 0o077)
        self.assertEqual([1,2],sorted(json.loads(x.read_text())['sequence'] for x in paths))
    def test_mapping_failure_never_writes_and_fresh_session_cannot_restart(self):
        transport,usb=self.transport();transport.open()
        with patch.object(transport,'_publish_mapping',side_effect=OSError('disk unavailable')):
            result=self.warm(transport).execute('warm',REQUEST,'echo fixture')
        self.assertFalse(result['execution_verified']);self.assertNotIn('write',usb.calls)
        another,other_usb=self.transport()
        with self.assertRaises(OSError):another.open()
        self.assertEqual([],other_usb.calls)
    def test_explicit_recovery_attachment_reads_without_enabling_new_input(self):
        transport,usb=self.transport();transport.open();usb.fail=True
        self.assertFalse(self.warm(transport).execute('warm',REQUEST,'echo fixture')['execution_verified'])
        transport.close()
        recovery,reader=self.transport(fresh=False);recovery.open()
        self.assertFalse(recovery.preflight('fixture-device-01'))
        result=self.warm(recovery).recover('warm',REQUEST)
        self.assertTrue(result['execution_verified'])
        self.assertEqual(['open','read'],reader.calls)
    def test_bad_open_is_closed_and_wrong_async_context_is_rejected(self):
        transport,usb=self.transport()
        async def wrong_ready():
            usb.calls.append('open')
            return {'session_id':OTHER}
        usb.open=wrong_ready
        with self.assertRaises(OSError):transport.open()
        self.assertEqual(['open','close'],usb.calls)
        async def cannot_construct():
            with self.assertRaises(OSError):
                self.transport()
        asyncio.run(cannot_construct())
        bad=FakeUSB(int(time.time()*1000)+60000)
        bad.binding=('different-device',SESSION,bad.expiry)
        with self.assertRaises(ValueError):
            WarmSessionTransport(self.settings.state_dir,'fixture-device-01',
                SESSION,b'B'*32,bad.expiry,bad,fresh_session=True)
        self.assertEqual([],bad.calls)
