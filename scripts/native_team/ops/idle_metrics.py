#!/usr/bin/env python3
"""Read-only SQLite idle timings; never starts ChatGPT or changes task state."""
import math
import json
import sqlite3
import time

LANES=("R","Q","G","S")


def _percentile(values, q):
    values=sorted(values)
    if not values:
        return None
    x=(len(values)-1)*q
    lo=int(math.floor(x))
    hi=int(math.ceil(x))
    return round(values[lo]+(values[hi]-values[lo])*(x-lo),1)


def calculate(db, now=None, threshold=600):
    now=time.time() if now is None else now
    out={}
    # Read all scopes: admission and metric must agree about real actionable work.
    all_tasks=[dict(row) for row in db.execute(
        "SELECT id,state,started_at,completed_at,deps,paths FROM task ORDER BY id")]
    by_id={t["id"]:t for t in all_tasks}
    passed={x["task_id"]:x["ts"] for x in db.execute(
        "SELECT task_id,MAX(ts) AS ts FROM event WHERE kind='review_pass' GROUP BY task_id")}
    occupied=[json.loads(t["paths"]) for t in all_tasks
              if t["state"] in ("leased","blocked","review_pending")]
    def overlap(a,b):
        return any(x==y or x.startswith(y.rstrip("/")+"/") or y.startswith(x.rstrip("/")+"/")
                   for x in a for y in b)
    for lane in LANES:
        tasks=[t for t in all_tasks if t["id"].startswith(lane+"-")]
        if not tasks:
            out[lane]={"state":"no_tasks","ready_idle_seconds":None,
                       "worker_idle_seconds":None,"over_10_minutes":False}
            continue
        busy=any(x["state"]=="leased" for x in tasks)
        awaiting=any(x["state"]=="review_pending" for x in tasks)
        blocked=any(x["state"]=="blocked" for x in tasks)
        pending=[t for t in tasks if t["state"]=="pending"]
        finished=[t for t in tasks if t["completed_at"] is not None]
        latest_done=max((x["completed_at"] for x in finished),default=None)
        enqueued={}
        for row in db.execute(
            "SELECT task_id,MIN(ts) AS since FROM event WHERE kind='enqueued' "
            "AND task_id LIKE ? GROUP BY task_id",(lane+"-%",)):
            enqueued[row["task_id"]]=row["since"]
        gaps=[]
        sorted_start=sorted((t for t in tasks if t["started_at"] is not None),
                            key=lambda x:x["started_at"])
        for prev,nxt in zip(sorted_start,sorted_start[1:]):
            if prev["completed_at"] is not None and nxt["started_at"]>=prev["completed_at"]:
                gaps.append(nxt["started_at"]-prev["completed_at"])
        actionable=[]
        if not busy:
            for t in pending:
                deps=json.loads(t["deps"])
                if any(dep not in by_id or by_id[dep]["state"]!="done" for dep in deps):
                    continue
                paths=json.loads(t["paths"])
                if any(overlap(paths,scope) for scope in occupied):
                    continue
                dep_times=[passed.get(dep) or by_id[dep]["completed_at"] for dep in deps]
                dep_times=[x for x in dep_times if x is not None]
                started=max([enqueued.get(t["id"],now)]+dep_times)
                actionable.append((t["id"],started))
        if busy:
            state="working"
        elif actionable:
            state="pending_ready"
        elif awaiting:
            state="awaiting_independent_review"
        elif blocked:
            state="blocked"
        elif pending:
            state="pending_dependencies"
        else:
            state="no_backlog"
        age=None
        if not busy and (pending or awaiting) and latest_done is not None:
            age=max(0,round(now-latest_done))
        ready=max(0,round(now-min(x[1] for x in actionable))) if actionable else None
        planning_idle=(max(0,round(now-latest_done))
                       if state=="no_backlog" and latest_done is not None else None)
        review_times=[t["completed_at"] for t in tasks if t["state"]=="review_pending" and t["completed_at"] is not None]
        review_wait=max(0,round(now-min(review_times))) if review_times else None
        out[lane]={"state":state,
                   "review_wait_seconds":review_wait,
                   "review_over_10_minutes":review_wait is not None and review_wait>threshold,
                   "planning_deficit_seconds":planning_idle,
                   "planning_deficit_over_5_minutes":planning_idle is not None and planning_idle>300,
                   "planning_deficit_over_10_minutes":planning_idle is not None and planning_idle>600,
                   "pending_count":len(pending),
                   "actionable_count":len(actionable),
                   "blocked_count":sum(t["state"]=="blocked" for t in tasks),
                   "review_count":sum(t["state"]=="review_pending" for t in tasks),
                   "worker_idle_seconds":age,
                   "ready_idle_seconds":ready,
                   "over_10_minutes":ready is not None and ready>threshold,
                   "historical_gaps":len(gaps),
                   "gap_p50_seconds":_percentile(gaps,0.5),
                   "gap_p90_seconds":_percentile(gaps,0.9)}
    return out
