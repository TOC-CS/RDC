"""Measure local RDC worker overhead using synthetic data, never production files."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rdc.config import Settings
from rdc.engine import Engine


def measure(operation,count=25):
    samples=[]
    for _ in range(count):
        start=time.perf_counter()
        result=operation()
        if result.get('ok') is False: raise RuntimeError(result)
        samples.append((time.perf_counter()-start)*1000)
    ordered=sorted(samples)
    return {'samples':count,'median_ms':round(statistics.median(samples),3),
            'p95_ms':round(ordered[min(len(ordered)-1,int(.95*len(ordered)))],3)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--browser',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='rdc-benchmark-') as temp:
        root=Path(temp)/'workspace';root.mkdir()
        file=root/'fixture.txt';file.write_text('RDC benchmark fixture\n'*100)
        start=time.perf_counter()
        engine=Engine(Settings(state_dir=Path(temp)/'state',roots=[root],approval_mode='trusted',allow_exec=True))
        report={'platform':platform.platform(),'python':platform.python_version(),
                'scope':'Local worker, synthetic fixtures; no competitor or model-latency comparison.',
                'startup_ms':round((time.perf_counter()-start)*1000,3),
                'tool_count':len(engine.catalog()),'catalog_bytes':len(json.dumps(engine.catalog()).encode())}
        try:
            report['file_read']=measure(lambda:engine.call('rdc_file_read',{'file_path':str(file)}))
            report['status']=measure(lambda:engine.call('rdc_system_status',{}))
            start=time.perf_counter()
            admitted=engine.call('rdc_job_start',{'argv':[sys.executable,'-c','print("benchmark-job")'],'cwd':str(root),'idempotency_key':'benchmark'})
            if not admitted['ok']:raise RuntimeError(admitted)
            report['job_admission_ms']=round((time.perf_counter()-start)*1000,3)
            identifier=admitted['job']['id']
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                status=engine.call('rdc_job_status',{'job_id':identifier})['job']
                if status['status'] not in ('queued','running'):break
                time.sleep(.01)
            if status['status']!='completed':raise RuntimeError(status)
            report['job_end_to_end_ms']=round((time.perf_counter()-start)*1000,3)
            report['job_output']=measure(lambda:engine.call('rdc_job_output',{'job_id':identifier}))
            if args.browser:
                start=time.perf_counter()
                browser=engine.call('rdc_browser_start',{})
                if not browser['ok']:raise RuntimeError(browser)
                sid=browser['session_id']
                report['browser_cold_start_ms']=round((time.perf_counter()-start)*1000,3)
                result=engine.call('rdc_browser_navigate',{'session_id':sid,'url':'data:text/html,<title>RDC benchmark</title><label>Name<input></label><button>Preview</button>'})
                if not result['ok']:raise RuntimeError(result)
                report['browser_observe']=measure(lambda:engine.call('rdc_browser_observe',{'session_id':sid}),10)
                report['browser_screenshot']=measure(lambda:engine.call('rdc_browser_screenshot',{'session_id':sid}),10)
        finally:
            engine.close()
    encoded=json.dumps(report,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded+'\n')
    print(encoded)


if __name__=='__main__':main()
