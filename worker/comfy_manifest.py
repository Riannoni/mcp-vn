"""Crash-resilient ComfyUI execution journal.

A durable prompt ID prevents a worker restart from silently submitting
another GPU execution for an already accepted /prompt request. This is an
at-least-once queue with best-effort deduplication, NOT a distributed exactly-once
transaction: a power loss between POST and local fsync remains possible.
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

def load(job, expected_workflow_digest=None):
    """Resume only the exact workflow when its digest is supplied.

    Legacy callers can omit the digest, but GPU execution must provide it.
    A stale graph may produce different pixels even with the same job spec.
    """
    path=key(job)
    if not path.is_file():return None
    try:
        d=json.loads(path.read_text())
        if (d.get("version")!=1 or d.get("signature")!=signature(job) or
            not re.fullmatch(r"[0-9a-f-]{36}",str(d.get("prompt_id",""))) or
            (expected_workflow_digest is not None and
             (not isinstance(expected_workflow_digest,str) or
              not expected_workflow_digest or
              d.get("workflow_digest")!=expected_workflow_digest))):
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

def digest(graph):
    return hashlib.sha256(json.dumps(graph,sort_keys=True,
                               ensure_ascii=False).encode()).hexdigest()

def status(result):
    if result.get("status",{}).get("status_str")=="success":
        return "finished"
    if result.get("status",{}).get("status_str") in ("error","failed"):
        return "failed"
    return "pending"
