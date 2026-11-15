"""Direct bearer HTTP MCP example; requires a running `rdc serve`.

Run with the same private state directory on this host. Uses only stdlib.
Public ChatGPT web onboarding requires OAuth and is outside this alpha.
"""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8765/mcp')
    args = parser.parse_args()
    from rdc.cli import read_secret
    token = read_secret(args.state_dir / 'agent-token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
               'Accept': 'application/json, text/event-stream'}

    def request(message):
        req = Request(args.url, json.dumps(message).encode(), headers=headers, method='POST')
        with urlopen(req, timeout=30) as response:
            if response.headers.get('mcp-session-id'):
                headers['mcp-session-id'] = response.headers['mcp-session-id']
            data = response.read()
            return json.loads(data) if data else None

    initialized = request({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                           'params': {'protocolVersion': '2025-11-25', 'capabilities': {},
                                      'clientInfo': {'name': 'rdc-example', 'version': '0.1'}}})
    headers['mcp-protocol-version'] = initialized['result']['protocolVersion']
    request({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    tools = request({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    print(json.dumps(tools, indent=2))
    if headers.get('mcp-session-id'):
        with urlopen(Request(args.url, headers=headers, method='DELETE'), timeout=30):
            pass


if __name__ == '__main__':
    main()
