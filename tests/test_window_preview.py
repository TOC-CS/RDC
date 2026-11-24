import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from rdc.errors import RDCError


class WindowPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = SimpleNamespace(background_only=False, desktop_mode='shared', state_dir=Path(self.temp.name))
        self.calls = []
        self.rows = [{'window_id':42, 'pid':100, 'launch_id':'one', 'bundle_id':'org.example.app',
                      'title':'Mixer', 'width':900, 'height':600}]
        def backend(action, **args):
            self.calls.append((action,args))
            if action == 'list': return {'windows':self.rows}
            if action == 'capture': return {'width':900,'height':600,'mime_type':'image/jpeg','data':'/9j/'}
            if action == 'resize': return {'width':max(480,args['width']),'height':args['height']}
        self.backend = backend

    def tearDown(self): self.temp.cleanup()

    def windows(self):
        from rdc.windows import Windows
        return Windows(self.settings, backend=self.backend)

    def test_window_tools_are_present(self):
        from rdc.adapters import Adapters
        adapter = Adapters(SimpleNamespace(background_only=False, desktop_mode='shared',browser_backend='disabled',adb_serial=None,state_dir=Path(self.temp.name)))
        try:
            names={tool['name'] for tool in adapter.catalog()}
            self.assertIn('rdc_window_list',names)
            self.assertIn('rdc_window_open',names)
        finally: adapter.close()

    def test_binding_captures_only_discovered_window(self):
        w=self.windows(); target=w.list()['windows'][0]
        session=w.open(target['target_id'],resize_to_view=True)
        shot=w.snapshot(session['session_id'])
        self.assertEqual(shot['session_id'],session['session_id'])
        captures=[args for action,args in self.calls if action=='capture']
        self.assertEqual(captures[0]['window_id'],42)
        self.assertEqual(captures[0]['pid'],100)
        self.assertEqual(captures[0]['launch_id'],'one')

    def test_reused_window_id_is_never_captured(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'])
        self.rows[0]['launch_id']='different-process'
        with self.assertRaises(RDCError) as error: w.snapshot(session['session_id'])
        self.assertEqual(error.exception.code,'session_not_found')
        self.assertFalse(any(action=='capture' for action,_ in self.calls))

    def test_disappeared_window_cannot_reappear_in_same_session(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'])
        original=self.rows; self.rows=[]
        with self.assertRaises(RDCError): w.snapshot(session['session_id'])
        self.rows=original
        with self.assertRaises(RDCError): w.snapshot(session['session_id'])

    def test_resize_requires_explicit_session_authorization(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'])
        with self.assertRaises(RDCError) as error: w.resize(session['session_id'],320,700)
        self.assertEqual(error.exception.code,'resize_not_enabled')
        self.assertFalse(any(action=='resize' for action,_ in self.calls))

    def test_resize_reports_native_minimum(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'],resize_to_view=True)
        result=w.resize(session['session_id'],320,700)
        self.assertEqual((result['width'],result['height']),(480,700))
        self.assertTrue(result['size_constrained'])

    def test_local_resize_recovery_does_not_repeat_mutation(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'],resize_to_view=True)
        first=w.resize(session['session_id'],320,700,request_id='one-resize')
        second=w.resize(session['session_id'],320,700,request_id='one-resize')
        self.assertEqual(first,second)
        self.assertEqual(len([a for a,_ in self.calls if a=='resize']),1)
        with self.assertRaises(RDCError): w.resize(session['session_id'],400,700,request_id='one-resize')

    def test_uncertain_local_resize_is_never_replayed(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'],resize_to_view=True)
        original=self.backend
        def uncertain(action,**args):
            if action=='resize':
                self.calls.append((action,args))
                raise RDCError('window_capture_unavailable','Unknown result')
            return original(action,**args)
        w.backend=uncertain
        for _ in range(2):
            with self.assertRaises(RDCError): w.resize(session['session_id'],320,700,request_id='uncertain')
        self.assertEqual(len([a for a,_ in self.calls if a=='resize']),1)

    def test_close_only_forgets_preview_binding(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'])
        w.close(session['session_id'])
        self.assertEqual(w.status()['sessions'],[])
        self.assertFalse(any(action in ('close','terminate') for action,_ in self.calls))

    def test_disappearance_during_resize_permanently_ends_binding(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'],resize_to_view=True)
        original=self.backend
        def gone(action,**args):
            if action=='resize': raise RDCError('session_not_found','Window ended')
            return original(action,**args)
        w.backend=gone
        with self.assertRaises(RDCError): w.resize(session['session_id'],320,700)
        w.backend=original
        self.assertEqual(w.status()['sessions'],[])
        with self.assertRaises(RDCError): w.snapshot(session['session_id'])

    def test_permission_refusal_can_recover_without_replaying_uncertain_action(self):
        w=self.windows(); session=w.open(w.list()['windows'][0]['target_id'],resize_to_view=True)
        original=self.backend
        def denied(action,**args):
            if action=='resize': raise RDCError('accessibility_permission_required','No permission')
            return original(action,**args)
        w.backend=denied
        with self.assertRaises(RDCError): w.resize(session['session_id'],320,700,request_id='permission-test')
        w.backend=original
        self.assertEqual(w.resize(session['session_id'],320,700,request_id='permission-test')['height'],700)

    def test_owner_reviewed_binding_authorizes_resize_but_pause_still_blocks(self):
        from rdc.config import Settings
        from rdc.engine import Engine
        engine=Engine(Settings(state_dir=Path(self.temp.name)/'review-state',roots=[Path(self.temp.name)],desktop_mode='shared',approval_mode='review',background_only=False))
        engine.adapters.windows.backend=self.backend
        try:
            target=engine.call('rdc_window_list')['windows'][0]['target_id']
            queued=engine.call('rdc_window_open',{'target_id':target,'resize_to_view':True})
            self.assertEqual(queued['status'],'pending_approval')
            opened=engine.decide(queued['request_id'],True)
            args={'session_id':opened['session_id'],'width':320,'height':700}
            resized=engine.call('rdc_preview_resize',args)
            self.assertTrue(resized['ok'])
            self.assertNotIn('status',resized)
            self.assertEqual(resized['height'],700)
            engine.pause(True)
            self.assertEqual(engine.call('rdc_preview_resize',args)['error']['code'],'paused')
            engine.pause(False)
            engine.adapters.windows.close(opened['session_id'])
            self.assertFalse(engine.call('rdc_preview_resize',args)['ok'])
            opened=engine.owner_call('rdc_window_open',{'target_id':target,'resize_to_view':False})
            args['session_id']=opened['session_id']
            self.assertEqual(engine.call('rdc_preview_resize',args)['error']['code'],'resize_not_enabled')
        finally: engine.close()

    def test_disabled_desktop_does_not_enumerate_windows(self):
        self.settings.desktop_mode='disabled'; w=self.windows()
        with self.assertRaises(RDCError): w.list()
        self.assertEqual(self.calls,[])

    def test_embedded_preview_refuses_whole_desktop(self):
        from rdc.config import Settings
        from rdc.engine import Engine
        engine=Engine(Settings(state_dir=Path(self.temp.name)/'state',roots=[Path(self.temp.name)],desktop_mode='shared'))
        try:
            for name in ('rdc_preview_open','rdc_preview_frame'):
                result=engine.call(name,{'session_id':'desktop'})
                self.assertFalse(result['ok'])
                self.assertEqual(result['error']['code'],'window_required')
        finally: engine.close()
