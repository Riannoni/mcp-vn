"""Crash-resilient ComfyUI execution journal.

The immutable per-attempt graph is fsynced *before* POST; a reconnect can
reuse its original random seed and logical-action idempotency key. The broker
still owns the uncertain-submit/queue fail-closed boundary; this is not a
distributed exactly-once GPU execution guarantee.
"""
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

def _root():
    p=Path(os.environ.get("VN_COMFY_MANIFEST_DIR",
        str(Path.home()/".local/share/mcp-vn/render-manifests")))
    p.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(p,0o700)
    return p

def key(job):
    ident=str(job.get("id") or "")
    if not re.fullmatch(r"[0-9a-f-]{36}",ident):raise ValueError("Invalid job ID")
    return _root()/(ident+".json")

def signature(job):
    data={k:job.get(k) for k in ("id","kind","style","prompt","character")}
    data["spec"]=job.get("spec") or {}
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,
                                  default=str).encode()).hexdigest()

def load(job):
    path=key(job)
    if not path.is_file():return None
    try:
        d=json.loads(path.read_text())
        if (d.get("version")!=1 or d.get("signature")!=signature(job) or
            not re.fullmatch(r"[0-9a-f-]{36}",str(d.get("prompt_id","")))):
            return None
        return d
    except (OSError,ValueError,TypeError):
        return None

def persist(job,prompt_id,workflow_digest):
    path=key(job)
    record={"version":1,"job_id":job["id"],
            "attempt":int(job.get("attempts") or 1),
            "signature":signature(job),"prompt_id":str(prompt_id),
            "workflow_digest":workflow_digest}
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        with open(tmp,"x",encoding="utf-8") as f:
            os.chmod(tmp,0o600)
            json.dump(record,f,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)
    return record


def intent_path(job):
    """Private immutable per-job/per-attempt graph, durably stored before POST."""
    attempt=int(job.get("attempts") or 1)
    if not 1 <= attempt <= 10000:
        raise ValueError("Invalid Comfy attempt")
    p=key(job)
    return p.with_name(p.stem+".attempt-"+str(attempt)+".intent.json")

def load_intent(job):
    path=intent_path(job)
    if not path.exists():
        return None
    try:
        if path.is_symlink():
            raise ValueError("Symlinked Comfy intent")
        data=json.loads(path.read_text(encoding="utf-8"))
        graph=data.get("graph")
        if (data.get("version")!=1 or data.get("signature")!=signature(job) or
            data.get("job_id")!=job["id"] or
            data.get("attempt")!=int(job.get("attempts") or 1) or
            not isinstance(graph,dict) or
            data.get("workflow_digest")!=digest(graph)):
            raise ValueError("Comfy intent contract/digest mismatch")
        return data
    except (OSError,ValueError,TypeError,KeyError) as exc:
        # Never regenerate a new random seed if the previous POST outcome
        # may be unknown. A corrupt/stale existing intent is a hard stop.
        raise RuntimeError("COMFY_INTENT_UNVERIFIED") from exc

def persist_intent(job,graph):
    """Atomically create (not replace) and fsync exact graph before HTTP POST."""
    if not isinstance(graph,dict):
        raise ValueError("Invalid Comfy graph")
    existing=load_intent(job)
    if existing is not None:
        if existing["workflow_digest"]!=digest(graph):
            raise RuntimeError("COMFY_INTENT_GRAPH_CONFLICT")
        return existing
    path=intent_path(job)
    record={"version":1,"job_id":job["id"],
            "attempt":int(job.get("attempts") or 1),
            "signature":signature(job),"workflow_digest":digest(graph),
            "graph":graph}
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        with open(tmp,"x",encoding="utf-8") as f:
            os.chmod(tmp,0o600)
            json.dump(record,f,ensure_ascii=False,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp,path)  # no-clobber: concurrent workers cannot replace intent
        except FileExistsError:
            existing=load_intent(job)
            if existing is None or existing["workflow_digest"]!=record["workflow_digest"]:
                raise RuntimeError("COMFY_INTENT_CONFLICT")
            return existing
        fd=os.open(str(path.parent),os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)
    return record

def digest(graph):
    return hashlib.sha256(json.dumps(graph,sort_keys=True,
                               ensure_ascii=False).encode()).hexdigest()

def status(result):
    if result.get("status",{}).get("status_str")=="success":
        return "finished"
    if result.get("status",{}).get("status_str") in ("error","failed"):
        return "failed"
    return "pending"
