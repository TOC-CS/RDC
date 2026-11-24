"""Official MCP SDK transports and the authenticated headless owner API.

HTTP bearer mode is intended for direct clients and an authenticated gateway.
It does not implement the OAuth onboarding required by ChatGPT's public web UI.
"""
from __future__ import annotations

import base64
import binascii
from contextlib import asynccontextmanager
import hmac
import json
from urllib.parse import urlsplit

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

MAX_BODY_BYTES = 1_048_576


def create_mcp_server(engine) -> Server:
    """Expose only the engine's agent catalog; owner decisions stay off MCP."""
    from . import __version__
    from .preview import UI_EXTENSION, list_resources, read_resource
    async def list_tools(context, params):
        descriptors = await anyio.to_thread.run_sync(engine.catalog)
        return types.ListToolsResult(tools=[types.Tool.model_validate(item) for item in descriptors])

    async def call_tool(context, params):
        result = await anyio.to_thread.run_sync(engine.call, params.name, params.arguments or {})
        if result.get('ok') and result.get('mime_type') in ('image/png','image/jpeg','image/webp') and isinstance(result.get('data'),str):
            # Images belong in MCP image blocks. Repeating their base64 in text
            # wastes model context and prevents clients from displaying them.
            metadata = {key:value for key,value in result.items() if key != 'data'}
            metadata['image_in_content'] = True
            return types.CallToolResult(
                content=[types.TextContent(type='text',text=json.dumps(metadata,ensure_ascii=False)),
                         types.ImageContent(type='image',data=result['data'],mime_type=result['mime_type'])],
                structured_content=metadata)
        return types.CallToolResult(
            content=[types.TextContent(type='text', text=json.dumps(result, ensure_ascii=False))],
            structured_content=result,
            is_error=result.get('ok') is False,
        )

    def input_schema(name):
        return next((item['inputSchema'] for item in engine.catalog() if item['name'] == name), None)

    server = Server('rdc', version=__version__, title='RDC',
                  instructions='RDC agent tools operate within owner grants. Pass the current task session_id to rdc_preview_open for a live view of that source in compatible AI hosts. Closing the view leaves the worker running. Routine operations follow the configured policy. Exceptional owner decisions use the private local owner API, never agent tools.',
                  on_list_tools=list_tools, on_call_tool=call_tool,
                  get_tool_input_schema=input_schema,
                  on_list_resources=list_resources, on_read_resource=read_resource)
    server.extensions[UI_EXTENSION] = {}
    return server


async def run_stdio(engine):
    server = create_mcp_server(engine)
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await anyio.to_thread.run_sync(engine.close)


