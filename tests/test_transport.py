"""Transport contracts exercise actual ASGI boundaries and official MCP clients."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace

import anyio
import httpx
from starlette.testclient import TestClient

try:
    from rdc.server import create_app, create_mcp_server
except ImportError:
    create_app = create_mcp_server = None


class FixtureEngine:
    def __init__(self):
        self.settings = SimpleNamespace(allowed_origins=[], max_read_bytes=262144)
        self.calls = []
        self.closed = False

    def catalog(self):
        return [{'name': 'rdc_echo', 'description': 'Echo a value', 'inputSchema': {'type': 'object', 'properties': {'value': {'type': 'string'}}, 'required': ['value'], 'additionalProperties': False}}]

    def call(self, name, arguments):
        self.calls.append(('agent', name, arguments))
        return {'ok': True, 'value': arguments['value']}

    def owner_call(self, name, arguments):
        self.calls.append(('owner', name, arguments))
        return {'ok': True, 'name': name, 'arguments': arguments}

    def status(self):
        return {'device_id': 'fixture', 'paused': False}

    def decide(self, request_id, approve):
        return {'ok': True, 'request_id': request_id, 'approve': approve}

    def pause(self, paused):
        return {'ok': True, 'paused': paused}

    def snapshot(self, session_id=None):
        return {'mime_type': 'image/png', 'data': base64.b64encode(b'png-fixture').decode()}

    def close(self):
        self.closed = True


class HttpContracts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(create_app, 'HTTP transport has not been implemented')
        self.engine = FixtureEngine()
        self.client = TestClient(create_app(self.engine, 'agent-secret', 'owner-secret'), base_url='http://127.0.0.1')
        self.client.__enter__()
        self.owner = {'Authorization': 'Bearer owner-secret'}

    def tearDown(self):
        if hasattr(self, 'client'):
            self.client.__exit__(None, None, None)

    def test_owner_routes_reject_agent_and_missing_tokens(self):
        for path in ('/api/status', '/api/preview', '/api/jobs/a/output'):
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.get(path, headers={'Authorization': 'Bearer agent-secret'}).status_code, 403)
        self.assertEqual(self.client.post('/mcp', json={}).status_code, 401)
        self.assertEqual(self.client.get('/api/status', headers=self.owner).json()['device_id'], 'fixture')

    def test_mcp_screenshots_are_images_instead_of_base64_text(self):
        from mcp import Client
        data = base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
        self.engine.call = lambda name,args: {'ok':True,'mime_type':'image/png','data':data,'session_id':'fixture'}
        async def exchange():
            async with Client(create_mcp_server(self.engine)) as client:
                result = await client.call_tool('rdc_echo', {'value':'screenshot'})
                self.assertTrue(any(part.type=='image' for part in result.content))
                self.assertNotIn('data', result.structured_content)
                self.assertNotIn(data, ''.join(part.text for part in result.content if part.type=='text'))
        anyio.run(exchange)

    def test_rejects_cross_origin_host_and_large_or_invalid_json(self):
        for origin in ('https://attacker.example', 'null'):
            self.assertEqual(self.client.post('/api/pause', headers={**self.owner, 'Origin': origin}, json={'paused': True}).status_code, 403)
        self.assertEqual(self.client.get('/api/status', headers={**self.owner, 'Host': 'attacker.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/pause', headers=self.owner, content=b'{' + b' ' * 1048576).status_code, 413)
        for body in ({'paused': 'false'}, {'paused': True, 'extra': 1}, []):
            self.assertEqual(self.client.post('/api/pause', headers=self.owner, json=body).status_code, 400)
        self.assertFalse(self.engine.calls)

    def test_owner_actions_and_preview_preserve_interface(self):
        self.assertEqual(self.client.post('/api/pause', headers=self.owner, json={'paused': True}).json()['paused'], True)
        self.assertEqual(self.client.post('/api/decision', headers=self.owner, json={'request_id': 'a', 'approve': False}).json()['approve'], False)
        self.client.post('/api/call', headers=self.owner, json={'name': 'rdc_echo', 'arguments': {'value': 'owner'}})
        self.assertEqual(self.engine.calls[-1], ('owner', 'rdc_echo', {'value': 'owner'}))
        image = self.client.get('/api/preview?session_id=abc', headers=self.owner)
        self.assertEqual(image.content, b'png-fixture')
        self.assertEqual(image.headers['content-type'], 'image/png')
        result = self.client.get('/api/jobs/job-1/output?offset=12&limit=99', headers=self.owner).json()
        self.assertEqual(result['arguments'], {'job_id': 'job-1', 'offset': 12, 'limit': 99})
        self.assertEqual(self.client.get('/api/jobs/job-1/output?offset=-1', headers=self.owner).status_code, 400)

    def test_real_mcp_initialize_discover_call_over_http(self):
        headers = {'Authorization': 'Bearer agent-secret', 'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}
        init = self.client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'contract', 'version': '1'}}})
        self.assertEqual(init.status_code, 200, init.text)
        self.assertIn('serverInfo', init.json()['result'])
        session_id = init.headers.get('mcp-session-id')
        if session_id:
            headers['mcp-session-id'] = session_id
        headers['mcp-protocol-version'] = init.json()['result']['protocolVersion']
        self.client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        tools = self.client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}).json()['result']['tools']
        self.assertEqual([tool['name'] for tool in tools], ['rdc_echo'])
        result = self.client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'rdc_echo', 'arguments': {'value': 'wire-value'}}}).json()['result']
        self.assertEqual(result['structuredContent'], {'ok': True, 'value': 'wire-value'})
        self.assertEqual(self.engine.calls[-1][0], 'agent')


    def test_official_sdk_client_over_real_http_socket(self):
        import uvicorn
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        import httpx2

        engine = FixtureEngine()
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(engine, 'agent-secret', 'owner-secret'), log_level='critical'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(server.started, 'HTTP server did not start')

        async def exchange():
            async with httpx2.AsyncClient(headers={'Authorization': 'Bearer agent-secret'}, trust_env=False) as client:
                async with streamable_http_client(f'http://127.0.0.1:{port}/mcp', http_client=client) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        listed = await session.list_tools()
                        self.assertEqual([tool.name for tool in listed.tools], ['rdc_echo'])
                        value = await session.call_tool('rdc_echo', {'value': 'sdk-http'})
                        self.assertEqual(value.structured_content['value'], 'sdk-http')
        try:
            anyio.run(exchange)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()
        self.assertFalse(thread.is_alive())
        self.assertTrue(engine.closed)


class CliContracts(unittest.TestCase):
    def test_init_private_tokens_and_preserve_existing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state'
            command = [sys.executable, '-m', 'rdc', 'init', '--state-dir', str(state), '--root', tmp]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads((state / 'config.json').read_text())
            self.assertEqual(config['roots'], [str(Path(tmp).resolve())])
            self.assertFalse(config['allow_exec'])
            self.assertEqual(config['approval_mode'], 'review')
            agent = (state / 'agent-token').read_text().strip()
            owner = (state / 'owner-token').read_text().strip()
            self.assertNotEqual(agent, owner)
            self.assertGreaterEqual(len(agent), 40)
            self.assertNotIn(agent, result.stdout)
            self.assertNotIn(owner, result.stdout)
            if os.name != 'nt':
                for name in ('agent-token', 'owner-token', 'config.json'):
                    self.assertEqual((state / name).stat().st_mode & 0o777, 0o600)
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual((state / 'agent-token').read_text().strip(), agent)

    def test_official_sdk_stdio_round_trip(self):
        async def exchange(state, root):
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client, StdioServerParameters
            params = StdioServerParameters(command=sys.executable, args=['-B', '-m', 'rdc', 'stdio', '--state-dir', str(state)])
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    info = await session.initialize()
                    self.assertEqual(info.server_info.name, 'rdc')
                    from rdc import __version__
                    self.assertEqual(info.server_info.version, __version__)
                    tools = await session.list_tools()
                    self.assertIn('rdc_file_read', [tool.name for tool in tools.tools])
                    result = await session.call_tool('rdc_file_read', {'file_path': str(root / 'fixture.txt')})
                    self.assertFalse(result.is_error)
                    self.assertIn('hello stdio', json.dumps(result.structured_content))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'fixture.txt').write_text('hello stdio')
            state = root / '.state'
            init = subprocess.run([sys.executable, '-m', 'rdc', 'init', '--state-dir', str(state), '--root', str(root)], capture_output=True, text=True)
            self.assertEqual(init.returncode, 0, init.stderr)
            anyio.run(exchange, state, root)


if __name__ == '__main__':
    unittest.main()
