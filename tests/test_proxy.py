"""Shared-worker bridge contracts use real TCP and an official stdio client."""
import base64
from contextlib import contextmanager, nullcontext
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import anyio
import httpx
from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server import Server
from mcp.shared.exceptions import MCPError
import uvicorn

from rdc.server import create_app


class BrowserWorkerFixture:
    """A stateful browser adapter stand-in owned by the HTTP worker alone."""
    def __init__(self):
        self.settings = SimpleNamespace(allowed_origins=[], max_read_bytes=262144)
        self.sources = {}
        self.calls = []
        self.closed = False

    def catalog(self):
        return [{'name': 'rdc_browser', 'description': 'Fixture browser',
                 'inputSchema': {'type': 'object', 'properties': {'action': {'type': 'string'},
                 'session_id': {'type': 'string'}, 'text': {'type': 'string'}}, 'required': ['action']}}]

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        source = arguments.get('session_id', 'browser-1')
        if arguments['action'] == 'open':
            self.sources[source] = 'initial page'
        elif arguments['action'] == 'type':
            self.sources[source] = arguments['text']
        elif arguments['action'] == 'slow':
            time.sleep(1)
            self.sources[source] = 'completed after timeout'
        return {'ok': True, 'session_id': source, 'text': self.sources.get(source)}

    def status(self):
        return {'sources': self.sources, 'closed': self.closed}

    def snapshot(self, session_id=None):
        return {'mime_type': 'image/png', 'data': base64.b64encode(self.sources[session_id].encode()).decode()}

    def close(self):
        self.closed = True


@contextmanager
def running_worker(engine, agent, mcp_server=None):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    replacement = (patch('rdc.server.create_mcp_server', return_value=mcp_server)
                   if mcp_server is not None else nullcontext())
    with replacement:
        app = create_app(engine, agent, 'owner-only')
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    if not server.started:
        raise AssertionError('worker did not start')
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        if thread.is_alive():
            raise AssertionError('worker did not stop')


