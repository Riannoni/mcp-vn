#!/usr/bin/env python3
"""Guard an OPTIONAL ChatGPT Scheduled Task run_now request.

This program never calls OpenAI, never starts a worker and never bypasses a
plan limit. A human or the cloud chief must use the supported Automations
action separately, after checking its current run status.
"""
import argparse
import json
import sqlite3
import subprocess
import time
from pathlib import Path

LANES={"R":"renderer","Q":"qa","G":"golden","S":"reliability"}
COOLDOWN_S=3600


def readiness(root, lane, db, now, cooldown=COOLDOWN_S):
    if lane not in LANES:
        raise ValueError("unknown lane")
    state=db.execute("SELECT v FROM team_meta WHERE k='state'").fetchone()
    if state is None or state[0]!="active":
        return {"eligible":False,"reason":"team_inactive","lane":lane}
    tasks=db.execute("SELECT id,state,deps,paths FROM task WHERE id LIKE ? ORDER BY priority DESC,id",
                     (lane+"-%",)).fetchall()
    states=[t[1] for t in tasks]
    if "leased" in states:
        return {"eligible":False,"reason":"worker_busy","lane":lane}
    worktree=root/("lane-"+LANES[lane])
    result=subprocess.run(["git","-C",str(worktree),"status","--porcelain",
                           "--untracked-files=all"],capture_output=True,text=True,timeout=10)
    if result.returncode or result.stdout.strip():
        return {"eligible":False,"reason":"worktree_dirty_or_missing","lane":lane}
    if "blocked" in states:
        return {"eligible":False,"reason":"blocker_requires_review","lane":lane}
    if "review_pending" in states:
        return {"eligible":False,"reason":"review_pending","lane":lane}
    completed={x[0] for x in db.execute("SELECT id FROM task WHERE state='done'")}
    occupied=[json.loads(x[0]) for x in db.execute("SELECT paths FROM task WHERE state='leased'")]
    def overlaps(a,b):
        return any(x==y or x.startswith(y.rstrip("/")+"/") or y.startswith(x.rstrip("/")+"/")
                   for x in a for y in b)
    ready=[]
    for row in tasks:
        if row[1]!="pending":
            continue
        if not set(json.loads(row[2])).issubset(completed):
            continue
        paths=json.loads(row[3])
        if any(overlaps(paths,scope) for scope in occupied):
            continue
        ready.append(row[0])
    if not ready:
        return {"eligible":False,"reason":"no_ready_task","lane":lane}
    last=db.execute("SELECT requested_at FROM wake_reservation WHERE lane=?",(lane,)).fetchone()
    if last and now-last[0]<cooldown:
        return {"eligible":False,"reason":"wake_cooldown","lane":lane,
                "retry_after_seconds":round(cooldown-(now-last[0]))}
    return {"eligible":True,"lane":lane,"task_id":ready[0],"ready_count":len(ready),
            "reason":"optional_cloud_run_now_ready"}