class Boundary:
    """Apply role, host, origin, and size checks before parsing or MCP routing."""
    def __init__(self, app, agent_token, owner_token, allowed_origins):
        self.app = app
        self.agent_token = agent_token.encode()
        self.owner_token = owner_token.encode()
        self.allowed_origins = set(allowed_origins)
        self.allowed_hosts = {urlsplit(origin).netloc.lower() for origin in allowed_origins}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        headers = {}
        for key, value in scope['headers']:
            key = key.lower()
            if key in headers and key in (b'host', b'authorization', b'origin', b'content-length'):
                await JSONResponse({'error': 'duplicate security header'}, status_code=400)(scope, receive, send)
                return
            headers[key] = value
        host = headers.get(b'host', b'').decode('latin1').lower()
        try:
            hostname = urlsplit('http://' + host).hostname
        except ValueError:
            hostname = None
        if hostname not in ('127.0.0.1', 'localhost', '::1') and host not in self.allowed_hosts:
            await JSONResponse({'error': 'host forbidden'}, status_code=403)(scope, receive, send)
            return
        origin = headers.get(b'origin')
        if origin is not None:
            origin = origin.decode('latin1')
            if origin not in self.allowed_origins and origin != f"{scope.get('scheme', 'http')}://{host}":
                await JSONResponse({'error': 'origin forbidden'}, status_code=403)(scope, receive, send)
                return
        path = scope['path']
        if path == '/mcp' or path.startswith('/mcp/') or path.startswith('/api/'):
            authorization = headers.get(b'authorization', b'')
            token = authorization[7:] if authorization.startswith(b'Bearer ') else b''
            is_owner = hmac.compare_digest(token, self.owner_token)
            is_agent = hmac.compare_digest(token, self.agent_token)
            allowed = is_agent if path == '/mcp' or path.startswith('/mcp/') else is_owner
            if not allowed:
                status = 403 if is_owner or is_agent else 401
                response = JSONResponse({'error': 'owner token required' if path.startswith('/api/') else 'agent token required'}, status_code=status,
                                        headers={'WWW-Authenticate': 'Bearer'} if status == 401 else {})
                await response(scope, receive, send)
                return
        if scope['method'] in ('POST', 'PUT', 'PATCH'):
            try:
                length = int(headers.get(b'content-length', b'0'))
                if length < 0:
                    raise ValueError
            except ValueError:
                await JSONResponse({'error': 'invalid content length'}, status_code=400)(scope, receive, send)
                return
            chunks = []
            total = 0
            if length > MAX_BODY_BYTES:
                await JSONResponse({'error': 'request too large'}, status_code=413)(scope, receive, send)
                return
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                total += len(message.get('body', b''))
                if total > MAX_BODY_BYTES:
                    await JSONResponse({'error': 'request too large'}, status_code=413)(scope, receive, send)
                    return
                chunks.append(message)
                if not message.get('more_body', False):
                    break
            iterator = iter(chunks)
            original_receive = receive
            async def buffered_receive():
                try:
                    return next(iterator)
                except StopIteration:
                    return await original_receive()
            receive = buffered_receive

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [
                    (b'cache-control', b'no-store'),
                    (b'x-content-type-options', b'nosniff'),
                    (b'content-security-policy', b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
                    (b'referrer-policy', b'no-referrer'),
                ]
            await send(message)
        await self.app(scope, receive, secure_send)


def create_app(engine, agent_token: str, owner_token: str):
    if not agent_token or not owner_token or hmac.compare_digest(agent_token, owner_token):
        raise ValueError('distinct nonempty agent and owner tokens are required')
    server = create_mcp_server(engine)
    origins = engine.settings.allowed_origins
    security = TransportSecuritySettings(
        allowed_hosts=['127.0.0.1', 'localhost', '[::1]', '127.0.0.1:*', 'localhost:*', '[::1]:*'] + [urlsplit(origin).netloc for origin in origins],
        allowed_origins=['http://127.0.0.1', 'http://localhost', 'http://[::1]', 'http://127.0.0.1:*', 'http://localhost:*', 'http://[::1]:*'] + list(origins))
    mcp_app = server.streamable_http_app(streamable_http_path='/mcp', json_response=True,
                                         max_request_body_size=MAX_BODY_BYTES, transport_security=security)

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with server.session_manager.run():
                yield
        finally:
            await anyio.to_thread.run_sync(engine.close)

    async def body(request, fields):
        if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
            raise ValueError('application/json required')
        value = await request.json()
        if not isinstance(value, dict) or set(value) != set(fields):
            raise ValueError('invalid request fields')
        return value

    async def api(request: Request):
        try:
            if request.url.path == '/api/status':
                result = await anyio.to_thread.run_sync(engine.status)
            elif request.url.path == '/api/credentials':
                result = {'ok': True, **await anyio.to_thread.run_sync(engine.credentials.owner_snapshot)}
            elif request.url.path == '/api/credentials/enroll':
                value = await body(request, ('label', 'origin', 'provider', 'locator'))
                result = await anyio.to_thread.run_sync(lambda: engine.credentials.enroll(**value))
            elif request.url.path == '/api/credentials/remove':
                value = await body(request, ('credential_id',))
                if not isinstance(value['credential_id'], str):
                    raise ValueError('credential_id required')
                result = await anyio.to_thread.run_sync(engine.credentials.remove, value['credential_id'])
            elif request.url.path == '/api/credentials/decision':
                value = await body(request, ('request_id', 'decision'))
                if not isinstance(value['request_id'], str) or value['decision'] not in ('once', 'always', 'deny'):
                    raise ValueError('request_id and once, always, or deny decision required')
                result = await anyio.to_thread.run_sync(engine.credentials.decide, value['request_id'], value['decision'])
            elif request.url.path == '/api/credentials/revoke':
                value = await body(request, ('grant_id',))
                if not isinstance(value['grant_id'], str):
                    raise ValueError('grant_id required')
                result = await anyio.to_thread.run_sync(engine.credentials.revoke, value['grant_id'])
            elif request.url.path == '/api/call':
                value = await body(request, ('name', 'arguments'))
                if not isinstance(value['name'], str) or not isinstance(value['arguments'], dict):
                    raise ValueError('name and arguments required')
                result = await anyio.to_thread.run_sync(engine.owner_call, value['name'], value['arguments'])
            elif request.url.path == '/api/decision':
                value = await body(request, ('request_id', 'approve'))
                if not isinstance(value['request_id'], str) or type(value['approve']) is not bool:
                    raise ValueError('request_id and boolean approve required')
                result = await anyio.to_thread.run_sync(engine.decide, value['request_id'], value['approve'])
            elif request.url.path == '/api/pause':
                value = await body(request, ('paused',))
                if type(value['paused']) is not bool:
                    raise ValueError('boolean paused required')
                result = await anyio.to_thread.run_sync(engine.pause, value['paused'])
            elif request.url.path == '/api/preview':
                result = await anyio.to_thread.run_sync(engine.snapshot, request.query_params.get('session_id'))
                if result.get('ok') is False:
                    return JSONResponse(result, status_code=409)
                if result.get('mime_type') not in ('image/png', 'image/jpeg', 'image/webp'):
                    raise ValueError('preview unavailable')
                return Response(base64.b64decode(result['data'], validate=True), media_type=result['mime_type'])
            else:
                offset = int(request.query_params.get('offset', '0'))
                limit = int(request.query_params.get('limit', '65536'))
                if offset < 0 or not 1 <= limit <= engine.settings.max_read_bytes:
                    raise ValueError('invalid output offset or limit')
                result = await anyio.to_thread.run_sync(engine.owner_call, 'rdc_job_output',
                                                        {'job_id': request.path_params['job_id'], 'offset': offset, 'limit': limit})
            return JSONResponse(result)
        except (ValueError, TypeError, KeyError, binascii.Error) as exc:
            return JSONResponse({'error': str(exc)}, status_code=400)
        except Exception as exc:
            # Expected domain failures expose their stable public code, never tracebacks.
            from rdc.errors import RDCError
            if isinstance(exc, RDCError):
                return JSONResponse({'ok': False, 'error': {'code': exc.code, 'message': exc.message}}, status_code=400)
            raise

    routes = [Route('/api/status', api), Route('/api/call', api, methods=['POST']),
              Route('/api/credentials', api),
              Route('/api/credentials/enroll', api, methods=['POST']),
              Route('/api/credentials/remove', api, methods=['POST']),
              Route('/api/credentials/decision', api, methods=['POST']),
              Route('/api/credentials/revoke', api, methods=['POST']),
              Route('/api/decision', api, methods=['POST']), Route('/api/pause', api, methods=['POST']),
              Route('/api/preview', api), Route('/api/jobs/{job_id}/output', api)]
    # Reuse the official SDK's exact /mcp route without an extra path prefix.
    routes.extend(mcp_app.routes)
    app = Starlette(routes=routes, lifespan=lifespan)
    return Boundary(app, agent_token, owner_token, origins)
