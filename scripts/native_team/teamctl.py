#!/usr/bin/env python3
"""Four ChatGPT scheduled-worker lanes: local control plane for isolated source work.

No model execution, API, GPU, deploy or network. Review gate is mandatory.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import coordinator as c

LANES={'R':'renderer','Q':'qa','G':'golden','S':'reliability'}
ROOT=Path(__file__).resolve().parent.parent
DB=ROOT/'state/team.sqlite3'
SEED=[
 ('R-01','Source-grounded bimanual contact', 'Review PR47 pre-GPU actor-relative prop+hands architecture on NEW heldout case. No map rerolls or GPUs. One negative regression first.', ['worker/bimanual_scene_planner.py','tests/bimanual-scene-planner.test.py']),
 ('R-02','Generalized staged prop and ROI', 'Audit generic compositor vs source plate and actor masks, failing contact/garment negative test. No posthoc fixed-coordinate hacks.', ['worker/prop_layer_compositor.py','tests/prop-layer-compositor.test.py']),
 ('Q-01','Strict source-provenance gate', 'Review previous pilot worker-a uncommitted diff on PC as read-only source, then reproduce/apply to this independent PR49 branch with tests. No mixing scene/frame/actor evidence.', ['worker/atomic_prop_gate.py','tests/atomic-prop-gate.test.py']),
 ('Q-02','Semantic QA observability contract', 'Trace missing required scene evidence without loosening PASS; build narrow negative tests for unknown contact.', ['worker/qa_evidence_fence.py','tests/qa-evidence-fence.test.py']),
 ('G-01','Golden manifest independent review', 'Review previous pilot worker-b commit 5a3ccd9. Find one real false accept in 30+ labeled synthetic manifest validator and fix with negative test; only synthetic data.', ['scripts/render_golden_set_audit.py','scripts/tests/test_render_golden_set_audit.py']),
 ('G-02','Honest visual QA metrics', 'Implement offline confusion-matrix metrics for human labels incl unknown/unobservable, protect against empty labels; no private PNG publication.', ['scripts/render_quality_metrics.py','scripts/tests/test_render_quality_metrics.py']),
 ('S-01','Atomic publish version fence', 'Reproduce stale candidate version/scene collision in source code, implement isolated source-only policy and negative test. No production deploy.', ['scripts/render_publish_fence.py','scripts/tests/test_render_publish_fence.py']),
 ('S-02','Crash/restart/rollback tests', 'Isolated offline E2E crash/retry/save preservation contract, no GPU or production service manipulation.', ['scripts/render_e2e_rehearsal.py','scripts/tests/test_render_e2e_rehearsal.py']),
]

def git(lane,*args):
    p=subprocess.run(['git','-C',str(ROOT/('lane-'+LANES[lane])),*args],capture_output=True,text=True,timeout=15)
    if p.returncode:raise RuntimeError('git error: '+p.stderr[:200])
    return p.stdout.strip()

def paths_valid(xs):
    return isinstance(xs,list) and bool(xs) and len(xs)<12 and all(isinstance(x,str) and x and not x.startswith(('/','.git')) and '\\' not in x and all(y not in ('','.','..') for y in x.split('/')) for x in xs)

def open_db():
    if not DB.is_file():raise FileNotFoundError('not initialized')
    db=c.database(DB)
    db.execute('CREATE TABLE IF NOT EXISTS team_meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS claim_baselines(task_id TEXT PRIMARY KEY, head TEXT NOT NULL)')
    return db

def initialize():
    if DB.exists():raise FileExistsError('Already initialized')
    DB.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    for lane in LANES:
        work=ROOT/('lane-'+LANES[lane])
        if not (work/'AGENTS.md').is_file() or not (work/'docs/DEVELOPMENT-AND-TESTING.md').is_file():
            raise RuntimeError('mandatory docs missing')
        if git(lane,'status','--porcelain'):
            raise RuntimeError('dirty lane')
    db=open_db() if DB.is_file() else c.database(DB)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS team_meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS claim_baselines(task_id TEXT PRIMARY KEY, head TEXT NOT NULL)')
        db.execute("INSERT INTO team_meta VALUES ('state','active')")
        db.execute("INSERT INTO team_meta VALUES ('goal','render-v1 issue #20 Sprite + 3 CG first-shot, 30+ human-labeled independent G2/G3')")
        for tid,name,instructions,scope in SEED:
            c.add(db,tid,'source_inventory',scope,goal='render-v1 #20 '+name,priority=100 if tid.endswith('01') else 50)
            db.execute('UPDATE task SET action=? WHERE id=?',(instructions,tid))
        c.emit(db,'TEAM','initialized','4 isolated lanes; no GPU')
    finally:db.close()
    return {'ready':True,'root':str(ROOT),'tasks':len(SEED)}

def claim(db,lane,owner):
    if db.execute("SELECT v FROM team_meta WHERE k='state'").fetchone()[0]!='active':return {'claimed':False,'reason':'paused'}
    if git(lane,'status','--porcelain','--untracked-files=all'):
        return {'claimed':False,'reason':'dirty_worktree_needs_review'}
    # Co.claim is serialized by BEGIN IMMEDIATE, with a narrow lane prefix.
    item=c.claim(db,owner,ttl=2700,lane=lane)
    if item is None:return {'claimed':False,'reason':'no_unclaimed_ready_task'}
    db.execute('INSERT OR REPLACE INTO claim_baselines(task_id,head) VALUES(?,?)',(item['id'],git(lane,'rev-parse','HEAD')))
    task=db.execute('SELECT paths FROM task WHERE id=?',(item['id'],)).fetchone()
    return {'claimed':True,**item,'lane':lane,'worktree':str(ROOT/('lane-'+LANES[lane])), 'paths':json.loads(task[0])}

def submit(db,lane,owner,fence,tid,file):
    f=Path(file).resolve()
    base=(ROOT/'evidence'/LANES[lane]).resolve()
    if not f.is_file() or f.is_symlink() or base not in f.parents or f.stat().st_size>16000:
        raise ValueError('evidence must be a small private file in lane evidence dir')
    result=json.loads(f.read_text())
    if result.get('source_status')!='tested_isolated' or result.get('g2')!='UNVERIFIED' or result.get('g3')!='NO_GO':
        raise ValueError('source-only result cannot assert visual quality')
    if not result.get('tests') or not isinstance(result['tests'],list):raise ValueError('tests required')
    allowed=json.loads(db.execute('SELECT paths FROM task WHERE id=?',(tid,)).fetchone()[0])
    changed=result.get('changed_paths')
    if not paths_valid(changed) or any(x not in allowed for x in changed):raise ValueError('unapproved paths')
    baseline=db.execute('SELECT head FROM claim_baselines WHERE task_id=?',(tid,)).fetchone()
    if not baseline:raise ValueError('missing source SHA')
    pending=git(lane,'status','--porcelain','--untracked-files=all').splitlines()
    committed=git(lane,'diff','--name-only',baseline[0],'HEAD').splitlines()
    existing={x[3:] for x in pending}|set(committed)
    if not set(changed).issubset(existing) or any(x not in allowed for x in existing):
        raise ValueError('changed paths differ from scope')
    raw=f.read_bytes()
    return {'accepted':c.complete(db,tid,owner,fence,{'sha256':hashlib.sha256(raw).hexdigest(),
            'path':str(f.relative_to(ROOT)),'tests':result['tests'],'status':'source-only'},passed=True)}

def review(db,task_id,approve,note):
    if not note.strip():raise ValueError('independent review note required')
    x=db.execute('SELECT state,result FROM task WHERE id=?',(task_id,)).fetchone()
    if not x or x['state']!='review_pending':return {'approved':False,'reason':'not pending'}
    doc=json.loads(x['result'])
    f=(ROOT/doc['path']).resolve()
    if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=doc['sha256']:
        raise ValueError('evidence tampered')
    db.execute('UPDATE task SET state=? WHERE id=?',('done' if approve else 'blocked',task_id))
    c.emit(db,task_id,'review_pass' if approve else 'review_block',note[:400])
    return {'approved':approve,'task':task_id}

def watchdog(db):
    now=time.time()
    db.execute('BEGIN IMMEDIATE')
    try:
        # In forked coordinator: lease expiry blocks, no blind retry.
        c._expire(db,now)
        warnings=[]
        for prefix,name in LANES.items():
            vals=[dict(x) for x in db.execute('SELECT id,state,attempt,owner FROM task WHERE id LIKE ?', (prefix+'-%',))]
            if any(v['state']=='blocked' for v in vals):warnings.append(f'{name}:BLOCKED')
            if not any(v['state']=='leased' for v in vals):
                warnings.append(f'{name}:idle_or_waiting_for_next_scheduled_chat')
        c.emit(db,'TEAM','watchdog_tick','; '.join(warnings))
        db.execute('COMMIT')
    except BaseException:db.execute('ROLLBACK');raise
    return {'watchdog_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'warnings':warnings}

def status(db):
    result={'team':db.execute("SELECT v FROM team_meta WHERE k='state'").fetchone()[0],'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'lanes':{},'g2':'UNVERIFIED','g3':'NO_GO'}
    for lane,name in LANES.items():
        tasks=[{'id':x['id'],'state':x['state'],'attempt':x['attempt'],'owner':x['owner'],'lease_until':x['lease_until']} for x in db.execute('SELECT * FROM task WHERE id LIKE ? ORDER BY id',(lane+'-%',))]
        result['lanes'][name]={'tasks':tasks,'head':git(lane,'rev-parse','--short','HEAD'), 'dirty':bool(git(lane,'status','--porcelain','--untracked-files=all'))}
    result['last_events']=[dict(x) for x in db.execute('SELECT ts,task_id,kind,detail FROM event ORDER BY seq DESC LIMIT 12')]
    return result

def main():
    p=argparse.ArgumentParser()
    subs=p.add_subparsers(dest='cmd',required=True)
    subs.add_parser('init');subs.add_parser('status');subs.add_parser('watchdog')
    cc=subs.add_parser('claim');cc.add_argument('--lane',choices=LANES,required=True);cc.add_argument('--owner',required=True)
    cc=subs.add_parser('heartbeat');cc.add_argument('--task',required=True);cc.add_argument('--owner',required=True);cc.add_argument('--fence',required=True)
    cc=subs.add_parser('submit');cc.add_argument('--lane',choices=LANES,required=True);cc.add_argument('--task',required=True);cc.add_argument('--owner',required=True);cc.add_argument('--fence',required=True);cc.add_argument('--evidence',required=True)
    cc=subs.add_parser('review');cc.add_argument('--task',required=True);cc.add_argument('--approve',action='store_true');cc.add_argument('--note',required=True)
    cc=subs.add_parser('enqueue');cc.add_argument('--spec',required=True)
    cc=subs.add_parser('stop');cc.add_argument('--reason',required=True)
    args=p.parse_args()
    if args.cmd=='init':print(json.dumps(initialize()));return 0
    db=open_db()
    try:
        if args.cmd=='status':result=status(db)
        elif args.cmd=='watchdog':result=watchdog(db)
        elif args.cmd=='claim':result=claim(db,args.lane,args.owner)
        elif args.cmd=='heartbeat':result={'accepted':c.heartbeat(db,args.task,args.owner,args.fence,ttl=2700)}
        elif args.cmd=='submit':result=submit(db,args.lane,args.owner,args.fence,args.task,args.evidence)
        elif args.cmd=='review':result=review(db,args.task,args.approve,args.note)
        elif args.cmd=='enqueue':
            d=json.loads(Path(args.spec).read_text())
            if d['lane'] not in LANES or not d['id'].startswith(d['lane']+'-') or not paths_valid(d['paths']):raise ValueError('invalid lane/task scope')
            c.add(db,d['id'],'source_inventory',d['paths'],d.get('dependencies',[]),goal=d['goal'],priority=d.get('priority',50))
            db.execute('UPDATE task SET action=? WHERE id=?',(d['instructions'],d['id']))
            result={'enqueued':d['id']}
        elif args.cmd=='stop':
            db.execute("UPDATE team_meta SET v='stopped' WHERE k='state'")
            c.emit(db,'TEAM','stopped',args.reason);result={'stopped':True}
        else:raise ValueError('unsupported')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    finally:db.close()
if __name__=='__main__':sys.exit(main())
