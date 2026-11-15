"""Portable MCP App resource. No worker secrets or direct network connection."""
from pathlib import Path

from mcp import types
from mcp.shared.exceptions import MCPError

UI_URI = 'ui://rdc/preview-v1.html'
UI_MIME = 'text/html;profile=mcp-app'
UI_EXTENSION = 'io.modelcontextprotocol/ui'


async def list_resources(context, params):
    return types.ListResourcesResult(resources=[types.Resource(
        uri=UI_URI, name='rdc-preview', title='RDC Live Preview',
        description='An embedded view of RDC browser and configured mobile sessions. Closing the view leaves the worker running.',
        mime_type=UI_MIME)])


async def read_resource(context, params):
    if str(params.uri) != UI_URI:
        raise MCPError(code=-32002, message='RDC preview resource not found')
    path = Path(__file__).parent / 'embedded' / 'preview.html'
    try:
        html = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise MCPError(code=-32603, message='RDC preview bundle is missing; reinstall a complete RDC package') from None
    return types.ReadResourceResult(contents=[types.TextResourceContents(
        uri=UI_URI, mime_type=UI_MIME, text=html, meta={
            'ui':{'prefersBorder':True,
                  'csp':{'connectDomains':[], 'resourceDomains':[], 'frameDomains':[]}},
            'openai/ui':{'availableDisplayModes':['inline','fullscreen','pip']},
            'openai/widgetDescription':'RDC live browser and mobile preview. Mobile input uses the configured device; hiding the view leaves work running.'})])
