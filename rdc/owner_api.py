"""Private local owner operations, with no browser or agent-accessible approval UI."""
from __future__ import annotations
import http.client
import json

# Fixed routes only. Never accept an arbitrary destination or bearer from agent arguments.
ROUTES = {
    'status': ('GET', '/api/status', ()),
    'pause': ('POST', '/api/pause', ()),
    'resume': ('POST', '/api/pause', ()),
    'decision': ('POST', '/api/decision', ('request_id', 'approve')),
    'credentials': ('GET', '/api/credentials', ()),
    'enroll': ('POST', '/api/credentials/enroll', ('label', 'origin', 'provider', 'locator')),
    'remove': ('POST', '/api/credentials/remove', ('credential_id',)),
    'credential-decision': ('POST', '/api/credentials/decision', ('request_id', 'decision')),
    'revoke': ('POST', '/api/credentials/revoke', ('grant_id',)),
}
MAX_REQUEST = 1_048_576
MAX_RESPONSE = 4_194_304

def read_body(operation, stream):
    fields = ROUTES[operation][2]
    if not fields:
        return None
    raw = stream.read(MAX_REQUEST + 1)
    if len(raw.encode('utf-8')) > MAX_REQUEST:
        raise ValueError('Owner request exceeds the size limit')
    try:
        body = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError('Owner operation requires a JSON object on standard input') from None
    if not isinstance(body, dict) or set(body) != set(fields):
        raise ValueError('Invalid owner request fields')
    return body

def request(operation, *, port, token, body=None):
    if operation not in ROUTES or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid local owner operation or port')
    method, path, fields = ROUTES[operation]
    if fields:
        if not isinstance(body, dict) or set(body) != set(fields):
            raise ValueError('Invalid owner request fields')
    elif body is not None:
        raise ValueError('Unexpected owner request body')
    if operation in ('pause', 'resume'):
        body = {'paused': operation == 'pause'}
    payload = json.dumps(body, allow_nan=False).encode('utf-8') if body is not None else None
    if payload is not None and len(payload) > MAX_REQUEST:
        raise ValueError('Owner request exceeds the size limit')
    # Direct loopback, no environment proxy, redirects or implicit mutation retry.
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=60)
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Owner response exceeds the size limit')
        if response.status != 200:
            raise ValueError('Local owner operation refused (HTTP %d)' % response.status)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('Invalid local owner response')
        return value
    except (OSError, http.client.HTTPException):
        raise ValueError('Local owner request outcome unconfirmed; inspect status before retrying') from None
    finally:
        connection.close()
