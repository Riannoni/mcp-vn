#!/usr/bin/env python3
"""Read-only summary of actual recorded job/attempt timings (no story text)."""
from pathlib import Path
import argparse
import json
import statistics
def percentile(values,pct):
    values=sorted(values)
    return round(values[min(len(values)-1,int((len(values)-1)*pct))]/1000,2)
def report(folder):
    rows=[]
    for path in Path(folder).glob("*.json"):
        try:rows.append(json.loads(path.read_text()))
        except (ValueError,OSError):continue
    results={}
    for kind in ("background","sprite","scene","local_cg","video"):
        subset=[x for x in rows if x.get("kind")==kind]
        metrics={}
        for key in ("generation_ms","qa_ms","postprocess_ms","total_ms"):
            samples=[]
            for j in subset:
                if key=="total_ms":
                    value=(j.get("timings") or {}).get(key)
                    if isinstance(value,(int,float)):samples.append(value)
                else:
                    for attempt in j.get("attempt_history") or []:
                        value=(attempt.get("timings") or {}).get(key)
                        if isinstance(value,(int,float)):samples.append(value)
            if samples:metrics[key]={"n":len(samples),"p50_seconds":percentile(samples,.5),
                                    "p90_seconds":percentile(samples,.9)}
        results[kind]={"jobs":len(subset),"done":sum(j.get("status")=="done" for j in subset),
                       "failed":sum(j.get("status")=="failed" for j in subset),
                       "timings":metrics}
    return {"jobs":len(rows),"by_kind":results,
      "note":"Historical sample, not post-release A/B; never infer a latency regression without controlled comparable jobs"}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--jobs",required=True)
    args=p.parse_args()
    print(json.dumps(report(args.jobs),ensure_ascii=False,indent=2))
