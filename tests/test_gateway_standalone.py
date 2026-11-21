"""Standalone RDC2 self-hosted gateway integration and persistence contracts."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from rdc.gateway_standalone import StandaloneGateway, DeviceSocket, create_app, initialize

def hash_result(raw):
    return hashlib.sha256(raw.encode()).hexdigest()

class StandaloneGatewayContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rdc2-standalone-")
        self.root=Path(self.tmp.name)/"state"
        initialize(self.root)
        self.state=StandaloneGateway(self.root)
        self.client_token=self.state.client_token
        self.device_token=self.state.device_token
        self.client=TestClient(create_app(self.state))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.state.db.close()
        self.tmp.cleanup()

    def auth(self):
        return {"Authorization":"Bearer "+self.client_token}

    def call(self,name,args=None,key=None):
        data={"jsonrpc":"2.0","id":"synthetic-call",
              "method":"tools/call","params":{"name":name,"arguments":args or {}}}
        return self.client.post("/v2/mcp",headers=self.auth(),json=data)

    def test_authenticated_worker_registers_real_tool_catalog(self):
        with self.client.websocket_connect("/v2/device/socket",
                    headers={"X-RDC-Device-Key":self.device_token}) as ws:
            tools=[
              {"name":"rdc_code_context","description":"Owner-scoped combined coding read.",
               "inputSchema":{"type":"object","properties":{
                   "path":{"type":"string"}},"required":["path"]}},
              {"name":"rdc_system_status","description":"Worker status.",
               "inputSchema":{"type":"object","properties":{}}}]
            ws.send_json({"version":2,"type":"register_catalog","tools":tools})
            ack=ws.receive_json()
            self.assertEqual(ack,{"version":2,"type":"catalog_ack","toolCount":2})
            reply=self.client.post("/v2/mcp",headers=self.auth(),json={
                "jsonrpc":"2.0","id":"tool-list","method":"tools/list"})
            self.assertEqual(reply.status_code,200)
            names={t["name"] for t in reply.json()["result"]["tools"]}
            self.assertIn("rdc_code_context",names)
            self.assertIn("rdc_connection_status",names)
            self.assertEqual(len(names),5)
            ws.send_json({"version":2,"type":"register_catalog","tools":[{
                "name":"rdc_connection_status","description":"collision",
                "inputSchema":{"type":"object","properties":{}}}]})
            refusal=ws.receive_json()
            self.assertEqual(refusal["type"],"operation_error")
            self.assertEqual(refusal["code"],"invalid_catalog")
            self.assertIn("rdc_code_context",{t["name"] for t in self.client.post(
                 "/v2/mcp",headers=self.auth(),json={
                   "jsonrpc":"2.0","id":"same","method":"tools/list"}).json()["result"]["tools"]})

    def test_device_pairing_at_init_requires_valid_device_uuid(self):
        other=Path(self.tmp.name)/"paired"
        wanted="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        initialize(other,device_id=wanted)
        self.assertEqual((other/"device-id").read_text().strip(),wanted)
        self.assertEqual((other/"device-id").stat().st_mode & 0o777,0o600)
        with self.assertRaises(ValueError):
            initialize(Path(self.tmp.name)/"bad-device",device_id="../my-other-device")

    def test_private_install_survives_restart_and_refuses_overwrite(self):
        self.assertNotEqual(self.client_token,self.device_token)
        for name in ("client-token","device-token","device-id"):
            self.assertEqual((self.root/name).stat().st_mode & 0o777,0o600)
        with self.assertRaises(ValueError):
            initialize(self.root)
        reopened=StandaloneGateway(self.root)
        try:
            self.assertEqual(reopened.client_token,self.client_token)
            self.assertEqual(reopened.device_id,self.state.device_id)
        finally:
            reopened.db.close()

    def test_official_mcp_modern_discovery_falls_back_to_legacy_initialize(self):
        response=self.client.post("/v2/mcp",headers=self.auth(),json={
            "jsonrpc":"2.0","id":"discover-1",
            "method":"server/discover","params":{"protocolVersion":"2026-11-25"}})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["error"]["code"],-32601)
        self.assertEqual(response.json()["id"],"discover-1")
        initialized=self.client.post("/v2/mcp",headers=self.auth(),json={
            "jsonrpc":"2.0","id":"initialize-1","method":"initialize","params":{}})
        self.assertEqual(initialized.status_code,200)
        self.assertEqual(initialized.json()["result"]["serverInfo"]["name"],"rdc-standalone")

    def test_portable_gateway_cli_uses_explicit_private_client_token_file(self):
        from rdc.cli import parser, read_secret
        tokenfile=self.root/"client-token"
        args=parser().parse_args(["gateway-connect","--url",
              "https://rdc.example.test/v2/mcp","--token-file",str(tokenfile)])
        self.assertEqual(args.command,"gateway-connect")
        self.assertEqual(args.url,"https://rdc.example.test/v2/mcp")
        self.assertEqual(read_secret(args.token_file),self.client_token)
        with self.assertRaises(SystemExit):
            parser().parse_args(["gateway-connect","--url",
                                 "https://rdc.example.test/v2/mcp"])

    def test_standalone_relay_configuration_needs_no_sites_credentials(self):
        from rdc.relay import RelayConfig, RelayPermanentError
        base={"gateway_url":"https://standalone.example.test/v2/mcp",
              "device_id":self.state.device_id,"device_key":self.device_token}
        config=RelayConfig(**base,transport="standalone")
        self.assertEqual(config.sites_service_token,"")
        with self.assertRaises(RelayPermanentError):
            RelayConfig(**base)
        with self.assertRaises(RelayPermanentError):
            RelayConfig(**base,transport="standalone",
                        sites_service_token="unnecessary-sites-credential-"+"x"*40)
        with self.assertRaises(RelayPermanentError):
            RelayConfig(**base,transport="unknown")
        malformed=self.client.post("/v2/mcp",content=b"{bad json",
              headers={**self.auth(),"Content-Type":"application/json"})
        self.assertEqual(malformed.status_code,400)
        self.assertEqual(malformed.json()["error"]["data"]["code"],"invalid_request")
        oversized=self.client.post("/v2/mcp",content=b"x"*(1_048_576+1),
              headers={**self.auth(),"Content-Type":"application/json"})
        self.assertEqual(oversized.status_code,413,
            "unauthenticated or oversized message must not be buffered or parsed")

    def test_owner_authentication_and_offline_admission(self):
        reply=self.client.post("/v2/mcp",json={"jsonrpc":"2.0","id":1,
            "method":"tools/list"},headers={"Authorization":"Bearer incorrect"})
        self.assertEqual(reply.status_code,401)
        self.assertEqual(self.call("rdc_connection_status").json()["result"]["structuredContent"]["online"],False)
        offline=self.call("rdc_job_run",{"argv":["/bin/echo","fix"],"cwd":"/tmp",
                       "_rdc_request_id":"offline"})
        self.assertEqual(offline.status_code,503)
        self.assertEqual(offline.json()["error"]["data"]["code"],"device_offline")
        self.assertEqual(self.state.row("SELECT count(*) AS n FROM operations")["n"],0)

    def test_exact_claim_result_and_duplicate_never_reexecutes(self):
        with self.client.websocket_connect("/v2/device/socket",
                    headers={"X-RDC-Device-Key":self.device_token}) as ws:
            ws.send_json({"version":2,"type":"heartbeat"})
            heartbeat=ws.receive_json()
            self.assertTrue(heartbeat["claimWaitSupported"])
            ws.send_json({"version":2,"type":"claim_wait"})
            args={"argv":["/bin/echo","safe-synthetic"],"cwd":"/tmp",
                  "_rdc_request_id":"original-key"}
            with ThreadPoolExecutor(max_workers=1) as pool:
                answer=pool.submit(self.call,"rdc_job_run",args)
                claimed=ws.receive_json()
                self.assertEqual(claimed["type"],"claimed")
                op=claimed["operation"]
                self.assertEqual(op["requestJson"].count("safe-synthetic"),1)
                content=json.dumps({"content":[{"type":"text","text":"original-result"}],
                                    "structuredContent":{"ok":True,"output":"original-result"}})
                ws.send_json({"version":2,"type":"complete","id":op["id"],
                              "claimId":op["claimId"],"requestDigest":op["requestDigest"],
                              "resultJson":content,"resultDigest":hash_result(content)})
                receipt=ws.receive_json()
                self.assertEqual(receipt["type"],"result_ack")
                result=answer.result(timeout=8)
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()["result"]["structuredContent"]["output"],"original-result")
            duplicate=self.call("rdc_job_run",args)
            self.assertEqual(duplicate.json()["result"]["structuredContent"]["output"],"original-result")
            self.assertEqual(self.state.row("SELECT count(*) AS n FROM operations")["n"],1)
            conflict=self.call("rdc_job_run",{**args,"argv":["/bin/echo","changed"]})
            self.assertEqual(conflict.status_code,409)
            metrics=self.call("rdc_recent_operation_metrics",{"limit":30})
            self.assertEqual(metrics.status_code,200)
            view=metrics.json()["result"]["structuredContent"]
            self.assertEqual(view["sampleCount"],1)
            self.assertEqual(view["validSampleCount"],1)
            self.assertEqual(view["invalidSampleCount"],0)
            self.assertEqual(view["samples"][0]["operationId"],op["id"])
            self.assertGreaterEqual(view["samples"][0]["queuePickupMs"],0)
            self.assertGreaterEqual(view["samples"][0]["claimToResultMs"],0)
            self.assertIn("gatewaySendMs",view["samples"][0])
            self.assertGreaterEqual(view["samples"][0]["gatewaySendMs"],0)
            self.assertNotIn("original-result",metrics.text)

    def test_lost_connection_preserves_original_claim_on_restart(self):
        with self.client.websocket_connect("/v2/device/socket",
                    headers={"X-RDC-Device-Key":self.device_token}) as ws:
            ws.send_json({"version":2,"type":"heartbeat"})
            ws.receive_json()
            ws.send_json({"version":2,"type":"claim"})
            self.assertIsNone(ws.receive_json()["operation"])
            self.state.enqueue("durable-id",json.dumps({"name":"rdc_job_run",
                "arguments":{"argv":["/bin/echo","once"],"cwd":"/tmp"}}),
                "rdc_job_run",True)
            ws.send_json({"version":2,"type":"claim"})
            original=ws.receive_json()["operation"]
            self.assertEqual(self.state.recover(original["id"])["state"],"claimed")
        restarted=StandaloneGateway(self.root)
        try:
            self.assertEqual(restarted.recover(original["id"])["state"],"claimed")
            self.assertIsNone(restarted.claim(),"unknown original must never be claimed again")
        finally:
            restarted.db.close()

    def test_large_result_private_file_and_original_recovery(self):
        with self.client.websocket_connect("/v2/device/socket",
                    headers={"X-RDC-Device-Key":self.device_token}) as ws:
            ws.send_json({"version":2,"type":"heartbeat"})
            ws.receive_json()
            raw=json.dumps({"name":"rdc_job_run","arguments":{"cwd":"/tmp","argv":["/bin/echo","bulktest"]}})
            opid,_=self.state.enqueue("bulk-1",raw,"rdc_job_run",True)
            ws.send_json({"version":2,"type":"claim"})
            op=ws.receive_json()["operation"]
            self.assertEqual(op["id"],opid)
            result=json.dumps({"content":[{"type":"text","text":"K"*300_000}]})
            data={"id":op["id"],"claimId":op["claimId"],"requestDigest":op["requestDigest"],
                  "resultJson":result,"resultDigest":hash_result(result)}
            bad=self.client.post("/v2/device/result",json=data,
                                 headers={"X-RDC-Device-Key":"wrong"})
            self.assertEqual(bad.status_code,401)
            saved=self.client.post("/v2/device/result",json=data,
                                   headers={"X-RDC-Device-Key":self.device_token})
            self.assertEqual(saved.status_code,200)
            self.assertFalse(saved.json()["duplicate"])
            self.assertIsNone(next(iter(self.state.sockets)).active,
                "HTTP bulk completion must free the exact claimant for its next job")
            self.assertEqual(self.state.recover(opid)["resultJson"],result)
            again=self.client.post("/v2/device/result",json=data,
                                   headers={"X-RDC-Device-Key":self.device_token})
            self.assertTrue(again.json()["duplicate"])
            self.assertEqual(len(list((self.root/"results").glob("*.json"))),1)


    def _completed_trace(self, *, backward_clock=False):
        socket=DeviceSocket(None)
        self.state.sockets.add(socket)
        base=self.state.clock()
        self.state.last_heartbeat=base
        data=json.dumps({"name":"rdc_job_run",
                         "arguments":{"argv":["/bin/echo","trace-secret-never-reveal"],
                                      "cwd":"/tmp"}})
        op_id,fresh=self.state.enqueue("trace-original-key",data,"rdc_job_run",True)
        self.assertTrue(fresh)
        if backward_clock:
            self.state.clock=lambda:base-1
        claimed=self.state.claim()
        self.assertEqual(claimed["id"],op_id)
        if backward_clock:
            self.state.clock=lambda:base-2
        raw=json.dumps({"content":[{"type":"text","text":"private trace output"}],
                        "structuredContent":{"ok":True}})
        args={"id":op_id,"claimId":claimed["claimId"],
              "requestDigest":claimed["requestDigest"],"resultJson":raw,
              "resultDigest":hash_result(raw)}
        complete=self.state.complete(args)
        self.assertFalse(complete["duplicate"])
        return op_id,args

    def test_monotonic_gateway_phases_are_precise_and_duplicate_safe(self):
        op_id,args=self._completed_trace()
        metric=self.state.phase_metrics()["samples"][0]
        self.assertEqual(metric["operationId"],op_id)
        self.assertIsInstance(metric["monotonicQueuePickupMs"],float)
        self.assertIsInstance(metric["monotonicClaimToResultMs"],float)
        self.assertGreaterEqual(metric["monotonicQueuePickupMs"],0.0)
        self.assertGreaterEqual(metric["monotonicClaimToResultMs"],0.0)
        self.assertTrue(self.state.complete(args)["duplicate"])
        again=self.state.phase_metrics()["samples"][0]
        self.assertEqual(again["monotonicClaimToResultMs"],
                         metric["monotonicClaimToResultMs"],
                         "same original operation cannot have its first timing overwritten")
        self.assertNotIn("private trace output",str(metric))
        self.assertNotIn("trace-secret-never-reveal",str(metric))

    def test_monotonic_phases_stay_valid_when_wall_clock_regresses_and_restart_nulls(self):
        original,_=self._completed_trace(backward_clock=True)
        before=self.state.phase_metrics()["samples"][0]
        self.assertEqual(before["operationId"],original)
        self.assertEqual(before["timingStatus"],"invalid_clock_order")
        self.assertGreaterEqual(before["monotonicQueuePickupMs"],0)
        self.assertGreaterEqual(before["monotonicClaimToResultMs"],0)
        rebooted=StandaloneGateway(self.root)
        try:
            after=rebooted.phase_metrics()["samples"][0]
            self.assertEqual(after["operationId"],original)
            self.assertIsNone(after["monotonicQueuePickupMs"])
            self.assertIsNone(after["monotonicClaimToResultMs"])
        finally:
            rebooted.db.close()

    def test_monotonic_phase_ring_eviction_is_bounded_without_replaying_work(self):
        for i in range(512):
            self.state.phase_ns["historical-"+str(i)]=[i,i,i]
        socket=DeviceSocket(None)
        self.state.sockets.add(socket)
        self.state.last_heartbeat=self.state.clock()
        operation,_=self.state.enqueue(
            "new-original",json.dumps({"name":"rdc_job_run",
                "arguments":{"cwd":"/tmp","argv":["/bin/echo","one"]}}),
            "rdc_job_run",True)
        self.assertEqual(len(self.state.phase_ns),512)
        self.assertNotIn("historical-0",self.state.phase_ns)
        self.assertIn(operation,self.state.phase_ns)


    def test_standalone_requires_websocket_backend_before_serving(self):
        from rdc import gateway_standalone as gateway
        with patch('rdc.gateway_standalone.importlib.import_module',
                   return_value=object()) as load:
            self.assertTrue(gateway.require_websocket_backend())
        load.assert_called_once_with('websockets.asyncio.server')

    def test_missing_websocket_backend_fails_closed_with_install_hint(self):
        from rdc import gateway_standalone as gateway
        with patch('rdc.gateway_standalone.importlib.import_module',
                   side_effect=ModuleNotFoundError('websockets missing')):
            with self.assertRaisesRegex(RuntimeError,'rdc\\[v2\\]'):
                gateway.require_websocket_backend()

    def test_cli_server_refuses_to_become_healthy_without_websocket(self):
        import sys
        from rdc import gateway_standalone as gateway
        args=['rdc-standalone-gateway','serve','--state-dir',str(self.root),
              '--port','18795']
        with (patch.object(sys,'argv',args),
              patch('rdc.gateway_standalone.require_websocket_backend',
                    side_effect=RuntimeError('missing WebSocket transport')),
              patch('uvicorn.run') as serve):
            with self.assertRaisesRegex(RuntimeError,'missing WebSocket'):
                gateway.main()
        serve.assert_not_called()

if __name__=="__main__":
    unittest.main()
