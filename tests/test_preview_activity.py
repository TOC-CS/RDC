"""Actual Engine work, persisted job output and nonblocking preview observations."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from rdc.adapters import Adapters, _Browsers
from rdc.config import Settings
from rdc.engine import Engine
from rdc.errors import RDCError

SID = '12345678-1234-1234-1234-123456789abc'
SID2 = '22345678-1234-1234-1234-123456789abc'
MOBILE = 'mobile-32345678-1234-1234-1234-123456789abc'


class SessionAdapters:
    """Only remote-driver I/O is replaced; Engine admission and tracking stay real."""
    def __init__(self):
        self.sessions = [{'session_id': SID, 'browser': 'chromium', 'width': 800, 'height': 600},
                         {'session_id': SID2, 'browser': 'chromium', 'width': 800, 'height': 600}]
        self.mobile = [{'session_id': MOBILE, 'platform': 'Android', 'width': 400, 'height': 800}]
        self.calls = []
        self.failure = False
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block = False

    def status(self):
        raise AssertionError('Activity must use the nonblocking session snapshot')

    def activity_status(self):
        return {'browser': {'sessions': self.sessions, 'busy': self.block, 'status_stale': self.block, 'updated_at': 12},
                'mobile': {'sessions': self.mobile, 'busy': False, 'status_stale': False, 'updated_at': 13}}

    def call(self, name, args):
        self.calls.append(name)
        if self.block:
            self.entered.set()
            if not self.release.wait(3):
                raise AssertionError('Fixture release deadline exceeded')
        if self.failure:
            raise RDCError('fixture_failure', 'PRIVATE DRIVER ERROR')
        if name.endswith('_list'):
            return {'sessions': self.sessions}
        if name == 'rdc_browser_start':
            return dict(self.sessions[-1])
        if name.endswith('_close'):
            self.sessions[:] = [row for row in self.sessions if row['session_id'] != args['session_id']]
            self.mobile[:] = [row for row in self.mobile if row['session_id'] != args['session_id']]
            return {'session_id': args['session_id'], 'closed': True}
        return {'session_id': args['session_id']}

    def snapshot(self, session_id):
        self.calls.append('snapshot')
        return {'session_id': session_id, 'mime_type': 'image/png', 'data': base64.b64encode(b'png').decode(),
                'width': 800, 'height': 600}

    def close(self):
        self.release.set()


class PreviewActivityContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = Engine(Settings(state_dir=self.root/'state', roots=[self.root],
                                      browser_backend='disabled', approval_mode='trusted', allow_exec=True))

    def tearDown(self):
        self.engine.close()
        self.tmp.cleanup()

    def call(self, name, args=None):
        result = self.engine.call(name, args or {})
        self.assertTrue(result['ok'], result)
        return result

    def sessions(self):
        self.engine.adapters.close()
        adapter = SessionAdapters()
        self.engine.adapters = adapter
        return adapter

    def activity(self, **args):
        return self.call('rdc_preview_activity', args)

    def test_explicit_job_bound_floating_preview_auto_clears_only_for_confirmed_terminal_job(self):
        adapter = self.sessions()
        selected_job = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        state = {'status':'running'}
        def snapshot(job_id):
            self.assertEqual(job_id, selected_job)
            return {'job':{'id':job_id,'status':state['status'],'spec':'PRIVATE CMD',
                           'cwd':'PRIVATE PATH','error':'PRIVATE ERROR'}}
        with patch.object(self.engine.jobs, 'status', side_effect=snapshot):
            opened = self.call('rdc_preview_open', {'session_id':SID,'job_id':selected_job})
            self.assertEqual(opened['viewer']['task_job_id'], selected_job)
            self.assertFalse(opened['viewer']['task_complete'])
            self.assertNotIn('PRIVATE', json.dumps(opened))
            running = self.call('rdc_preview_frame', {'session_id':SID,'job_id':selected_job})
            self.assertEqual(running['task'], {'job_id':selected_job,'status':'running','complete':False})
            self.assertIn('data', running)
            state['status']='completed'
            finished = self.call('rdc_preview_frame', {'session_id':SID,'job_id':selected_job})
            self.assertEqual(finished['task'], {'job_id':selected_job,'status':'completed','complete':True})
            self.assertNotIn('data', finished, 'Completed job must not require another image capture')
            self.assertEqual(adapter.calls.count('snapshot'), 1)
            state['status']='interrupted'
            uncertain = self.call('rdc_preview_frame', {'session_id':SID,'job_id':selected_job})
            self.assertFalse(uncertain['task']['complete'], 'Uncertain interrupted work must retain the viewer')
            self.assertIn('data', uncertain)
        unbound = self.engine.call('rdc_preview_open', {'job_id':selected_job})
        self.assertFalse(unbound['ok'], 'Job-linked preview must require an exact visual source')
        invalid = self.engine.call('rdc_preview_frame', {'session_id':SID,'job_id':'not-an-id'})
        self.assertFalse(invalid['ok'])

    def test_activity_catalog_is_read_only_app_only_and_has_no_resource_launch(self):
        tool = {item['name']: item for item in self.engine.catalog()}.get('rdc_preview_activity')
        self.assertIsNotNone(tool)
        self.assertFalse(tool['x-rdc-mutating'])
        self.assertTrue(tool['annotations']['readOnlyHint'])
        self.assertEqual(tool['_meta']['ui'], {'visibility': ['app']})
        self.assertNotIn('resourceUri', tool['_meta']['ui'])

    def test_actual_file_work_is_recorded_without_arguments_paths_contents_or_raw_errors(self):
        path = self.root/'PRIVATE-FILE-NAME'
        self.call('rdc_file_write', {'file_path': str(path), 'content': 'PRIVATE-CONTENT'})
        self.assertFalse(self.engine.call('rdc_file_read', {'file_path': str(self.root/'PRIVATE-MISSING')})['ok'])
        data = self.activity()
        self.assertEqual([row['tool'] for row in data['recent_operations']], ['rdc_file_read', 'rdc_file_write'])
        self.assertEqual([row['status'] for row in data['recent_operations']], ['failed', 'completed'])
        for private in ('PRIVATE-FILE', 'PRIVATE-CONTENT', 'PRIVATE-MISSING', str(self.root)):
            self.assertNotIn(private, json.dumps(data))
        before = list(data['recent_operations'])
        self.activity()
        self.assertEqual(self.activity()['recent_operations'], before)

    def test_invalid_arguments_and_approval_queue_are_not_reported_as_executing(self):
        self.assertFalse(self.engine.call('rdc_file_write', {'file_path': 'PRIVATE'})['ok'])
        self.engine.settings.approval_mode = 'review'
        queued = self.call('rdc_file_write', {'file_path': str(self.root/'queued'), 'content': 'PRIVATE'})
        self.assertEqual(queued['status'], 'pending_approval')
        data = self.activity()
        self.assertEqual(data['current_operations'], [])
        self.assertEqual(data['recent_operations'], [])
        self.assertEqual(data['pending_approvals'], 1)
        self.assertFalse((self.root/'queued').exists())
        self.engine.decide(queued['request_id'], True)
        self.assertEqual(self.activity()['recent_operations'][0]['tool'], 'rdc_file_write')

    def test_stale_session_observation_cannot_delete_focus_from_a_later_successful_start(self):
        calls = []
        def driver(worker, action, args):
            self.assertEqual(action, 'start')
            session_id = SID if not worker.sessions else SID2
            calls.append(session_id)
            worker.sessions[session_id] = {'session_id':session_id,'backend':'fixture','browser':'chromium',
                'url':'about:blank','width':800,'height':600,'observation_id':None,'cursor':{'x':0,'y':0}}
            return worker.info(worker.sessions[session_id])
        with patch.object(_Browsers, 'call', driver):
            self.call('rdc_browser_start')
            first = self.activity()['focus']
            original_sessions = self.engine._preview_sessions
            def older_sessions_with_concurrent_start():
                older = original_sessions()
                self.call('rdc_browser_start')
                return older
            # Deterministically interleave a real admitted Engine start after
            # session capture, before this earlier activity request reads focus.
            with patch.object(self.engine, '_preview_sessions', side_effect=older_sessions_with_concurrent_start):
                older = self.activity()
            self.assertEqual([row['session_id'] for row in older['sessions']], [SID])
            self.assertEqual(older['focus']['session_id'], SID)
            fresh = self.activity()['focus']
            self.assertEqual(fresh['session_id'], SID2)
            self.assertGreater(fresh['sequence'], first['sequence'])
            self.assertIsNone(self.call('rdc_preview_open')['session_id'])
            self.assertEqual(calls, [SID, SID2])

    def test_successful_browser_and_mobile_work_change_focus_but_failed_actions_and_observers_do_not(self):
        adapter = self.sessions()
        self.call('rdc_browser_navigate', {'session_id': SID2, 'url': 'https://private.invalid/path'})
        first = self.activity()['focus']
        self.assertEqual(first['session_id'], SID2)
        self.assertIsNone(self.call('rdc_preview_open')['session_id'])
        self.call('rdc_preview_frame', {'session_id': SID})
        self.call('rdc_browser_list')
        self.assertEqual(self.activity()['focus'], first)
        adapter.failure = True
        self.assertFalse(self.engine.call('rdc_browser_navigate', {'session_id': SID, 'url': 'https://private.invalid/'})['ok'])
        self.assertEqual(self.activity()['focus'], first)
        self.assertNotIn('PRIVATE DRIVER ERROR', json.dumps(self.activity()))
        adapter.failure = False
        self.call('rdc_mobile_observe', {'session_id': MOBILE})
        mobile = self.activity()['focus']
        self.assertEqual(mobile['session_id'], MOBILE)
        self.assertGreater(mobile['sequence'], first['sequence'])
        self.call('rdc_mobile_close', {'session_id': MOBILE})
        self.assertEqual(self.activity()['focus']['session_id'], SID2)
        self.assertEqual(self.call('rdc_preview_open', {'session_id': SID})['session_id'], SID)
        self.assertEqual(self.activity()['focus']['session_id'], SID2)

    def test_in_progress_target_is_visible_and_activity_polling_never_replays_actions(self):
        adapter = self.sessions()
        adapter.block = True
        with ThreadPoolExecutor(max_workers=1) as pool:
            work = pool.submit(self.engine.call, 'rdc_browser_navigate', {'session_id': SID2, 'url': 'https://private.invalid/'})
            try:
                self.assertTrue(adapter.entered.wait(1))
                data = self.activity()
                self.assertEqual(data['current_operations'][0]['session_id'], SID2)
                self.assertEqual(data['current_operations'][0]['tool'], 'rdc_browser_navigate')
                self.assertIsNone(data['focus'])
                self.assertTrue(data['session_status']['busy'])
                for _ in range(3):
                    self.activity()
                self.assertEqual(adapter.calls, ['rdc_browser_navigate'])
            finally:
                adapter.release.set()
            self.assertTrue(work.result(timeout=2)['ok'])
        self.assertEqual(self.activity()['current_operations'], [])
        self.assertEqual(self.activity()['focus']['session_id'], SID2)

    def test_real_durable_job_state_and_selected_bounded_output_tail(self):
        marker = 'ACTUAL-JOB-MARKER'
        # Use a real detached worker and real log. No command is repeated by polling.
        script = "import sys,time; print('ACTUAL-JOB-MARKER',flush=True); print('x'*12000,flush=True); time.sleep(.35)"
        started = self.call('rdc_job_start', {'argv': [sys.executable, '-c', script, 'PRIVATE-ARGV'],
                                             'cwd': str(self.root), 'idempotency_key': 'PRIVATE-KEY'})
        job_id = started['job']['id']
        deadline = time.monotonic()+8
        observed_active = False
        while time.monotonic() < deadline:
            data = self.activity(job_id=job_id)
            job = next(row for row in data['jobs'] if row['job_id'] == job_id)
            observed_active |= job['status'] in ('queued', 'running')
            if job['status'] not in ('queued', 'running', 'cancelling'):
                break
            time.sleep(.025)
        self.assertTrue(observed_active)
        self.assertEqual(job['status'], 'completed')
        tail = data['job_output']
        self.assertEqual(tail['bytes_available'], len((marker+os.linesep+'x'*12000+os.linesep).encode()))
        self.assertEqual(tail['next_offset']-tail['offset'], 8192)
        self.assertEqual(len(tail['text'].encode()), 8192)
        self.assertTrue(tail['complete'])
        self.assertTrue(tail['truncated'])
        self.assertEqual(tail['text'], ('x'*12000+os.linesep)[-8192:])
        self.assertNotIn('job_output', self.activity())
        for name,args in [('rdc_job_status',{'job_id':job_id}),('rdc_job_output',{'job_id':job_id}),('rdc_job_list',{})]:
            self.call(name,args)
        self.assertEqual([row['tool'] for row in self.activity()['recent_operations']], ['rdc_job_start'])
        encoded = json.dumps(data)
        for private in ('PRIVATE-ARGV', 'PRIVATE-KEY', script, str(self.root)):
            self.assertNotIn(private, encoded)
        self.assertEqual(len(self.engine.jobs.list()['jobs']), 1)
        self.assertEqual([row['tool'] for row in data['recent_operations']], ['rdc_job_start'])

    def test_status_and_list_observers_do_not_become_activity_events(self):
        self.call('rdc_file_list', {'path':str(self.root)})
        self.call('rdc_job_list')
        self.call('rdc_browser_list')
        self.call('rdc_mobile_list')
        self.call('rdc_system_status')
        self.assertEqual(self.activity()['recent_operations'], [])

    def test_unknown_session_argument_is_never_copied_into_activity_metadata(self):
        result = self.engine.call('rdc_browser_navigate', {'session_id':'PRIVATE-RAW-ARGUMENT', 'url':'https://example.invalid/'})
        self.assertFalse(result['ok'])
        data = self.activity()
        self.assertEqual(data['recent_operations'][0]['status'], 'failed')
        self.assertNotIn('PRIVATE-RAW-ARGUMENT', json.dumps(data))

    def test_concurrent_current_records_are_bounded_and_recover_after_completion(self):
        path = self.root/'actual-file'
        path.write_text('actual data')
        release = threading.Event()
        entered = threading.Condition()
        count = 0
        original_read = self.engine.files.read
        def held_read(**args):
            nonlocal count
            with entered:
                count += 1
                entered.notify_all()
            if not release.wait(4):
                raise AssertionError('Fixture release deadline exceeded')
            return original_read(**args)
        with patch.object(self.engine.files, 'read', side_effect=held_read), ThreadPoolExecutor(max_workers=34) as pool:
            futures = [pool.submit(self.engine.call, 'rdc_file_read', {'file_path':str(path)}) for _ in range(34)]
            try:
                with entered:
                    self.assertTrue(entered.wait_for(lambda: count==34, timeout=3))
                data = self.activity()
                self.assertEqual(len(data['current_operations']), 32)
                self.assertTrue(data['current_operations_truncated'])
                self.assertEqual(len({row['activity_id'] for row in data['current_operations']}), 32)
            finally:
                release.set()
            self.assertTrue(all(future.result(timeout=2)['ok'] for future in futures))
        data = self.activity()
        self.assertEqual(data['current_operations'], [])
        self.assertFalse(data['current_operations_truncated'])
        self.assertEqual(len(data['recent_operations']), 20)

    def test_recent_operations_and_job_summaries_are_bounded_with_truthful_counts(self):
        path = self.root/'file'
        for index in range(24):
            self.call('rdc_file_write', {'file_path': str(self.root/f'file-{index}'), 'content': 'x'})
        # Stored job rows are the real source; no runner or log is fabricated.
        with self.engine.store.connection() as db:
            for index in range(12):
                db.execute('INSERT INTO jobs(id,fingerprint,spec,status,created_at,heartbeat) VALUES (?,?,?,?,?,?)',
                           (f'00000000-0000-4000-8000-{index:012d}', 'x', json.dumps({'argv':['PRIVATE'],'cwd':'PRIVATE','timeout':1}),
                            'running' if index < 3 else 'completed', time.time()+index, time.time()))
        data = self.activity()
        self.assertEqual(len(data['recent_operations']), 20)
        self.assertEqual(len(data['jobs']), 10)
        self.assertTrue(data['jobs_truncated'])
        self.assertEqual(data['active_jobs'], 3)
        self.assertEqual(sum(row['status']=='running' for row in data['jobs']), 3)
        self.assertNotIn('PRIVATE', json.dumps(data))

    def test_selected_output_refuses_symlinks_instead_of_exposing_another_file(self):
        job_id = '00000000-0000-4000-8000-000000000010'
        with self.engine.store.connection() as db:
            db.execute('INSERT INTO jobs(id,fingerprint,spec,status,created_at) VALUES (?,?,?,?,?)',
                       (job_id, 'x', '{}', 'completed', time.time()))
        private = self.root/'private'
        private.write_text('PRIVATE-SECRET')
        try:
            (self.engine.jobs.directory/f'{job_id}.output').symlink_to(private)
        except OSError:
            self.skipTest('Symlinks unavailable')
        result = self.engine.call('rdc_preview_activity', {'job_id': job_id})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'output_unavailable')
        self.assertNotIn('PRIVATE-SECRET', json.dumps(result))

    def test_native_targets_require_existing_configuration_and_never_capture_idle_host(self):
        self.assertEqual(self.activity()['sessions'], [])
        self.engine.settings.desktop_mode = 'shared'
        self.engine.settings.adb_serial = 'PRIVATE-SERIAL'
        with patch.object(self.engine.adapters, '_desktop', side_effect=AssertionError('Idle desktop capture')), \
             patch.object(self.engine.adapters, '_android', side_effect=AssertionError('Idle ADB capture')):
            data = self.activity()
            self.assertEqual([(row['session_id'],row['kind']) for row in data['sessions']], [('desktop','desktop'),('android-adb','adb')])
            self.assertIsNone(self.call('rdc_preview_open')['session_id'])
            self.assertIsNone(data['focus'])
            self.assertNotIn('PRIVATE-SERIAL', json.dumps(data))

    def test_native_real_action_focus_and_explicit_frame_use_existing_guarded_adapters(self):
        self.engine.settings.desktop_mode = 'shared'
        self.engine.settings.adb_serial = 'PRIVATE-SERIAL'
        shot = {'mime_type':'image/png','data':base64.b64encode(b'png').decode(),'width':400,'height':300}
        calls = []
        def desktop(action, args):
            calls.append(('desktop',action))
            return shot if action=='screenshot' else {'performed':action}
        def android(action, args):
            calls.append(('adb',action))
            if action=='screenshot':
                raise RDCError('screenshot_redaction_required','Private native screen')
            return {'performed':action}
        with patch.object(self.engine.adapters, '_desktop', side_effect=desktop), \
             patch.object(self.engine.adapters, '_android', side_effect=android):
            queued = self.call('rdc_desktop_keys', {'keys':'Tab'})
            self.assertEqual(queued['status'], 'pending_approval')
            self.assertEqual(calls, [])
            self.assertTrue(self.engine.decide(queued['request_id'], True)['ok'])
            self.assertIsNone(self.call('rdc_preview_open')['session_id'])
            self.assertEqual(self.engine.call('rdc_preview_open', {'session_id':'desktop'})['error']['code'],'window_required')
            self.assertEqual(self.engine.call('rdc_preview_frame', {'session_id':'desktop'})['error']['code'],'window_required')
            frame = self.call('rdc_desktop_screenshot')
            self.assertEqual((frame['width'],frame['height']), (400,300))
            self.call('rdc_android_tap', {'x':1,'y':2})
            self.assertEqual(self.activity()['focus']['session_id'], 'android-adb')
            failed = self.engine.call('rdc_preview_frame', {'session_id':'android-adb'})
            self.assertFalse(failed['ok'])
            self.assertEqual(failed['error']['code'], 'screenshot_redaction_required')
        self.assertEqual(calls, [('desktop','keys'),('desktop','screenshot'),('adb','tap'),('adb','screenshot')])
        self.engine.settings.desktop_mode='disabled'
        self.assertFalse(self.engine.call('rdc_preview_open', {'session_id':'desktop'})['ok'])


class NonblockingAdapterActivity(unittest.TestCase):
    def test_cached_browser_sessions_remain_available_while_owner_thread_is_busy(self):
        settings = Settings(state_dir=Path('/unused'), roots=[Path.cwd()], browser_backend='disabled')
        adapter = Adapters(settings)
        self.addCleanup(adapter.close)
        self.assertTrue(callable(getattr(adapter, 'activity_status', None)), 'Nonblocking activity snapshot is missing')
        entered,release = threading.Event(),threading.Event()
        calls = []
        def driver(worker, action, args):
            calls.append(action)
            if action=='start':
                worker.sessions[SID] = {'session_id':SID,'backend':'fixture','browser':'chromium','url':'about:blank',
                    'width':800,'height':600,'observation_id':None,'cursor':{'x':0,'y':0}}
                return worker.info(worker.sessions[SID])
            entered.set()
            if not release.wait(3):
                raise AssertionError('Fixture release deadline exceeded')
            return worker.info(worker.sessions[SID])
        try:
            with patch.object(_Browsers, 'call', driver), ThreadPoolExecutor(max_workers=2) as pool:
                adapter.call('rdc_browser_start', {})
                work = pool.submit(adapter.call,'rdc_browser_navigate',{'session_id':SID,'url':'https://example.invalid/'})
                self.assertTrue(entered.wait(1))
                read = pool.submit(adapter.activity_status)
                try:
                    data = read.result(timeout=.4)
                    self.assertTrue(data['browser']['busy'])
                    self.assertTrue(data['browser']['status_stale'])
                    self.assertEqual(data['browser']['sessions'][0]['session_id'], SID)
                    data['browser']['sessions'].clear()
                    self.assertEqual(len(adapter.activity_status()['browser']['sessions']), 1)
                    self.assertEqual(calls, ['start','navigate'])
                finally:
                    release.set()
                work.result(timeout=2)
                self.assertFalse(adapter.activity_status()['browser']['busy'])
        finally:
            release.set()
            adapter.close()


if __name__ == '__main__':
    unittest.main()
