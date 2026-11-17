"""Local synthetic comparison: six SHA-guarded coding edits, one vs six Engine calls."""
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import time

from rdc.config import Settings
from rdc.engine import Engine


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def metrics(values):
    values = sorted(values)
    def quantile(p):
        index = (len(values)-1)*p
        low = int(index)
        high = min(low+1,len(values)-1)
        return round(values[low]+(values[high]-values[low])*(index-low),3)
    return {"runs":len(values),"p50_ms":round(statistics.median(values),3),
            "p95_ms":quantile(.95),"p99_ms":quantile(.99)}


def run(trials=30,warmups=3):
    if trials<5 or trials>100:
        raise ValueError("Expected 5 to 100 trials")
    count=6
    samples={"batch":[],"individual":[]}
    with tempfile.TemporaryDirectory(prefix="rdc-code-batch-") as scratch:
        home=Path(scratch)
        project=home/"workspace"
        project.mkdir()
        engine=Engine(Settings(state_dir=home/"state",roots=[project],
                               approval_mode="trusted",allow_exec=False,
                               browser_backend="disabled"))
        try:
            for t in range(trials+warmups):
                order=("batch","individual") if t%2==0 else ("individual","batch")
                for mode in order:
                    edits=[]
                    for i in range(count):
                        file=project/f"module_{i}.py"
                        initial=f"module_{i}=old\n"
                        file.write_text(initial,encoding="utf-8")
                        edits.append({"file_path":file.name,"old_text":"=old",
                                      "new_text":"=new","expected_sha256":digest(initial),
                                      "expected_count":1})
                    start=time.perf_counter()
                    if mode=="batch":
                        reply=engine.call("rdc_code_edit_many",{"path":str(project),"edits":edits})
                        assert reply["ok"] and reply["applied"]==count,reply
                    else:
                        for edit in edits:
                            reply=engine.call("rdc_file_edit",
                                {**edit,"file_path":str(project/edit["file_path"])})
                            assert reply["ok"],reply
                    elapsed_ms=(time.perf_counter()-start)*1000
                    assert all((project/f"module_{i}.py").read_text()==
                               f"module_{i}=new\n" for i in range(count))
                    if t>=warmups:samples[mode].append(elapsed_ms)
        finally:
            engine.close()
    batch,individual=metrics(samples["batch"]),metrics(samples["individual"])
    return {"scope":"local RDC Engine, zero network requests",
            "edits_per_case":count,"trials":trials,"warmups":warmups,
            "results":{"batch":{**batch,"correct":trials,"engine_calls_per_case":1},
                       "individual":{**individual,"correct":trials,
                                     "engine_calls_per_case":count}},
            "p50_speedup_ratio_individual_over_batch":
                round(individual["p50_ms"]/max(batch["p50_ms"],0.001),2),
            "limitations":["Cloud/ChatGPT transport excluded",
                           "No Desktop Commander run",
                           "Independent file edits are not a cross-file transaction"]}


if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
