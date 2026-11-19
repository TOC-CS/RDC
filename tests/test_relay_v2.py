"""RDC 2.0 WebSocket transport contracts using only disposable in-memory peers."""
import asyncio
import hashlib
import json
import time
import unittest
from rdc.relay import Operation, RelayPermanentError, RelayTransientError
from rdc.relay_v2 import V2SocketGateway, v2_socket_url

def operation(key='one'):
    raw=json.dumps({'name':'rdc_job_run','arguments':{'argv':['/bin/echo',key],
        'cwd':'/tmp'}},separators=(',',':'))
    now=int(time.time()*1000)
    return {'id':'operation-'+key,'claimId':'claim-'+key,
            'requestJson':raw,'requestDigest':hashlib.sha256(raw.encode()).hexdigest(),
            'expiresAtMs':now+30_000,'serverTimeMs':now,
            'tool':'rdc_job_run','mutating':True}

class Peer:
    def __init__(self, on_send=None):
        self.outbound=[]
        self.inbound=asyncio.Queue()
        self.on_send=on_send
    async def send(self,raw):
        msg=json.loads(raw)
        self.outbound.append(msg)
        if self.on_send:
            outcome=self.on_send(msg)
            if asyncio.iscoroutine(outcome):
                await outcome
    async def recv(self):
        msg=await self.inbound.get()
        if isinstance(msg,Exception):
            raise msg
        return json.dumps(msg) if isinstance(msg,dict) else msg
    def incoming(self,*frames):
        for item in frames:
            self.inbound.put_nowait(item)

class URLTests(unittest.TestCase):
    def test_socket_url_is_single_https_to_wss_private_path(self):
        self.assertEqual(v2_socket_url('https://private.example.test/mcp'),
                         'wss://private.example.test/v2/device/socket')
        with self.assertRaises(RelayPermanentError):
            v2_socket_url('http://private.example.test/mcp')
        with self.assertRaises(RelayPermanentError):
            v2_socket_url('https://other.example.test/path?password=bad')

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_immediate_claim_maps_to_original_durable_operation(self):
        def on_send(msg):
            if msg['type']=='claim':
                peer.incoming({'version':2,'type':'claimed','operation':operation()})
        peer=Peer(on_send)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        claimed,delay=await gateway.poll()
        self.assertIsInstance(claimed,Operation)
        self.assertEqual(claimed.operation_id,'operation-one')
        self.assertEqual(claimed.claim_id,'claim-one')
        self.assertEqual(claimed.request['name'],'rdc_job_run')
        self.assertEqual([x['type'] for x in peer.outbound],['claim'])
        self.assertEqual(delay,0)

    async def test_initial_empty_claim_waits_for_wake_then_claims_once(self):
        calls=0
        def on_send(msg):
            nonlocal calls
            if msg['type']=='claim':
                calls+=1
                if calls==1:
                    peer.incoming({'version':2,'type':'claimed','operation':None},
                                  {'version':2,'type':'work_available'})
                else:
                    peer.incoming({'version':2,'type':'claimed','operation':operation('wake')})
        peer=Peer(on_send)
        claimed,_=await V2SocketGateway(peer,wait_timeout=.05).poll()
        self.assertEqual(claimed.operation_id,'operation-wake')
        self.assertEqual(calls,2)

    async def test_idle_timeout_emits_heartbeat_without_polling(self):
        calls=0
        def on_send(msg):
            nonlocal calls
            if msg['type']=='claim':
                calls+=1
                if calls==1:
                    peer.incoming({'version':2,'type':'claimed','operation':None})
                else:
                    peer.incoming({'version':2,'type':'claimed','operation':operation('late')})
            if msg['type']=='heartbeat':
                peer.incoming({'version':2,'type':'heartbeat_ack'},
                              {'version':2,'type':'work_available'})
        peer=Peer(on_send)
        claimed,_=await V2SocketGateway(peer,wait_timeout=.01).poll()
        self.assertEqual(claimed.operation_id,'operation-late')
        self.assertIn('heartbeat',[x['type'] for x in peer.outbound])

    async def test_submit_waits_for_exact_original_result_ack_not_broadcast(self):
        peer=Peer(lambda msg: peer.incoming(
            {'version':2,'type':'result_available','id':msg['id']},
            {'version':2,'type':'result_ack','id':msg['id'],'duplicate':False}
        ) if msg['type']=='complete' else None)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        opdata=operation()
        op=Operation.from_wire({
            'operation_id':opdata['id'],'claim_id':opdata['claimId'],
            'request_json':opdata['requestJson'],'request_sha256':opdata['requestDigest'],
            'expires_at_ms':opdata['expiresAtMs']},opdata['serverTimeMs'])
        result='{"content":[{"type":"text","text":"success"}]}'
        await gateway.submit(op,result)
        sent=peer.outbound[0]
        self.assertEqual(sent['type'],'complete')
        self.assertEqual(sent['id'],op.operation_id)
        self.assertEqual(sent['resultDigest'],hashlib.sha256(result.encode()).hexdigest())

    async def test_heartbeat_only_never_claims_or_repeats_mutation(self):
        peer=Peer(lambda msg: peer.incoming({'version':2,'type':'heartbeat_ack'})
                  if msg['type']=='heartbeat' else None)
        claimed,_=await V2SocketGateway(peer,wait_timeout=.05).poll(claim=False)
        self.assertIsNone(claimed)
        self.assertEqual([x['type'] for x in peer.outbound],['heartbeat'])

    async def test_malformed_claim_wrong_sha_fails_closed(self):
        wrong=operation()
        wrong['requestDigest']='0'*64
        peer=Peer(lambda msg: peer.incoming({
            'version':2,'type':'claimed','operation':wrong}))
        with self.assertRaises(RelayPermanentError):
            await V2SocketGateway(peer,wait_timeout=.05).poll()

    async def test_disconnected_transport_is_transient_without_auto_redelivery(self):
        peer=Peer(lambda msg: peer.incoming(ConnectionError('synthetic disconnection')))
        with self.assertRaises(RelayTransientError):
            await V2SocketGateway(peer,wait_timeout=.05).poll()
        self.assertEqual(len(peer.outbound),1)

    async def test_error_frame_refuses_action_and_does_not_replay(self):
        peer=Peer(lambda msg: peer.incoming({
            'version':2,'type':'operation_error','code':'claim_mismatch'}))
        with self.assertRaises(RelayPermanentError):
            await V2SocketGateway(peer,wait_timeout=.05).poll()
        self.assertEqual(len(peer.outbound),1)

    async def test_oversized_frame_rejected_without_seeing_result(self):
        peer=Peer(lambda msg: peer.incoming('x'*1_600_000))
        with self.assertRaises(RelayPermanentError):
            await V2SocketGateway(peer,wait_timeout=.05).poll()

