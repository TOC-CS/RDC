"""Portable MCP App resource. No worker secrets or direct network connection."""
from pathlib import Path

from mcp import types
from mcp.shared.exceptions import MCPError

UI_URI = 'ui://rdc/preview-v10.html'
UI_V9_URI = 'ui://rdc/preview-v9.html'
UI_V8_URI = 'ui://rdc/preview-v8.html'
UI_V7_URI = 'ui://rdc/preview-v7.html'
UI_V6_URI = 'ui://rdc/preview-v6.html'
UI_V5_URI = 'ui://rdc/preview-v5.html'
UI_V4_URI = 'ui://rdc/preview-v4.html'
UI_PREVIOUS_URI = 'ui://rdc/preview-v3.html'
UI_V2_URI = 'ui://rdc/preview-v2.html'
UI_LEGACY_URI = 'ui://rdc/preview-v1.html'
UI_MIME = 'text/html;profile=mcp-app'
UI_EXTENSION = 'io.modelcontextprotocol/ui'


async def list_resources(context, params):
    return types.ListResourcesResult(resources=[types.Resource(
        uri=UI_URI, name='rdc-preview', title='RDC Live Preview',
        description='Live view of the selected RDC browser or configured device. Closing the view leaves the worker running.',
        mime_type=UI_MIME)])


async def read_resource(context, params):
    uri = str(params.uri)
    if uri not in (UI_URI, UI_V9_URI, UI_V8_URI, UI_V7_URI, UI_V6_URI, UI_V5_URI, UI_V4_URI, UI_PREVIOUS_URI, UI_V2_URI, UI_LEGACY_URI):
        raise MCPError(code=-32002, message='RDC preview resource not found')
    path = Path(__file__).parent / 'embedded' / 'preview.html'
    try:
        html = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise MCPError(code=-32603, message='RDC preview bundle is missing; reinstall a complete RDC package') from None
    return types.ReadResourceResult(contents=[types.TextResourceContents(
        uri=uri, mime_type=UI_MIME, text=html, meta={
            'ui':{'prefersBorder':False,
                  'csp':{'connectDomains':[], 'resourceDomains':[], 'frameDomains':[]}},
            'openai/ui':{'availableDisplayModes':['inline','fullscreen'], 'preferredDisplayMode':'inline'},
            'openai/widgetDescription':'Live view of the selected RDC session. Hiding the view leaves work running.'})])
