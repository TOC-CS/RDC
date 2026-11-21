"""Opt-in local-only private V2 relay, with no weakening of remote TLS."""
import unittest

from rdc.relay import RelayConfig, RelayPermanentError
from rdc.relay_v2 import v2_socket_url, v2_result_url

PRIVATE_DEVICE='11111111-2222-4333-8444-555555555555'
PRIVATE_KEY='k'*64
LOCAL='http://127.0.0.1:18795/v2/mcp'
REMOTE='https://owner.example.invalid/v2/mcp'

class V2LocalLoopbackTransportTests(unittest.TestCase):
    def cfg(self, url=LOCAL, mode='standalone-local', **kwargs):
        return RelayConfig(gateway_url=url, device_id=PRIVATE_DEVICE,
                           device_key=PRIVATE_KEY, transport=mode, **kwargs)

    def test_explicit_single_host_mode_uses_loopback_websocket_and_http_upload(self):
        conf=self.cfg()
        self.assertEqual(conf.gateway_url,LOCAL)
        self.assertEqual(v2_socket_url(conf.gateway_url,transport=conf.transport),
                         'ws://127.0.0.1:18795/v2/device/socket')
        self.assertEqual(v2_result_url(conf.gateway_url,transport=conf.transport),
                         'http://127.0.0.1:18795/v2/device/result')

    def test_existing_tls_mode_never_downgrades_to_insecure_loopback(self):
        with self.assertRaises(RelayPermanentError):
            self.cfg(mode='standalone')
        for mode in ('sites','standalone'):
            with self.subTest(mode=mode):
                with self.assertRaises(RelayPermanentError):
                    v2_socket_url(LOCAL,transport=mode)
                with self.assertRaises(RelayPermanentError):
                    v2_result_url(LOCAL,transport=mode)
        remote=self.cfg(url=REMOTE,mode='standalone')
        self.assertEqual(v2_socket_url(remote.gateway_url),
                         'wss://owner.example.invalid/v2/device/socket')

    def test_local_transport_rejects_public_and_ambiguous_urls(self):
        bad=(
            'http://example.com:18795/v2/mcp',
            'http://127.0.0.2:18795/v2/mcp',
            'http://localhost:18795/v2/mcp',
            'http://0.0.0.0:18795/v2/mcp',
            'http://[::1]:18795/v2/mcp',
            'https://127.0.0.1:18795/v2/mcp',
            'http://127.0.0.1/v2/mcp',
            'http://127.0.0.1:18795/mcp',
            'http://127.0.0.1:18795/v2/mcp?key=secret',
            'http://127.0.0.1:18795/v2/mcp#fragment',
            'http://name:pass@127.0.0.1:18795/v2/mcp',
            'http://127.0.0.1:18795/v2/mcp%2f',
        )
        for url in bad:
            with self.subTest(url=url):
                with self.assertRaises(RelayPermanentError):
                    self.cfg(url=url)
                with self.assertRaises(RelayPermanentError):
                    v2_socket_url(url,transport='standalone-local')

    def test_local_mode_forbids_sites_service_credentials(self):
        with self.assertRaises(RelayPermanentError):
            self.cfg(sites_service_token='S'*64)
        self.assertEqual(self.cfg().sites_service_token,'')

    def test_unknown_transport_and_url_never_enable_cleartext(self):
        for mode in ('unknown','standalone-local-other','','private'):
            with self.subTest(mode=mode):
                with self.assertRaises(RelayPermanentError):
                    self.cfg(mode=mode)
                with self.assertRaises(RelayPermanentError):
                    v2_socket_url(LOCAL,transport=mode)
                with self.assertRaises(RelayPermanentError):
                    v2_result_url(LOCAL,transport=mode)

    def test_private_local_mode_still_checks_worker_and_device_identity(self):
        with self.assertRaises(RelayPermanentError):
            RelayConfig(gateway_url=LOCAL,device_id='device id with spaces',
                        device_key=PRIVATE_KEY,transport='standalone-local')
        with self.assertRaises(RelayPermanentError):
            RelayConfig(gateway_url=LOCAL,device_id=PRIVATE_DEVICE,
                        device_key='short',transport='standalone-local')
        with self.assertRaises(RelayPermanentError):
            self.cfg(worker_url='http://public.example.com:8765/mcp')

class V2LocalCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_standalone_can_register_authentic_worker_catalog(self):
        import json
        from types import SimpleNamespace
        from rdc.relay_v2 import V2SocketGateway

        class Peer:
            def __init__(self):
                self.sent=[]
            async def send(self,raw):
                self.sent.append(json.loads(raw))
            async def recv(self):
                return json.dumps({"version":2,"type":"catalog_ack","toolCount":1})

        peer=Peer()
        gateway=V2SocketGateway(
            peer,config=SimpleNamespace(transport="standalone-local"),wait_timeout=.05)
        await gateway.register_catalog({"rdc_system_status":{"type":"object","properties":{}}})
        self.assertEqual(len(peer.sent),1)
        self.assertEqual(peer.sent[0]["type"],"register_catalog")
        self.assertEqual(peer.sent[0]["tools"][0]["name"],"rdc_system_status")
