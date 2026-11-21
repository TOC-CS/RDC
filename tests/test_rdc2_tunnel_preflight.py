"""Fail-closed, secret-free private MCP tunnel readiness contracts."""
import os
from pathlib import Path
import tempfile
import unittest

from scripts.rdc2_tunnel_preflight import inspect_tunnel_config


class TunnelPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rdc2-tunnel-readiness-')
        self.base=Path(self.tmp.name)
        self.runtime=self.base/'runtime.key'
        self.client=self.base/'client-token'
        self.binary=self.base/'tunnel-client'
        for item in (self.runtime,self.client):
            item.write_text('PRIVATE NEVER READ OR DISCLOSE '+item.name)
            item.chmod(0o600)
        self.binary.write_text('#!/bin/sh\nexit 0\n')
        self.binary.chmod(0o700)
        self.config={
           'tunnel_id':'tunnel_0123456789abcdef0123456789abcdef',
           'mcp_server_url':'http://127.0.0.1:18786/v2/mcp',
           'runtime_key_file':str(self.runtime),
           'gateway_client_token_file':str(self.client)
        }
    def tearDown(self):
        self.tmp.cleanup()

    def check(self,**kwargs):
        return inspect_tunnel_config({**self.config,**kwargs},binary=str(self.binary))

    def test_ready_only_with_owner_private_local_credentials_and_executable(self):
        result=self.check()
        self.assertTrue(result['ready'])
        self.assertEqual(result['blockers'],[])
        self.assertEqual(result['transport'],'owner-private-outbound-tunnel')

    def test_rejects_public_endpoint_userinfo_query_and_wrong_route(self):
        for url in ('https://example.com/v2/mcp',
                    'http://127.0.0.1:18786/mcp',
                    'http://user:pw@127.0.0.1:18786/v2/mcp',
                    'http://127.0.0.1:18786/v2/mcp?token=secret',
                    'http://127.0.0.1:18786/v2/mcp#bad',
                    'http://localhost.evil.test:18786/v2/mcp'):
            with self.subTest(url=url):
                self.assertFalse(self.check(mcp_server_url=url)['ready'])

    def test_rejects_missing_and_malformed_tunnel_identity(self):
        for value in ('','not-a-tunnel','tunnel_short','tunnel_@@@'):
            with self.subTest(value=value):
                self.assertFalse(self.check(tunnel_id=value)['ready'])

    def test_rejects_credential_symlink_world_readable_and_missing_files(self):
        self.runtime.chmod(0o644)
        self.assertFalse(self.check()['ready'])
        self.runtime.chmod(0o600)
        link=self.base/'linked.key'
        link.symlink_to(self.runtime)
        self.assertFalse(self.check(runtime_key_file=str(link))['ready'])
        self.assertFalse(self.check(runtime_key_file=str(self.base/'missing'))['ready'])

    def test_runtime_and_gateway_client_keys_must_be_different_paths(self):
        self.assertFalse(self.check(gateway_client_token_file=str(self.runtime))['ready'])

    def test_no_secret_content_or_private_path_is_returned_in_diagnostics(self):
        text=str(self.check())
        self.assertNotIn('PRIVATE NEVER READ',text)
        self.assertNotIn(str(self.runtime),text)
        self.assertNotIn(str(self.client),text)
        self.assertNotIn('0123456789abcdef',text)

    def test_missing_or_nonexecutable_client_blocks_activation(self):
        self.binary.chmod(0o600)
        self.assertFalse(self.check()['ready'])
        self.assertFalse(inspect_tunnel_config(self.config,binary='missing-client')['ready'])

    def test_cli_refuses_symlink_to_private_config_file(self):
        import io
        import json
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from scripts.rdc2_tunnel_preflight import main
        original=self.base/'owner-config.json'
        original.write_text(json.dumps(self.config)+'\n')
        original.chmod(0o600)
        link=self.base/'linked-config.json'
        link.symlink_to(original)
        output=io.StringIO()
        with patch('sys.argv',['rdc2_tunnel_preflight',
                '--config',str(link),'--binary',str(self.binary)]),redirect_stdout(output):
            result=main()
        self.assertEqual(result,2)
        self.assertNotIn(str(original),output.getvalue())
        self.assertNotIn(str(self.runtime),output.getvalue())
