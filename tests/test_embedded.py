"""Embedded preview lifecycle and portable MCP resource contracts."""
import base64
from pathlib import Path
import tempfile
import unittest

import anyio
from mcp import Client
from mcp.shared.exceptions import MCPError

from rdc.config import Settings
from rdc.engine import Engine
from rdc.server import create_mcp_server

SID = '12345678-1234-1234-1234-123456789abc'


class Browsers:
    def __init__(self):
        self.sessions = [{'session_id': SID, 'backend': 'playwright', 'browser': 'chromium',
                          'url': 'https://example.test/', 'width': 800, 'height': 600,
                          'cursor': {'x': 42, 'y': 35}}]
        self.calls = []
    def call(self, name, args):
        self.calls.append(name)
        if name == 'rdc_browser_list':
            return {'sessions': self.sessions}
        if name == 'rdc_browser_screenshot':
            return self.sessions[0] | {'mime_type': 'image/png',
                'data': base64.b64encode(b'png-test').decode()}
        raise AssertionError('Preview invoked a mutating or unexpected adapter operation')
    def status(self):
        return {'browser': {'sessions': self.sessions}}
    def snapshot(self, session_id=None):
        return self.call('rdc_browser_screenshot', {'session_id': session_id})
    def close(self): pass


class EmbeddedContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.engine = Engine(Settings(state_dir=base/'state', roots=[base], approval_mode='review'))
        self.engine.adapters.close()
        self.engine.adapters = Browsers()
    def tearDown(self):
        self.engine.close()
        self.tmp.cleanup()

    def test_open_and_frame_are_read_only_even_while_agent_paused(self):
        self.engine.pause(True)
        opened = self.engine.call('rdc_preview_open', {})
        self.assertTrue(opened['ok'], opened)
        self.assertEqual(opened['session_id'], SID)
        self.assertTrue(opened['viewer']['close_keeps_working'])
        self.assertTrue(opened['paused'])
        frame = self.engine.call('rdc_preview_frame', {'session_id': SID})
        self.assertTrue(frame['ok'], frame)
        self.assertEqual(frame['device_id'], opened['device_id'])
        self.assertEqual(frame['cursor'], {'x': 42, 'y': 35})
        self.assertEqual(self.engine.store.approvals(), [])
        self.assertTrue(all('close' not in c for c in self.engine.adapters.calls))

    def test_empty_and_unknown_sessions_do_not_create_or_switch_browser(self):
        unknown = '87654321-4321-4321-4321-cba987654321'
        result = self.engine.call('rdc_preview_open', {'session_id': unknown})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'session_not_found')
        self.engine.adapters.sessions.clear()
        result = self.engine.call('rdc_preview_open', {})
        self.assertTrue(result['ok'])
        self.assertIsNone(result['session_id'])
        self.assertEqual(result['sessions'], [])

    def test_portable_resources_metadata_images_and_unknown_resource(self):
        async def check():
            async with Client(create_mcp_server(self.engine)) as client:
                tools = {t.name:t for t in (await client.list_tools()).tools}
                opening = tools['rdc_preview_open']
                uri = opening.meta['ui']['resourceUri']
                self.assertTrue(uri.startswith('ui://'))
                self.assertTrue(opening.annotations.read_only_hint)
                self.assertEqual(tools['rdc_preview_frame'].meta['ui']['visibility'], ['app'])
                self.assertNotIn('resourceUri', tools['rdc_preview_frame'].meta['ui'])
                resources = await client.list_resources()
                self.assertIn(uri, [str(r.uri) for r in resources.resources])
                html = (await client.read_resource(uri)).contents[0]
                self.assertEqual(html.mime_type, 'text/html;profile=mcp-app')
                self.assertIn('RDC', html.text)
                self.assertEqual(html.meta['ui']['csp']['connectDomains'], [])
                self.assertNotIn('owner-token', html.text)
                with self.assertRaises(MCPError):
                    await client.read_resource('ui://rdc/does-not-exist')
                frame = await client.call_tool('rdc_preview_frame', {'session_id': SID})
                self.assertFalse(frame.is_error)
                self.assertTrue(any(c.type == 'image' for c in frame.content))
                self.assertNotIn('data', frame.structured_content)
                self.assertEqual(frame.structured_content['session_id'], SID)
        anyio.run(check)


if __name__ == '__main__': unittest.main()
