"""RDC Codex local MCP registration must stay private and reversible."""
from pathlib import Path
import json
import os
import stat
import sys
import tempfile
import unittest

from scripts.rdc_setup_codex_local import build_local_codex_registration


class CodexLocalSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rdc-codex-setup-')
        self.root=Path(self.temp.name)
        self.state=self.root/'authorized-worker'
        self.state.mkdir(mode=0o700)
        self.token=self.state/'agent-token'
        self.token.write_text('FIXTURE-DO-NOT-READ-OR-REPORT')
        self.token.chmod(0o600)
        self.config=self.state/'config.json'
        self.config.write_text(json.dumps({
            'state_dir':str(self.state),
            'roots':[str(self.root)],
            'access_mode':'workspace'}))
        self.config.chmod(0o600)
        self.source=self.root/'source'
        (self.source/'rdc').mkdir(parents=True)
        (self.source/'rdc/cli.py').write_text('pass\n')

    def tearDown(self):
        self.temp.cleanup()

    def plan(self,**kwargs):
        options=dict(
            state_dir=self.state,
            worker_url='http://127.0.0.1:18791/mcp',
            alias='rdc2-fast-local',
            python=sys.executable,
            source_root=self.source,
        )
        options.update(kwargs)
        return build_local_codex_registration(**options)

    def test_builds_exact_local_stdio_command_without_reading_private_token(self):
        plan=self.plan()
        self.assertEqual(plan['alias'],'rdc2-fast-local')
        argv=plan['argv']
        self.assertEqual(argv[:3],['codex','mcp','add'])
        self.assertIn('PYTHONPATH='+str(self.source),argv)
        self.assertEqual(argv[-2:],['--timeout','15'])
        self.assertIn(str(self.state),argv)
        self.assertIn('http://127.0.0.1:18791/mcp',argv)
        self.assertNotIn('FIXTURE-DO-NOT-READ-OR-REPORT',str(plan))
        self.assertNotIn('agent-token',str(argv))

    def test_rejects_public_ambiguous_and_credential_bearing_endpoints(self):
        for url in ('http://example.com:18791/mcp',
                    'https://127.0.0.1:18791/mcp',
                    'http://localhost:18791/mcp',
                    'http://127.0.0.2:18791/mcp',
                    'http://127.0.0.1/mcp',
                    'http://127.0.0.1:18791/wrong',
                    'http://alice:pw@127.0.0.1:18791/mcp',
                    'http://127.0.0.1:18791/mcp?secret=yes',
                    'http://127.0.0.1:18791/mcp#bad',
                    'http://127.0.0.1:18791/mcp%2f'):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.plan(worker_url=url)

    def test_rejects_exposed_or_symlinked_agent_token(self):
        self.token.chmod(0o644)
        with self.assertRaises(ValueError):
            self.plan()
        self.token.chmod(0o600)
        alias=self.state/'agent-copy'
        alias.symlink_to(self.token)
        self.token.unlink()
        (self.state/'agent-token').symlink_to(alias)
        with self.assertRaises(ValueError):
            self.plan()

    def test_apply_refuses_to_replace_an_existing_codex_alias(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.rdc_setup_codex_local import install_if_absent

        plan=self.plan()
        with (patch('scripts.rdc_setup_codex_local.shutil.which',
                    return_value='/usr/local/bin/codex'),
              patch('scripts.rdc_setup_codex_local.subprocess.run',
                    return_value=SimpleNamespace(returncode=0)) as cmd):
            with self.assertRaisesRegex(RuntimeError,'already exists'):
                install_if_absent(plan)
        self.assertEqual(cmd.call_count,1)
        self.assertEqual(cmd.call_args.args[0],
                         ['codex','mcp','get','rdc2-fast-local'])

    def test_rejects_invalid_alias_and_unpaired_state(self):
        with self.assertRaises(ValueError):
            self.plan(alias='rdc2 local && execute')
        self.config.write_text(json.dumps({'state_dir':'/unrelated',
                                           'roots':[str(self.root)]}))
        with self.assertRaises(ValueError):
            self.plan()


if __name__=='__main__':
    unittest.main()
