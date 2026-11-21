"""Bounded standalone RDC V2 live-localhost gateway-to-device benchmark.

This test requires a disposable single-operator, loopback-only standalone
gateway. It never exercises the live ChatGPT Site, installed iMac relay, or
private TOC applications. 30 exact /bin/echo subprocesses, no shell expansion.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from websockets.asyncio.client import connect
import httpx

TOTAL=30
HOST="http://127.0.0.1:18782"
SOCKET="ws://127.0.0.1:18782/v2/device/socket"

def percentile(samples,p):
    seq=sorted(samples)
    n=(len(seq)-1)*p
    i=int(n)
    return round(seq[i]+(seq[min(len(seq)-1,i+1)]-seq[i])*(n-i),3)

async def main(root):
    state=Path(root)
    owner=(state/"client-token").read_text().strip()
    device=(state/"device-token").read_text().strip()
    assert owner!=device and len(owner)>=40 and len(device)>=40
    async with httpx.AsyncClient(trust_env=False,timeout=8) as client:
        async def rpc(name,args,request_id):
            return await client.post(HOST+"/v2/mcp",headers={"Authorization":"Bearer "+owner},
                json={"jsonrpc":"2.0","id":request_id,
                      "method":"tools/call","params":{"name":name,"arguments":args}})
        denied=await client.post(HOST+"/v2/mcp",headers={"Authorization":"Bearer incorrect"},
            json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
        assert denied.status_code==401
        async with connect(SOCKET,additional_headers={"X-RDC-Device-Key":device},
                           proxy=None,compression=None,max_size=1_572_864) as socket:
            await socket.send(json.dumps({"version":2,"type":"heartbeat"}))
            ack=json.loads(await socket.recv())
            assert ack.get("claimWaitSupported") is True
            await socket.send(json.dumps({"version":2,"type":"claim_wait"}))
            actual=[]
            async def process_operations():
                for n in range(TOTAL):
                    while True:
                        frame=json.loads(await asyncio.wait_for(socket.recv(),5))
                        if frame["type"]=="claimed":
                            break
                        assert frame["type"] in ("heartbeat_ack","work_available","result_available")
                    op=frame["operation"]
                    request=json.loads(op["requestJson"])
                    argv=request["arguments"]["argv"]
                    expected="RDC-VPS-LOCAL-"+str(n)
                    assert argv==["/bin/echo",expected],"unexpected or replayed command"
                    assert request["name"]=="rdc_job_run"
                    raw=op["requestJson"]
                    assert hashlib.sha256(raw.encode()).hexdigest()==op["requestDigest"]
                    proc=await asyncio.create_subprocess_exec(
                        "/bin/echo",expected,
                        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                    out,err=await proc.communicate()
                    assert proc.returncode==0 and err==b"" and out.decode().strip()==expected
                    actual.append(expected)
                    content=json.dumps({"content":[{"type":"text","text":expected}],
                                        "structuredContent":{"ok":True,"output":expected}},
                                       separators=(",",":"))
                    await socket.send(json.dumps({
                        "version":2,"type":"complete","id":op["id"],
                        "claimId":op["claimId"],"requestDigest":op["requestDigest"],
                        "resultJson":content,
                        "resultDigest":hashlib.sha256(content.encode()).hexdigest()
                    }))
                    while True:
                        receipt=json.loads(await asyncio.wait_for(socket.recv(),5))
                        if receipt["type"]=="result_ack":break
                        assert receipt["type"] in ("result_available","work_available")
                    assert receipt["id"]==op["id"] and receipt["duplicate"] is False
                    if n+1<TOTAL:
                        await socket.send(json.dumps({"version":2,"type":"claim_wait"}))
            task=asyncio.create_task(process_operations())
            latency=[]
            for n in range(TOTAL):
                expected="RDC-VPS-LOCAL-"+str(n)
                started=time.perf_counter()
                answer=await rpc("rdc_job_run",{
                    "argv":["/bin/echo",expected], "cwd":"/tmp",
                    "_rdc_request_id":"vps-v2-benchmark-"+str(n)
                },n)
                elapsed=(time.perf_counter()-started)*1000
                assert answer.status_code==200,(answer.status_code,answer.text[:260])
                data=answer.json()["result"]["structuredContent"]
                assert data["ok"] is True and data["output"]==expected, data
                latency.append(round(elapsed,3))
            await asyncio.wait_for(task,8)
            assert len(actual)==TOTAL
            # Exact duplicate must return retained original without reexecution.
            prior=await rpc("rdc_job_run",{
                "argv":["/bin/echo","RDC-VPS-LOCAL-0"], "cwd":"/tmp",
                "_rdc_request_id":"vps-v2-benchmark-0"
            },"same")
            assert prior.status_code==200
            assert prior.json()["result"]["structuredContent"]["output"]=="RDC-VPS-LOCAL-0"
            assert len(actual)==TOTAL
            status=await rpc("rdc_connection_status",{},"status")
            assert status.status_code==200
            x=status.json()["result"]["structuredContent"]
            assert x["online"] is True and x["transport"]=="standalone"
            report={"scope":"VPS-localhost-standalone-gateway-to-real-Python-device-simulation",
                    "platform":"Linux","host":"127.0.0.1:18782",
                    "sites_dependency":False,"tested_executables":["/bin/echo"],
                    "samples":TOTAL,"correct":len(actual),"replays":0,
                    "cloud_requests_per_command":1,"median_ms":percentile(latency,.5),
                    "p95_ms":percentile(latency,.95),"p99_ms":percentile(latency,.99),
                    "min_ms":min(latency),"max_ms":max(latency),
                    "source":"isolated-standalone-VPS-v2",
                    "note":"VPS localhost, not public TLS or ChatGPT hosted timing.",
                    "latencies_ms":latency}
            target=state.parent/"qa"/"rdc2-vps-localhost30-results.json"
            target.write_text(json.dumps(report,indent=2)+"\n")
            print(json.dumps({k:v for k,v in report.items() if k!="latencies_ms"},indent=2))
if __name__=="__main__":
    asyncio.run(main(sys.argv[1]))
