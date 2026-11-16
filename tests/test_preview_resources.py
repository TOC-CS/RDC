"""Resource URI compatibility at the actual Python MCP boundary."""
import unittest
from types import SimpleNamespace

import anyio
from mcp.shared.exceptions import MCPError

from rdc.preview import list_resources, read_resource


class PreviewResourceContracts(unittest.TestCase):
    def test_openai_starts_inline_and_only_advertises_supported_host_modes(self):
        async def check():
            result = await read_resource(None, SimpleNamespace(uri='ui://rdc/preview-v6.html'))
            layout = result.contents[0].meta['openai/ui']
            self.assertEqual(layout['preferredDisplayMode'], 'inline')
            self.assertEqual(layout['availableDisplayModes'], ['inline','fullscreen'])
        anyio.run(check)

    def test_fresh_resource_is_advertised_and_all_published_uris_are_readable(self):
        async def check():
            resources = await list_resources(None, None)
            self.assertEqual([str(item.uri) for item in resources.resources], ['ui://rdc/preview-v8.html'])
            bodies = []
            for uri in ('ui://rdc/preview-v8.html', 'ui://rdc/preview-v7.html', 'ui://rdc/preview-v6.html', 'ui://rdc/preview-v5.html', 'ui://rdc/preview-v4.html', 'ui://rdc/preview-v3.html', 'ui://rdc/preview-v2.html', 'ui://rdc/preview-v1.html'):
                result = await read_resource(None, SimpleNamespace(uri=uri))
                content = result.contents[0]
                self.assertEqual(str(content.uri), uri)
                self.assertEqual(content.mime_type, 'text/html;profile=mcp-app')
                self.assertIn('RDC', content.text)
                self.assertEqual(content.meta['ui']['csp']['connectDomains'], [])
                bodies.append(content.text)
            self.assertTrue(all(body == bodies[0] for body in bodies))
            with self.assertRaises(MCPError):
                await read_resource(None, SimpleNamespace(uri='ui://rdc/preview-v999.html'))
        anyio.run(check)


if __name__ == '__main__':
    unittest.main()
