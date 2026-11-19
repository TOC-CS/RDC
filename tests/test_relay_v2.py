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
