import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient
from rdc.cli import parser, main
from rdc.config import Settings
from rdc.server import create_app
from tests.test_transport import FixtureEngine

class HeadlessWorkerTests(unittest.TestCase):
    def test_01_root_and_legacy_assets_have_no_admin_ui(self):
        engine=FixtureEngine()
        with TestClient(create_app(engine,'fixture-agent','fixture-owner'),base_url='http://127.0.0.1') as client:
            for path in ('/','/index.html','/app.js','/styles.css'):
                result=client.get(path)
                self.assertEqual(404,result.status_code,path)
            self.assertEqual(401,client.get('/api/status').status_code)
            self.assertEqual(403,client.get('/api/status',headers={'Authorization':'Bearer fixture-agent'}).status_code)
            self.assertEqual(200,client.get('/api/status',headers={'Authorization':'Bearer fixture-owner'}).status_code)

    def test_02_new_scoped_initialization_automates_routine_operations(self):
        args=parser().parse_args(['init'])
        self.assertEqual('trusted',args.approval_mode)
        self.assertEqual('workspace',args.access_mode)
        self.assertFalse(args.allow_exec)
        self.assertEqual('disabled',args.desktop_mode)

    def test_03_legacy_review_configuration_is_not_silently_upgraded(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            s=Settings(p/'state',[p])
            self.assertEqual('review',s.approval_mode)
            self.assertEqual('review',parser().parse_args(['init','--approval-mode','review']).approval_mode)

    def test_04_legacy_open_flag_cannot_open_a_browser(self):
        args=parser().parse_args(['serve','--open'])
        self.assertFalse(hasattr(args,'open'))
        self.assertTrue(args.legacy_open)

    def test_05_owner_operations_use_local_transport_and_private_token(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root); (p/'owner-token').write_text('x'*48);(p/'owner-token').chmod(0o600)
            with patch('rdc.owner_api.request',return_value={'ok':True}) as call:
                self.assertEqual(0,main(['owner','status','--state-dir',str(p),'--port','9876']))
                call.assert_called_once_with('status',port=9876,token='x'*48,body=None)

    def test_06_owner_mutations_are_not_agent_tool_operations(self):
        engine=FixtureEngine()
        with TestClient(create_app(engine,'fixture-agent','fixture-owner'),base_url='http://127.0.0.1') as client:
            result=client.post('/api/decision',headers={'Authorization':'Bearer fixture-agent'},json={'request_id':'fixture','approve':True})
            self.assertEqual(403,result.status_code)
            result=client.post('/api/decision',headers={'Authorization':'Bearer fixture-owner'},json={'request_id':'fixture','approve':True})
            self.assertEqual(200,result.status_code)

    def test_07_no_dashboard_packaged(self):
        root=Path(__file__).resolve().parents[1]
        self.assertFalse((root/'rdc/web').exists())
        self.assertNotIn('"web/*"',(root/'pyproject.toml').read_text())

    def test_08_hosted_entry_has_no_live_session_list_or_polling(self):
        root=Path(__file__).resolve().parents[1]
        page=(root/'cloud-gateway/app/page.tsx').read_text()
        self.assertNotIn('setInterval',page)
        self.assertNotIn('/api/status',page)
        self.assertNotIn('device_id',page)


    def test_09_trusted_worker_enforces_scope_and_automates_allowed_write(self):
        from rdc.engine import Engine
        with tempfile.TemporaryDirectory() as root:
            p=Path(root); workspace=p/'work'; workspace.mkdir()
            engine=Engine(Settings(p/'state',[workspace],approval_mode='trusted',browser_backend='disabled'))
            try:
                response=engine.call('rdc_file_write',{'file_path':str(workspace/'fixture.txt'),'content':'automatic'})
                self.assertTrue(response['ok'],response)
                self.assertEqual('automatic',(workspace/'fixture.txt').read_text())
                denied=engine.call('rdc_file_write',{'file_path':str(p/'outside.txt'),'content':'denied'})
                self.assertFalse(denied['ok'])
                self.assertFalse((p/'outside.txt').exists())
            finally:
                engine.close()

    def test_10_owner_http_has_no_redirect_or_mutation_retry(self):
        from rdc.owner_api import request
        with patch('rdc.owner_api.http.client.HTTPConnection') as ctor:
            conn=ctor.return_value
            conn.getresponse.return_value.status=302
            conn.getresponse.return_value.read.return_value=b'{}'
            with self.assertRaises(ValueError):
                request('decision',port=8765,token='fixture',body={'request_id':'x','approve':False})
            ctor.assert_called_once_with('127.0.0.1',8765,timeout=60)
            conn.request.assert_called_once()
            conn.close.assert_called_once()

    def test_11_invalid_owner_input_never_dispatches(self):
        from io import StringIO
        from rdc.owner_api import request,read_body
        with patch('rdc.owner_api.http.client.HTTPConnection') as ctor:
            with self.assertRaises(ValueError):
                read_body('decision',StringIO('{"request_id":"x","approve":false,"extra":true}'))
            with self.assertRaises(ValueError):
                request('decision',port=0,token='fixture',body={'request_id':'x','approve':False})
            ctor.assert_not_called()

    def test_12_owner_cli_transport_handles_success_once(self):
        from rdc.owner_api import request
        with patch('rdc.owner_api.http.client.HTTPConnection') as ctor:
            conn=ctor.return_value
            conn.getresponse.return_value.status=200
            conn.getresponse.return_value.read.return_value=b'{"ok":true}'
            self.assertEqual({'ok':True},request('pause',port=8765,token='fixture'))
            args,kwargs=conn.request.call_args
            self.assertEqual(('POST','/api/pause'),args)
            self.assertEqual({'paused':True},json.loads(kwargs['body']))
            self.assertEqual('Bearer fixture',kwargs['headers']['Authorization'])
            conn.request.assert_called_once()
