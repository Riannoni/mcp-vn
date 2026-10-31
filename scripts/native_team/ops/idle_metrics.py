#!/usr/bin/env python3
"""Read-only SQLite idle timings; never starts ChatGPT or changes task state."""
import math
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
    for lane in LANES:
        tasks=[dict(row) for row in db.execute(
            "SELECT id,state,started_at,completed_at FROM task WHERE id LIKE ? ORDER BY id",
            (lane+"-%",))]
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
        if busy:
            state="working"
        elif blocked:
            state="blocked"
        elif awaiting:
            state="awaiting_independent_review"
        elif pending:
            state="pending_ready_or_dependency"
        else:
            state="no_backlog"
        age=None
        if not busy and (pending or awaiting) and latest_done is not None:
            age=max(0,round(now-latest_done))
        ready=None
        if not busy and pending:
            starts=[]
            for t in pending:
                start=enqueued.get(t["id"])
                if start is not None:
                    starts.append(max(start,latest_done if latest_done is not None else start))
            if starts:
                ready=max(0,round(now-min(starts)))
        planning_idle=(max(0,round(now-latest_done))
                       if state=="no_backlog" and latest_done is not None else None)
        out[lane]={"state":state,
                   "planning_deficit_seconds":planning_idle,
                   "planning_deficit_over_5_minutes":planning_idle is not None and planning_idle>300,
                   "planning_deficit_over_10_minutes":planning_idle is not None and planning_idle>600,
                   "pending_count":len(pending),
                   "review_count":sum(t["state"]=="review_pending" for t in tasks),
                   "worker_idle_seconds":age,
                   "ready_idle_seconds":ready,
                   "over_10_minutes":ready is not None and ready>threshold and not (awaiting or blocked),
                   "historical_gaps":len(gaps),
                   "gap_p50_seconds":_percentile(gaps,0.5),
                   "gap_p90_seconds":_percentile(gaps,0.9)}
    return out
