"""Balanced direct-local RDC source-context benchmark.

This compares three existing Engine.call reads to one bounded code-context
Engine.call. Both variants access the same disposable synthetic project and
must return exactly equal observable content. Cloud/AI host latency excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from rdc.config import Settings
from rdc.engine import Engine


def percentile(xs,p):
    ordered=sorted(xs)
    index=p*(len(ordered)-1)
    low=int(index)
    high=min(low+1,len(ordered)-1)
    return ordered[low]+(ordered[high]-ordered[low])*(index-low)


def summary(samples):
    ms=[r['elapsed_ms'] for r in samples]
    return {
        'trials':len(samples),'correct':sum(r['correct'] for r in samples),
        'p50_ms':round(statistics.median(ms),3),
        'p95_ms':round(percentile(ms,.95),3),
        'p99_ms':round(percentile(ms,.99),3),
        'min_ms':round(min(ms),3),
        'max_ms':round(max(ms),3),
        'stddev_ms':round(statistics.pstdev(ms),3),
        'tool_calls_per_workflow':samples[0]['tool_calls'],
    }


def run(trials=30,warmups=3):
    if not 1<=trials<=1000 or not 0<=warmups<=100:
        raise ValueError('Invalid trial and warmup count')
    with tempfile.TemporaryDirectory(prefix='rdc-code-context-bench-') as temp:
        base=Path(temp)
        root=base/'project'
        root.mkdir()
        for i in range(60):
            source=f'# synthetic code file {i}\n' + ''.join(
                f'arg_{j} = {i+j}\n' for j in range(45))
            if i==17:source+='return RDC_CTX_UNIQUE_20261117\n'
            (root/f'module_{i:03d}.py').write_text(source,encoding='utf-8')
        paths=[str(root/f'module_{i:03d}.py') for i in (2,17,59)]
        engine=Engine(Settings(
            state_dir=base/'isolated-state',
            roots=[root],
            approval_mode='trusted',
            browser_backend='disabled',
            allow_exec=False,
        ))
        order=['legacy_three_calls','single_code_context']*trials
        warm=['legacy_three_calls','single_code_context']*warmups
        rng=random.Random(20261117)
        rng.shuffle(order)
        rng.shuffle(warm)
        records={'legacy_three_calls':[],'single_code_context':[]}
        result_hash=hashlib.sha256()
        def must(name,arg):
            value=engine.call(name,arg)
            if not value.get('ok'):
                raise AssertionError(name+' returned '+str(value.get('error',{}).get('code')))
            return value
        def one(method,measured):
            begin=time.perf_counter()
            if method=='legacy_three_calls':
                listing=must('rdc_file_list',{'path':str(root),'limit':120})
                search=must('rdc_file_search',{'path':str(root),
                    'query':'RDC_CTX_UNIQUE_20261117','limit':100,'max_files':1000})
                files=must('rdc_file_read_many',{'file_paths':paths})['results']
                count=3
            else:
                response=must('rdc_code_context',{'path':str(root),
                    'query':'RDC_CTX_UNIQUE_20261117','file_paths':paths,
                    'list_limit':120,'search_limit':100,'max_files':1000})
                listing=response['listing']
                search=response['search']
                files=response['reads']
                count=1
            elapsed=(time.perf_counter()-begin)*1000
            assert len(listing['entries'])==60
            assert len(search['matches'])==1
            assert search['matches'][0]['line']==47
            assert len(files)==3 and all(x['ok'] for x in files)
            for entry,expected in zip(files,paths):
                assert entry['text']==Path(expected).read_text(encoding='utf-8')
                assert entry['sha256']==hashlib.sha256(Path(expected).read_bytes()).hexdigest()
                assert entry['truncated'] is False
                result_hash.update(entry['sha256'].encode('ascii'))
            if measured:
                records[method].append({'elapsed_ms':round(elapsed,3),
                                        'correct':True,'tool_calls':count})
        try:
            for method in warm:one(method,False)
            for method in order:one(method,True)
        finally:engine.close()
    return {
        'scope':'direct local disposable Engine only, NOT live RDC vs Desktop Commander',
        'python_version':sys.version.split()[0],'os':platform.system(),
        'source_catalog_tool':'rdc_code_context',
        'matched_conditions':'60 synthetic files, 1 matching code line, 3 small source reads, all results SHA-checked',
        'trials_per_variant':trials,'warmups_per_variant':warmups,
        'seed':20261117,
        'result_digest':result_hash.hexdigest(),
        'summary':{name:summary(s) for name,s in records.items()},
        'samples':records,
        'limitations':['No network or model inference','No live Site v16 or v17 tool latency',
                       'Reduces AI-host tool hops 3 to 1, but local execution may be similar or slower',
                       'Only code-context reads, no mutations or concurrent editors'],
    }


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials',type=int,default=30)
    parser.add_argument('--warmups',type=int,default=3)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run(args.trials,args.warmups)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['summary'],indent=2))
