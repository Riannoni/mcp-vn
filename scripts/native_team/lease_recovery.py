#!/usr/bin/env python3
"""Owner-fenced, fail-closed abandonment of source-only cloud lease.
Use only after the current cloud worker confirms a real blocker. Never retries.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import time

def abandon(root,task_id,owner,fence,reason,now=None):
    if not isinstance(task_id,str) or len(task_id)>40 or len(task_id)<4 or task_id[0] not in "RQGS" or task_id[1]!="-":
        raise ValueError("invalid task id")
    if not owner or not fence or not isinstance(reason,str) or not 12<=len(reason)<=220:
        raise ValueError("owner/fence and specific blocker required")
    dbpath=Path(root)/"state/team.sqlite3"
    now=time.time() if now is None else now
    db=sqlite3.connect(dbpath,timeout=10,isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT state,owner,fence,lease_until FROM task WHERE id=?",(task_id,)).fetchone()
        if not row or row[0]!="leased" or row[1]!=owner or row[2]!=fence or row[3]<=now:
            db.execute("ROLLBACK")
            return {"abandoned":False,"reason":"not_current_fenced_lease"}
        changed=db.execute("UPDATE task SET state='blocked',owner=NULL,fence=NULL,lease_until=0,completed_at=? WHERE id=? AND state='leased' AND owner=? AND fence=?",(now,task_id,owner,fence))
        if changed.rowcount!=1:raise RuntimeError("lost lease CAS")
        db.execute("INSERT INTO event(ts,task_id,kind,detail) VALUES(?,?,?,?)",
                   (now,task_id,"worker_abandoned",reason))
        db.execute("COMMIT")
        return {"abandoned":True,"task_id":task_id,"status":"blocked"}
    except BaseException:
        if db.in_transaction:db.execute("ROLLBACK")
        raise
    finally:db.close()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--task",required=True)
    p.add_argument("--owner",required=True)
    p.add_argument("--fence",required=True)
    p.add_argument("--reason",required=True)
    a=p.parse_args()
    print(json.dumps(abandon(a.root,a.task,a.owner,a.fence,a.reason)))