class SharedWorkerContracts(unittest.TestCase):
    def state(self, directory, token):
        state = Path(directory) / 'client-state'
        state.mkdir()
        (state / 'agent-token').write_text(token + '\n')
        (state / 'agent-token').chmod(0o600)
        return state

    def parameters(self, state, url, *extra):
        return StdioServerParameters(command=sys.executable,
            args=['-B', '-m', 'rdc', 'connect', '--state-dir', str(state), '--url', url + '/mcp', *extra])

    def test_stdio_browser_actions_share_owner_preview_and_outlive_disconnect(self):
        engine = BrowserWorkerFixture()
        token = 'a' * 48
        with tempfile.TemporaryDirectory() as tmp, running_worker(engine, token) as url:
            state = self.state(tmp, token)  # No config or owner credential is available to this bridge.

            async def exchange():
                async with stdio_client(self.parameters(state, url)) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        self.assertEqual([tool.name for tool in tools.tools], ['rdc_browser'])
                        opened = await session.call_tool('rdc_browser', {'action': 'open'})
                        source = opened.structured_content['session_id']
                        typed = await session.call_tool('rdc_browser', {'action': 'type', 'session_id': source, 'text': 'same live workspace'})
                        self.assertFalse(typed.is_error)
                        async with httpx.AsyncClient(trust_env=False) as client:
                            preview = await client.get(url + '/api/preview', params={'session_id': source}, headers={'Authorization': 'Bearer owner-only'})
                            self.assertEqual(preview.content, b'same live workspace')
                self.assertFalse(engine.closed)
                self.assertEqual(engine.sources[source], 'same live workspace')
                # A new stdio client attaches to the same worker, preserving its browser source.
                async with stdio_client(self.parameters(state, url)) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        result = await session.call_tool('rdc_browser', {'action': 'read', 'session_id': source})
                        self.assertEqual(result.structured_content['text'], 'same live workspace')
            anyio.run(exchange)
            self.assertEqual(len(engine.calls), 3)
            self.assertFalse(engine.closed)
        self.assertTrue(engine.closed)

    def test_bad_token_fails_without_exposing_credentials(self):
        token = 'correct-agent-' + 'a' * 48
        with tempfile.TemporaryDirectory() as tmp, running_worker(BrowserWorkerFixture(), token) as url:
            wrong = 'wrong-agent-' + 'b' * 48
            state = self.state(tmp, wrong)
            result = subprocess.run([sys.executable, '-m', 'rdc', 'connect', '--state-dir', str(state), '--url', url + '/mcp', '--timeout', '2'],
                                    input='', text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Cannot connect to RDC worker', result.stderr)
            self.assertNotIn(wrong, result.stderr + result.stdout)
            self.assertNotIn(token, result.stderr + result.stdout)
            self.assertNotIn('owner-only', result.stderr + result.stdout)
            self.assertEqual(result.stdout, '')

    def test_embedded_resources_metadata_and_identity_survive_bridge(self):
        """A real host must be able to fetch its UI after a recoverable miss."""
        engine = BrowserWorkerFixture()
        uri = 'ui://rdc/preview-v1.html'
        html = '<!doctype html><html><body>RDC fixture preview</body></html>'
        metadata = {'ui': {'prefersBorder': True, 'csp': {
            'connectDomains': [], 'resourceDomains': [], 'frameDomains': []}},
            'rdc/fixture': {'version': 1}}
        icon = types.Icon(src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZQAAAABJRU5ErkJggg==',
                          mime_type='image/png', sizes=['1x1'])
        reads = []

        async def list_resources(context, params):
            return types.ListResourcesResult(resources=[types.Resource(
                uri=uri, name='rdc-preview', title='RDC preview',
                mime_type='text/html;profile=mcp-app', icons=[icon], meta=metadata)])

        async def read_resource(context, params):
            reads.append((params.uri, params.meta,
                          context.session.client_capabilities.extensions))
            if params.uri != uri:
                raise MCPError(code=-32002, message='Preview resource not found',
                               data={'uri': params.uri})
            return types.ReadResourceResult(contents=[types.TextResourceContents(
                uri=uri, mime_type='text/html;profile=mcp-app', text=html, meta=metadata)])

        async def list_tools(context, params):
            descriptors = engine.catalog()
            descriptors[0]['_meta'] = {'ui': {'resourceUri': uri}}
            return types.ListToolsResult(tools=[types.Tool.model_validate(item)
                                               for item in descriptors])

        upstream = Server('rdc-fixture', version='7.2.1', title='RDC fixture identity',
                          description='Independent worker preview fixture', icons=[icon],
                          on_list_resources=list_resources, on_read_resource=read_resource,
                          on_list_tools=list_tools)
        upstream.extensions['io.modelcontextprotocol/ui'] = {}
        token = 'a' * 48
        with tempfile.TemporaryDirectory() as tmp, running_worker(engine, token, upstream) as url:
            state = self.state(tmp, token)

            async def exchange():
                async with stdio_client(self.parameters(state, url)) as streams:
                    async with ClientSession(*streams, extensions={
                        'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}
                    }) as session:
                        initialized = await session.initialize()
                        self.assertEqual(initialized.protocol_version, '2025-11-25')
                        self.assertIsNotNone(initialized.capabilities.resources)
                        # The SDK's 2025 codec omits the newer extension field;
                        # legacy hosts discover the UI through tool/resource metadata.
                        self.assertIsNone(initialized.capabilities.extensions)
                        self.assertEqual(initialized.server_info.name, 'rdc-fixture')
                        self.assertEqual(initialized.server_info.version, '7.2.1')
                        self.assertEqual(initialized.server_info.title, 'RDC fixture identity')
                        self.assertEqual(initialized.server_info.description,
                                         'Independent worker preview fixture')
                        self.assertEqual(initialized.server_info.icons, [icon])
                        listed = await session.list_resources()
                        self.assertEqual(len(listed.resources), 1)
                        self.assertEqual(listed.resources[0].uri, uri)
                        self.assertEqual(listed.resources[0].meta, metadata)
                        self.assertEqual(listed.resources[0].icons, [icon])

                        with self.assertRaises(MCPError) as rejected:
                            await session.read_resource('ui://rdc/missing.html')
                        self.assertEqual(rejected.exception.code, -32002)
                        self.assertEqual(rejected.exception.data,
                                         {'uri': 'ui://rdc/missing.html'})

                        # A domain error must not poison the persistent bridge.
                        content = await session.read_resource(uri, meta={'rdc/test': 'forwarded'})
                        self.assertEqual(content.contents[0].text, html)
                        self.assertEqual(content.contents[0].mime_type, 'text/html;profile=mcp-app')
                        self.assertEqual(content.contents[0].meta, metadata)
                        tools = await session.list_tools()
                        self.assertEqual([tool.name for tool in tools.tools], ['rdc_browser'])
                        self.assertEqual(tools.tools[0].meta, {'ui': {'resourceUri': uri}})
                self.assertFalse(engine.closed)
                async with stdio_client(self.parameters(state, url)) as streams:
                    async with ClientSession(*streams, extensions={
                        'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}
                    }) as session:
                        discovered = await session.discover()
                        self.assertEqual(discovered.capabilities.extensions,
                                         {'io.modelcontextprotocol/ui': {}})
                        self.assertEqual(session.server_info.title, 'RDC fixture identity')
                        self.assertEqual(session.server_info.icons, [icon])
                        content = await session.read_resource(uri)
                        self.assertEqual(content.contents[0].meta, metadata)
                        self.assertEqual(content.contents[0].text, html)
            anyio.run(exchange)
        self.assertEqual(len(reads), 3)
        self.assertEqual(reads[1][1]['rdc/test'], 'forwarded')
        self.assertEqual(reads[1][2], {
            'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}})

    def test_malformed_private_token_fails_before_network_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.state(tmp, 'short')
            result = subprocess.run([sys.executable, '-m', 'rdc', 'connect', '--state-dir', str(state)],
                                    input='', text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid token file', result.stderr)
            self.assertEqual(result.stdout, '')

    def test_definite_tool_rejection_preserves_error_and_keeps_bridge_usable(self):
        engine = BrowserWorkerFixture()

        async def list_tools(context, params):
            return types.ListToolsResult(tools=[types.Tool.model_validate(item) for item in engine.catalog()])

        async def call_tool(context, params):
            if params.arguments.get('action') == 'reject':
                raise MCPError(code=-32602, message='Fixture action rejected', data={'field': 'action'})
            value = engine.call(params.name, params.arguments)
            return types.CallToolResult(content=[], structured_content=value)

        upstream = Server('rdc-fixture', version='1', on_list_tools=list_tools, on_call_tool=call_tool)
        with tempfile.TemporaryDirectory() as tmp, running_worker(engine, 'a' * 48, upstream) as url:
            state = self.state(tmp, 'a' * 48)
            async def exchange():
                async with stdio_client(self.parameters(state, url)) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        with self.assertRaises(MCPError) as rejected:
                            await session.call_tool('rdc_browser', {'action': 'reject'})
                        self.assertEqual(rejected.exception.code, -32602)
                        self.assertEqual(rejected.exception.data, {'field': 'action'})
                        opened = await session.call_tool('rdc_browser', {'action': 'open'})
                        self.assertEqual(opened.structured_content['text'], 'initial page')
                        self.assertEqual(len((await session.list_tools()).tools), 1)
            anyio.run(exchange)
        self.assertEqual(engine.calls, [('rdc_browser', {'action': 'open'})])

    def test_definite_catalog_rejection_does_not_poison_later_requests(self):
        engine = BrowserWorkerFixture()

        async def list_tools(context, params):
            if params.cursor == 'expired-cursor':
                raise MCPError(code=-32602, message='Fixture cursor expired', data={'cursor': 'expired-cursor'})
            return types.ListToolsResult(tools=[types.Tool.model_validate(item) for item in engine.catalog()])

        upstream = Server('rdc-fixture', version='1', on_list_tools=list_tools)
        with tempfile.TemporaryDirectory() as tmp, running_worker(engine, 'a' * 48, upstream) as url:
            state = self.state(tmp, 'a' * 48)
            async def exchange():
                async with stdio_client(self.parameters(state, url)) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        with self.assertRaises(MCPError) as rejected:
                            await session.list_tools(params=types.PaginatedRequestParams(cursor='expired-cursor'))
                        self.assertEqual(rejected.exception.code, -32602)
                        self.assertEqual(rejected.exception.data, {'cursor': 'expired-cursor'})
                        self.assertEqual(len((await session.list_tools()).tools), 1)
            anyio.run(exchange)

    def test_timeout_reports_unknown_outcome_and_never_replays_mutation(self):
        engine = BrowserWorkerFixture()
        token = 'a' * 48
        with tempfile.TemporaryDirectory() as tmp, running_worker(engine, token) as url:
            state = self.state(tmp, token)
            async def exchange():
                async with stdio_client(self.parameters(state, url, '--timeout', '.3')) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        result = await session.call_tool('rdc_browser', {'action': 'slow'})
                        self.assertTrue(result.is_error)
                        self.assertIn('outcome may be unknown', result.content[0].text)
                        again = await session.call_tool('rdc_browser', {'action': 'slow'})
                        self.assertTrue(again.is_error)
            anyio.run(exchange)
            self.assertEqual(len(engine.calls), 1)
            self.assertFalse(engine.closed)

    def test_endpoint_validation(self):
        from rdc.proxy import validate_endpoint
        for valid in ('http://127.0.0.1:8765/mcp', 'http://localhost:8765/mcp', 'http://[::1]:8765/mcp', 'https://worker.example/mcp'):
            self.assertEqual(validate_endpoint(valid), valid)
        for invalid in ('http://example.com/mcp', 'https://user:secret@example.com/mcp', 'https://example.com/mcp?token=secret', 'https://example.com/mcp#token', 'file:///mcp', 'http://127.0.0.1:99999/mcp'):
            with self.subTest(endpoint=invalid), self.assertRaises(ValueError):
                validate_endpoint(invalid)


if __name__ == '__main__':
    unittest.main()
