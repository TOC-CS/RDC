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

class RegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_standalone_registers_capped_worker_catalog_with_exact_ack(self):
        from types import SimpleNamespace
        catalog={"rdc_system_status":{"type":"object","properties":{}},
                 "rdc_code_context":{"type":"object","properties":{
                     "path":{"type":"string"}},"required":["path"]}}
        peer=Peer(lambda msg: peer.incoming({
            "version":2,"type":"catalog_ack","toolCount":2})
            if msg["type"]=="register_catalog" else None)
        gateway=V2SocketGateway(peer,config=SimpleNamespace(transport="standalone"),
                                wait_timeout=.05)
        await gateway.register_catalog(catalog)
        self.assertEqual(peer.outbound[0]["type"],"register_catalog")
        self.assertEqual({tool["name"] for tool in peer.outbound[0]["tools"]},
                         set(catalog))
        site=V2SocketGateway(Peer(),config=SimpleNamespace(transport="sites"))
        with self.assertRaises(RelayPermanentError):
            await site.register_catalog(catalog)
        self.assertFalse(site.socket.outbound,
                         "private ChatGPT Site may never receive standalone catalog messages")

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

class LatencyClaimWaitTests(unittest.IsolatedAsyncioTestCase):
    async def test_advertised_claim_wait_accepts_original_without_extra_roundtrip(self):
        def on_send(frame):
            if frame['type']=='heartbeat':
                peer.incoming({'version':2,'type':'heartbeat_ack',
                               'claimWaitSupported':True})
            elif frame['type']=='claim_wait':
                peer.incoming({'version':2,'type':'claimed',
                               'operation':operation('fast')})
        peer=Peer(on_send)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        await gateway.poll(claim=False)
        claimed,_=await asyncio.wait_for(gateway.poll(),.3)
        self.assertEqual(claimed.operation_id,'operation-fast')
        self.assertEqual([item['type'] for item in peer.outbound],
                         ['heartbeat','claim_wait'])

class ClaimWaitRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_restarted_actor_loses_credit_but_work_hint_re_registers_claim_wait(self):
        credits=0
        def on_send(frame):
            nonlocal credits
            if frame['type']=='heartbeat':
                peer.incoming({'version':2,'type':'heartbeat_ack',
                               'claimWaitSupported':True})
            elif frame['type']=='claim_wait':
                credits+=1
                if credits==1:
                    peer.incoming({'version':2,'type':'work_available'})
                else:
                    peer.incoming({'version':2,'type':'claimed',
                                   'operation':operation('restored')})
        peer=Peer(on_send)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        await gateway.poll(claim=False)
        claimed,_=await asyncio.wait_for(gateway.poll(),.4)
        self.assertEqual(claimed.operation_id,'operation-restored')
        self.assertEqual(credits,2)
        self.assertEqual([x['type'] for x in peer.outbound],
                         ['heartbeat','claim_wait','claim_wait'])

    async def test_old_v2_server_without_capability_retains_legacy_explicit_claim(self):
        def on_send(frame):
            if frame['type']=='heartbeat':
                peer.incoming({'version':2,'type':'heartbeat_ack'})
            elif frame['type']=='claim':
                peer.incoming({'version':2,'type':'claimed',
                               'operation':operation('legacy')})
        peer=Peer(on_send)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        await gateway.poll(claim=False)
        claimed,_=await asyncio.wait_for(gateway.poll(),.4)
        self.assertEqual(claimed.operation_id,'operation-legacy')
        self.assertEqual([x['type'] for x in peer.outbound],['heartbeat','claim'])

class IndependentHeartbeatTests(unittest.IsolatedAsyncioTestCase):
    async def test_v2_heartbeat_hint_sends_without_stealing_result_receiver(self):
        peer=Peer()
        gateway=V2SocketGateway(peer,wait_timeout=.03)
        await asyncio.wait_for(gateway.heartbeat_hint(),.1)
        self.assertEqual([x['type'] for x in peer.outbound],['heartbeat'])
        self.assertTrue(peer.inbound.empty(),
                        'No receive required for the send-only heartbeat')

    async def test_v2_relay_background_heartbeat_avoids_second_websocket_reader(self):
        import anyio
        from rdc.relay import RelayPump
        class HeartbeatTransport:
            supports_activity_observer=False
            heartbeat_interval=.01
            def __init__(self):self.sent=0;self.polled=0
            async def heartbeat_hint(self):self.sent+=1
            async def poll(self,claim=False):
                self.polled+=1
                raise AssertionError('Background heartbeat stole the WebSocket reader')
        gateway=HeartbeatTransport()
        pump=RelayPump(None,None,gateway,None,{})
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(pump._heartbeat)
            await anyio.sleep(.045)
            tasks.cancel_scope.cancel()
        self.assertGreaterEqual(gateway.sent,3)
        self.assertEqual(gateway.polled,0)