def check(root,lane,reserve=False,requestor="chief",now=None,cooldown=COOLDOWN_S):
    root=Path(root).resolve()
    dbpath=root/"state/team.sqlite3"
    if not dbpath.is_file():
        raise FileNotFoundError("team sqlite not initialized")
    db=sqlite3.connect(dbpath,timeout=10,isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=10000")
        if reserve:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS wake_reservation ("
                       "lane TEXT PRIMARY KEY,requested_at REAL NOT NULL,"
                       "task_id TEXT NOT NULL,requestor TEXT NOT NULL)")
        else:
            # In a new installation with no previous reservations, inspect without mutation.
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name='wake_reservation'").fetchone()
            if not exists:
                db.execute("CREATE TEMP TABLE wake_reservation ("
                           "lane TEXT PRIMARY KEY,requested_at REAL NOT NULL,"
                           "task_id TEXT NOT NULL,requestor TEXT NOT NULL)")
        instant=time.time() if now is None else now
        result=readiness(root,lane,db,instant,cooldown)
        if reserve and result["eligible"]:
            if not requestor or len(requestor)>100:
                raise ValueError("invalid requestor")
            db.execute("INSERT INTO wake_reservation VALUES (?,?,?,?) "
                       "ON CONFLICT(lane) DO UPDATE SET requested_at=excluded.requested_at,"
                       "task_id=excluded.task_id,requestor=excluded.requestor",
                       (lane,instant,result["task_id"],requestor))
            result["reserved"]=True
            result["note"]="Call Automations.run_now once; success means requested, not completed"
        if reserve:
            db.execute("COMMIT")
        return result
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()



def review_readiness(db,now,cooldown=600,settle_seconds=120):
    """Chief review is ready when submitted evidence needs independent checking.

    Wait briefly for sibling workers, but never pretend a local scanner can
    start ChatGPT. The caller still checks the cloud Chief run is not active.
    """
    state=db.execute("SELECT v FROM team_meta WHERE k='state'").fetchone()
    if state is None or state[0]!='active':
        return {'eligible':False,'reason':'team_inactive'}
    tasks=db.execute("SELECT id,completed_at FROM task WHERE state='review_pending'").fetchall()
    if not tasks:
        return {'eligible':False,'reason':'nothing_to_review'}
    active=db.execute("SELECT COUNT(*) FROM task WHERE state='leased'").fetchone()[0]
    oldest=min(t[1] if t[1] is not None else now for t in tasks)
    if active and now-oldest < settle_seconds:
        return {'eligible':False,'reason':'other_workers_finishing',
                'review_count':len(tasks),'active_leases':active}
    last=db.execute("SELECT requested_at FROM wake_reservation WHERE lane='C'").fetchone()
    if last and now-last[0]<cooldown:
        return {'eligible':False,'reason':'chief_wake_cooldown',
                'retry_after_seconds':round(cooldown-(now-last[0]))}
    return {'eligible':True,'reason':'independent_review_ready',
            'review_count':len(tasks),'active_leases':active,'task_id':tasks[0][0]}


def check_review(root,reserve=False,requestor='worker',now=None,cooldown=600):
    root=Path(root).resolve()
    dbpath=root/'state/team.sqlite3'
    if not dbpath.is_file():
        raise FileNotFoundError('team sqlite not initialized')
    db=sqlite3.connect(dbpath,timeout=10,isolation_level=None)
    try:
        db.execute('PRAGMA busy_timeout=10000')
        if reserve:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS wake_reservation '
                       '(lane TEXT PRIMARY KEY,requested_at REAL NOT NULL,'
                       'task_id TEXT NOT NULL,requestor TEXT NOT NULL)')
        elif not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                            "AND name='wake_reservation'").fetchone():
            db.execute('CREATE TEMP TABLE wake_reservation '
                       '(lane TEXT PRIMARY KEY,requested_at REAL NOT NULL,'
                       'task_id TEXT NOT NULL,requestor TEXT NOT NULL)')
        instant=time.time() if now is None else now
        outcome=review_readiness(db,instant,cooldown)
        if reserve and outcome['eligible']:
            if not isinstance(requestor,str) or not requestor or len(requestor)>100:
                raise ValueError('invalid requestor')
            db.execute("INSERT INTO wake_reservation VALUES('C',?,?,?) "
                       "ON CONFLICT(lane) DO UPDATE SET requested_at=excluded.requested_at,"
                       "task_id=excluded.task_id,requestor=excluded.requestor",
                       (instant,outcome['task_id'],requestor))
            outcome['reserved']=True
            outcome['note']='Cloud worker must invoke supported Chief Automations.run_now once; platform may refuse'
        if reserve:
            db.execute('COMMIT')
        return outcome
    except BaseException:
        if db.in_transaction:db.execute('ROLLBACK')
        raise
    finally:
        db.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--lane",choices=LANES)\n    p.add_argument("--chief-review",action="store_true")
    p.add_argument("--reserve",action="store_true")
    p.add_argument("--requestor",default="chief")
    args=p.parse_args()
    if not args.chief_review and not args.lane:
        p.error('--lane is required unless --chief-review')
    result=(check_review(args.root,args.reserve,args.requestor)
            if args.chief_review
            else check(args.root,args.lane,args.reserve,args.requestor))
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