class BulkUploadTests(unittest.IsolatedAsyncioTestCase):
    def _original(self):
        raw=operation('bulk')
        return Operation.from_wire({
            'operation_id':raw['id'],'claim_id':raw['claimId'],
            'request_json':raw['requestJson'],
            'request_sha256':raw['requestDigest'],
            'expires_at_ms':raw['expiresAtMs']},raw['serverTimeMs'])

    def _config(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            gateway_url='https://private.example.test/mcp',
            sites_service_token='synthetic-test-site-service-2026',
            device_key='synthetic-test-device-key-2026')

    async def test_original_large_result_uses_only_authenticated_https_upload(self):
        from unittest.mock import patch
        from rdc import relay_v2
        requests=[]
        class Response:
            status_code=200
            def json(self):
                return {'ok':True,'operation_id':'operation-bulk',
                        'status':'completed','duplicate':False}
        class Client:
            def __init__(self,**kwargs):
                self.options=kwargs
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def post(self,url,*,content,headers):
                requests.append((url,content,headers))
                return Response()
        peer=Peer()
        result=json.dumps({'content':[{'type':'text','text':'P'*420_000}]})
        with patch.object(relay_v2.httpx2,'AsyncClient',Client):
            await V2SocketGateway(peer,config=self._config()).submit(self._original(),result)
        self.assertEqual(len(peer.outbound),0)
        self.assertEqual(len(requests),1)
        url,payload,headers=requests[0]
        self.assertEqual(url,'https://private.example.test/v2/device/result')
        self.assertEqual(json.loads(payload)['resultJson'],result)
        self.assertEqual(json.loads(payload)['id'],'operation-bulk')
        self.assertEqual(json.loads(payload)['resultDigest'],
                         hashlib.sha256(result.encode()).hexdigest())
        self.assertIn('X-RDC-Device-Key',headers)
        self.assertFalse('http://' in url)

    async def test_original_bulk_transport_failure_is_transient_without_replay(self):
        from unittest.mock import patch
        from rdc import relay_v2
        count=0
        class Response:
            status_code=503
        class Client:
            def __init__(self,**kwargs): pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def post(self,*args,**kwargs):
                nonlocal count
                count+=1
                return Response()
        with patch.object(relay_v2.httpx2,'AsyncClient',Client):
            with self.assertRaises(RelayTransientError):
                await V2SocketGateway(Peer(),config=self._config()).submit(
                    self._original(),json.dumps({'content':[{'text':'x'*320000}]}))
        self.assertEqual(count,1,'large upload may retry only through durable outbox')

    async def test_original_large_upload_denial_is_permanent_and_not_retried(self):
        from unittest.mock import patch
        from rdc import relay_v2
        count=0
        class Response:
            status_code=401
        class Client:
            def __init__(self,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def post(self,*args,**kwargs):
                nonlocal count
                count+=1
                return Response()
        with patch.object(relay_v2.httpx2,'AsyncClient',Client):
            with self.assertRaises(RelayPermanentError):
                await V2SocketGateway(Peer(),config=self._config()).submit(
                    self._original(),json.dumps({'content':[{'text':'x'*320000}]}))
        self.assertEqual(count,1)

    async def test_bulk_requires_explicit_private_config_not_unverified_route(self):
        with self.assertRaises(RelayPermanentError):
            await asyncio.wait_for(V2SocketGateway(Peer()).submit(
                self._original(),json.dumps({'content':[{'text':'x'*320000}]})),timeout=.1)

    async def test_beyond_twelve_megabytes_returns_explicit_original_error(self):
        peer=Peer(lambda msg: peer.incoming({
            'version':2,'type':'result_ack','id':msg['id'],'duplicate':False})
                  if msg['type']=='complete' else None)
        too_big=json.dumps({'content':[{'type':'text','text':'Q'*(13*1024*1024)}]})
        await V2SocketGateway(peer).submit(self._original(),too_big)
        self.assertEqual(len(peer.outbound),1)
        inline=peer.outbound[0]
        self.assertLess(len(inline['resultJson']),262144)
        self.assertIn('result_too_large',inline['resultJson'])
        self.assertEqual(inline['id'],'operation-bulk')
