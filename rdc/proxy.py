"""Official-SDK stdio bridge to an already running RDC HTTP worker.

The bridge owns transport sessions only. Browser sources, jobs, approvals and the
owner preview remain in the worker, which is never shut down by this process.
"""
from __future__ import annotations

import ipaddress
import math
from urllib.parse import urlsplit

import anyio
import httpx2
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import MCPError


class WorkerConnectionError(RuntimeError):
    """A deliberately credential-free connection diagnostic."""


def validate_endpoint(url: str) -> str:
    """Permit local HTTP or explicitly selected HTTPS without URL credentials."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
        if (parsed.scheme not in ('http', 'https') or not hostname or
                parsed.username is not None or parsed.password is not None or
                parsed.query or parsed.fragment or not parsed.path or
                any(ord(char) <= 32 or ord(char) == 127 for char in url) or
                (port is not None and not 1 <= port <= 65535)):
            raise ValueError
        if parsed.scheme == 'http':
            try:
                loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                loopback = hostname == 'localhost'
            if not loopback:
                raise ValueError
    except ValueError:
        raise ValueError('MCP URL must use loopback HTTP or HTTPS, without credentials, query or fragment') from None
    return url


LOST_MESSAGE = ('RDC worker connection failed or timed out; the tool outcome may be unknown. '
                'No action was retried. Check the owner dashboard before reconnecting.')
UI_EXTENSION = 'io.modelcontextprotocol/ui'
UI_MIME = 'text/html;profile=mcp-app'


def create_proxy_server(session: ClientSession, timeout: float) -> Server:
    """Keep one upstream client for the whole downstream stdio connection."""
    failed = False

    async def list_tools(context, params):
        nonlocal failed
        if failed:
            raise MCPError(code=-32603, message=LOST_MESSAGE)
        try:
            with anyio.fail_after(timeout):
                return await session.list_tools(params=params)
        except MCPError as exc:
            if exc.code not in (types.REQUEST_TIMEOUT, types.CONNECTION_CLOSED):
                raise
            failed = True
            raise MCPError(code=-32603, message=LOST_MESSAGE) from None
        except Exception:
            failed = True
            raise MCPError(code=-32603, message=LOST_MESSAGE) from None

    async def call_tool(context, params):
        nonlocal failed
        if not failed:
            try:
                with anyio.fail_after(timeout):
                    return await session.call_tool(params.name, params.arguments,
                                                   meta=params.meta)
            except MCPError as exc:
                # A complete protocol rejection leaves the connection usable.
                # Preserve it for the caller without retrying the rejected call.
                if exc.code not in (types.REQUEST_TIMEOUT, types.CONNECTION_CLOSED):
                    raise
                failed = True
            except Exception:
                # Never reconnect or replay a request: a timed-out mutation may
                # already have changed the remote browser or started a job.
                failed = True
        return types.CallToolResult(
            content=[types.TextContent(type='text', text=LOST_MESSAGE)],
            structured_content={'ok': False, 'error': {'code': 'worker_connection_lost', 'message': LOST_MESSAGE}},
            is_error=True)

    async def forward_resource(operation, *args, **kwargs):
        nonlocal failed
        if failed:
            raise MCPError(code=-32603, message=LOST_MESSAGE)
        try:
            with anyio.fail_after(timeout):
                return await operation(*args, **kwargs)
        except MCPError as exc:
            # An expected resource error (for example, a stale UI URI) is a
            # complete response, not a transport loss. Keep the shared bridge
            # usable and preserve the server's machine-readable error details.
            if exc.code not in (types.REQUEST_TIMEOUT, types.CONNECTION_CLOSED):
                raise
            failed = True
            raise MCPError(code=-32603, message=LOST_MESSAGE) from None
        except Exception:
            failed = True
            raise MCPError(code=-32603, message=LOST_MESSAGE) from None

    async def list_resources(context, params):
        return await forward_resource(session.list_resources, params=params)

    async def read_resource(context, params):
        return await forward_resource(session.read_resource, params.uri, meta=params.meta)

    info = session.server_info
    capabilities = session.server_capabilities
    has_resources = capabilities is not None and capabilities.resources is not None
    server = Server(info.name if info else 'rdc', version=info.version if info else '0.1.0a2',
                    title=info.title if info else None,
                    description=info.description if info else None,
                    website_url=info.website_url if info else None,
                    icons=info.icons if info else None,
                    instructions='Connected to the running RDC worker. Browser sources and embedded previews share that worker.',
                    on_list_tools=list_tools, on_call_tool=call_tool,
                    on_list_resources=list_resources if has_resources else None,
                    on_read_resource=read_resource if has_resources else None)
    # Only advertise the extension this bridge actually forwards. Other worker
    # extensions can require callbacks or notifications the bridge does not own.
    extensions = capabilities.extensions if capabilities is not None else None
    if has_resources and extensions is not None and UI_EXTENSION in extensions:
        server.extensions[UI_EXTENSION] = dict(extensions[UI_EXTENSION])
    return server


async def run_connect(url: str, agent_token: str, timeout: float = 60):
    """Serve stdio through a persistent authenticated official HTTP client."""
    validate_endpoint(url)
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 604800:
        raise ValueError('timeout must be greater than zero and at most seven days')
    initialized = False
    try:
        # Ignore ambient proxy environment variables so local credentials cannot
        # inadvertently be routed through an unrelated HTTP proxy.
        # SSE is a long-lived stream. Bound individual MCP operations above,
        # rather than timing out the shared transport and cancelling its peers.
        async with httpx2.AsyncClient(headers={'Authorization': f'Bearer {agent_token}'},
                                     timeout=httpx2.Timeout(timeout, read=None), trust_env=False) as client:
            async with streamable_http_client(url, http_client=client) as streams:
                # The bridge can relay UI resources to an Apps-capable host.
                # Plain MCP hosts still receive useful normal tool results.
                async with ClientSession(*streams, read_timeout_seconds=timeout,
                                         extensions={UI_EXTENSION: {'mimeTypes': [UI_MIME]}}) as session:
                    with anyio.fail_after(timeout):
                        try:
                            # Modern discovery preserves extension capability
                            # maps that the legacy 2025 handshake cannot encode.
                            await session.discover()
                        except MCPError as exc:
                            if exc.code not in (types.METHOD_NOT_FOUND,
                                                types.UNSUPPORTED_PROTOCOL_VERSION):
                                raise
                            # A definite unsupported discovery response permits
                            # a legacy handshake. Timeouts are never retried.
                            await session.initialize()
                    initialized = True
                    server = create_proxy_server(session, timeout)
                    async with stdio_server() as (read_stream, write_stream):
                        await server.run(read_stream, write_stream, server.create_initialization_options())
    except Exception:
        # Raw transport exception groups can include gateway URLs or payloads.
        # Keep CLI stderr helpful without revealing credentials or tool input.
        message = ('RDC worker connection ended. No action was retried; check the owner dashboard before reconnecting.'
                   if initialized else
                   'Cannot connect to RDC worker. Start rdc serve and verify the MCP URL and private agent-token file.')
        raise WorkerConnectionError(message) from None