class V2HeartbeatDuringExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_worker_receives_exact_result_ack_after_unread_heartbeats(self):
        import tempfile
        from pathlib import Path
        from rdc.relay import Journal, RelayConfig, RelayPump
        from mcp import types

        sent=[]
        def on_send(frame):
            sent.append(frame['type'])
            if frame['type']=='heartbeat':
                peer.incoming({'version':2,'type':'heartbeat_ack'})
            elif frame['type']=='complete':
                peer.incoming({'version':2,'type':'result_ack',
                    'id':frame['id'],'duplicate':False})
        peer=Peer(on_send)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        gateway.heartbeat_interval=.01
        raw=operation('slow')
        op=Operation.from_wire({
          'operation_id':raw['id'],'claim_id':raw['claimId'],
          'request_json':raw['requestJson'],
          'request_sha256':raw['requestDigest'],
          'expires_at_ms':raw['expiresAtMs'],
        },raw['serverTimeMs'])
        cfg=RelayConfig(gateway_url='https://fixture-only.invalid/mcp',
            device_id='device-test',
            device_key='synthetic-device-auth-for-tests-20261119',
            sites_service_token='synthetic-site-auth-for-tests-20261119')
        class SlowWorker:
            calls=0
            async def call_tool(self,name,args,**kwargs):
                self.calls+=1
                await asyncio.sleep(.065)
                return types.CallToolResult(
                    content=[types.TextContent(type='text',text='SLOW_OK')],
                    structured_content={'ok':True})
        worker=SlowWorker()
        catalog={'rdc_job_run':{'type':'object','properties':{
            'argv':{'type':'array','items':{'type':'string'}},
            'cwd':{'type':'string'}},
            'required':['argv','cwd']}}
        with tempfile.TemporaryDirectory(prefix='rdc2-heartbeat-journal-') as tmp:
            journal=Journal(Path(tmp)/'local.sqlite3','synthetic-binding')
            try:
                pump=RelayPump(cfg,journal,gateway,worker,catalog)
                await pump.handle(op)
                await pump.flush()
                self.assertEqual(journal.get(op.operation_id)['state'],'delivered')
            finally:
                journal.close()
        self.assertEqual(worker.calls,1)
        self.assertGreaterEqual(sent.count('heartbeat'),3)
        self.assertEqual(sent.count('complete'),1)
        self.assertEqual(gateway.supports_claim_wait,False)


class QuietHeartbeatBackpressureTests(unittest.IsolatedAsyncioTestCase):
    async def test_negotiated_quiet_heartbeat_does_not_fill_unread_socket(self):
        """A 20 minute command sends 80 liveness hints at 15s, without ACK fanout."""
        peer=Peer(lambda frame: peer.incoming({'version':2,'type':'heartbeat_ack',
                          'claimWaitSupported':True,'heartbeatNoAckSupported':True})
                  if frame['type']=='heartbeat' else None)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        await gateway.poll(claim=False)
        self.assertTrue(gateway.supports_no_ack_heartbeat)
        self.assertTrue(peer.inbound.empty())
        for _ in range(80):
            await gateway.heartbeat_hint()
        self.assertEqual([m['type'] for m in peer.outbound],
                         ['heartbeat']+['heartbeat_no_ack']*80)
        self.assertEqual(peer.inbound.qsize(),0,'Long commands must not accumulate ACKs')

    async def test_older_actor_without_quiet_heartbeat_capability_still_works(self):
        peer=Peer(lambda frame: peer.incoming({'version':2,'type':'heartbeat_ack',
                                               'claimWaitSupported':True})
                  if frame['type']=='heartbeat' else None)
        gateway=V2SocketGateway(peer,wait_timeout=.05)
        await gateway.poll(claim=False)
        self.assertFalse(gateway.supports_no_ack_heartbeat)
        await gateway.heartbeat_hint()
        self.assertEqual([m['type'] for m in peer.outbound],
                         ['heartbeat','heartbeat'])

class LostWorkHintRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_lost_wake_and_lost_actor_credit_re_registers_original_claim(self):
        """No work_available arrives after actor hibernation, so idle refresh must reconcile."""
        credits=0
        def on_send(frame):
            nonlocal credits
            if frame['type']=='heartbeat':
                peer.incoming({'version':2,'type':'heartbeat_ack',
                               'claimWaitSupported':True,
                               'heartbeatNoAckSupported':True})
            elif frame['type']=='claim_wait':
                credits+=1
                if credits==2:
                    peer.incoming({'version':2,'type':'claimed',
                                   'operation':operation('after-lost-hint')})
        peer=Peer(on_send)
        gateway=V2SocketGateway(peer,wait_timeout=.02)
        await gateway.poll(claim=False)
        claimed,_=await asyncio.wait_for(gateway.poll(),.24)
        self.assertEqual(claimed.operation_id,'operation-after-lost-hint')
        self.assertEqual(credits,2,
            'initial and one timeout recovery claim only; never a new operation ID')
        self.assertEqual([item['type'] for item in peer.outbound].count('heartbeat'),2)
        self.assertFalse(any(item['type']=='claim' for item in peer.outbound))

    async def test_idle_claim_refresh_never_reissues_mutating_worker_job(self):
        """When a pending credit already exists, repeated claim_wait is a no-op."""
        state={'registered':False,'claimed':False,'reissues':0}
        def on_send(frame):
            if frame['type']=='heartbeat':
                peer.incoming({'version':2,'type':'heartbeat_ack',
                               'claimWaitSupported':True})
            if frame['type']=='claim_wait':
                state['reissues']+=1
                state['registered']=True
                if state['reissues']==3:
                    state['claimed']=True
                    peer.incoming({'version':2,'type':'claimed',
                                   'operation':operation('idempotent-credit')})
        peer=Peer(on_send)
        gateway=V2SocketGateway(peer,wait_timeout=.012)
        await gateway.poll(claim=False)
        claimed,_=await asyncio.wait_for(gateway.poll(),.18)
        self.assertEqual(claimed.operation_id,'operation-idempotent-credit')
        self.assertEqual(state['reissues'],3)
        self.assertTrue(state['claimed'])
