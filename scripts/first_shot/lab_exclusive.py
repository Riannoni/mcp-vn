#!/usr/bin/env python3
"""Isolated disposable Comfy A/B: quiesce known competing dev submitters.

Owner-authorized lab-only mode, NOT a universal GPU security broker. Never
changes active game saves or accepted images. No candidate = no service changes.
Unknown job = fail closed; never infer /queue empty is an OS-wide GPU guarantee.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SERVICES = ("mcp-vn-worker.service", "mcp-vn-model-lab.service",
            "mcp-vn-kobold-gateway.service")
QUIET_TIME_SECONDS = 1.0
DISPATCH_TIMEOUT_SECONDS = 115


def command(*args, timeout=25):
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, check=False)


def service_is_active(unit):
    p = command("systemctl", "--user", "is-active", unit, timeout=10)
    return p.returncode == 0 and p.stdout.strip() == "active"


def stop_service(unit):
    p = command("systemctl", "--user", "stop", unit)
    if p.returncode != 0 or service_is_active(unit):
        raise RuntimeError("cannot_quiesce_" + unit)


def start_service(unit):
    p = command("systemctl", "--user", "start", unit, timeout=30)
    if p.returncode != 0 or not service_is_active(unit):
        raise RuntimeError("cannot_restore_" + unit)


def queue_empty():
    from urllib.request import urlopen
    with urlopen("http://127.0.0.1:8188/queue", timeout=5) as r:
        data=json.load(r)
    return (data.get("queue_running")==[] and data.get("queue_pending")==[])


def atomic(path, value):
    p=path.with_suffix(path.suffix+".tmp")
    p.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")
    os.chmod(p,0o600)
    os.replace(p,path)


def run(root, dispatcher, *, ops=None):
    root=Path(root).expanduser().resolve()
    dispatcher=Path(dispatcher).expanduser().resolve()
    operations=ops or {
        "is_active":service_is_active,
        "stop":stop_service,
        "start":start_service,
        "queue_empty":queue_empty,
        "dispatch":lambda:command(sys.executable,str(dispatcher),"tick","--root",str(root),
                                   timeout=DISPATCH_TIMEOUT_SECONDS),
        "pause":time.sleep,
    }
    for path in ("pending","running","review_pending"):
        if not (root/path).is_dir():
            raise FileNotFoundError("firstshot_state_directory_missing_"+path)
    lock=root.parent/"exclusive-dev-lab-maintenance.lock"
    lock.touch(mode=0o600,exist_ok=True)
    with lock.open("r+") as handle:
        try:
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"LAB_MAINTENANCE_IN_PROGRESS","gpu_submits":0}
        saved=root/"service-state.json"
        if saved.exists():
            try:
                old=json.loads(saved.read_text())
            except (OSError,ValueError):
                return {"status":"BLOCKED_UNREADABLE_PRIOR_LAB_SESSION","gpu_submits":0}
            # The dispatcher *moves* a queued candidate into running before
            # any /prompt POST. No running file + empty Comfy queue means
            # a crash occurred before submit (or after a known terminal
            # result), so formerly active dev services may be restored.
            recoverable = (old.get("schema")=="firstshot-lab-service-state-v1"
                and old.get("status") in (
                    "preparing","quiesced","completed","BLOCKED_UNKNOWN_GPU_OR_QUISCE")
                and isinstance(old.get("before"),dict)
                and set(old["before"])==set(SERVICES)
                and not list((root/"running").glob("*.json")))
            if not recoverable:
                return {"status":"BLOCKED_UNRESOLVED_PRIOR_LAB_SESSION","gpu_submits":0}
            if not operations["queue_empty"]():
                return {"status":"BLOCKED_PREVIOUS_GPU_STILL_ACTIVE","gpu_submits":0}
            restored=[]
            try:
                for unit in SERVICES:
                    if old["before"][unit] and not operations["is_active"](unit):
                        operations["start"](unit)
                        restored.append(unit)
            except BaseException:
                return {"status":"BLOCKED_RESTORE_FAILED","restored":restored}
            saved.unlink()
            return {"status":"LAB_PREVIOUS_SESSION_RECOVERED","restored":restored,
                    "gpu_submits":0}
        if list((root/"review_pending").glob("*.json")):
            return {"status":"WAIT_GOLDEN_PIXEL_REVIEW","gpu_submits":0}
        if list((root/"running").glob("*.json")):
            return {"status":"BLOCKED_UNKNOWN_PREVIOUS_SUBMIT","gpu_submits":0}
        if not list((root/"pending").glob("*.json")):
            return {"status":"NO_APPROVED_WORK","gpu_submits":0}
        if not operations["queue_empty"]():
            return {"status":"BLOCKED_COMFY_QUEUE_NOT_EMPTY","gpu_submits":0}
        before={name:bool(operations["is_active"](name)) for name in SERVICES}
        snapshot={"schema":"firstshot-lab-service-state-v1",
                  "started_at":time.time(),"before":before,
                  "status":"preparing","owner_pid":os.getpid()}
        atomic(saved,snapshot)
        stopped=[]
        try:
            for name in SERVICES:
                if before[name]:
                    operations["stop"](name)
                    stopped.append(name)
            operations["pause"](QUIET_TIME_SECONDS)
            if any(operations["is_active"](unit) for unit in SERVICES):
                raise RuntimeError("known_external_submitter_still_running")
            if not operations["queue_empty"]():
                # Unknown concurrent job: do not risk bringing competing
                # submitter services back until independently inspected.
                raise RuntimeError("gpu_queue_changed_during_quiesce")
            snapshot["status"]="quiesced"
            atomic(saved,snapshot)
            run_result=operations["dispatch"]()
            if run_result.returncode:
                raise RuntimeError("dispatcher_failed_or_unknown_gpu_job")
            try:
                value=json.loads(run_result.stdout)
            except (ValueError,TypeError):
                raise RuntimeError("dispatcher_return_not_json") from None
            state=value.get("status")
            known = {
                "GPU_FINISHED_REVIEW_REQUIRED","NO_APPROVED_WORK",
                "BLOCKED_INVALID_PLAN","BLOCKED_RUN_ALREADY_EXISTS",
                "WAIT_INDEPENDENT_ORIGINAL_PIXEL_REVIEW",
            }
            if state not in known:
                raise RuntimeError("dispatcher_state_requires_manual_recovery")
            if not operations["queue_empty"]():
                raise RuntimeError("unattributed_gpu_job_after_dispatch")
            snapshot["status"]="completed"
            snapshot["dispatcher_status"]=state
            atomic(saved,snapshot)
        except BaseException as exc:
            # Fail closed: don't restart GPU-competing dev services when an
            # uncertain Comfy submit could still exist.
            snapshot["status"]="BLOCKED_UNKNOWN_GPU_OR_QUISCE"
            snapshot["reason_type"]=type(exc).__name__
            atomic(saved,snapshot)
            return {"status":snapshot["status"],"reason_type":type(exc).__name__,
                    "gpu_submits":"UNKNOWN_CHECK_HISTORY_FIRST"}
        restored=[]
        errors=[]
        for unit in reversed(stopped):
            try:
                operations["start"](unit)
                restored.append(unit)
            except BaseException as exc:
                errors.append({"unit":unit,"error":type(exc).__name__})
        if errors:
            snapshot["status"]="RESTORE_PARTIAL"
            snapshot["restored"]=restored
            snapshot["restore_errors"]=errors
            atomic(saved,snapshot)
            return {"status":"RESTORE_PARTIAL","errors":len(errors)}
        # Only on proven complete GPU and fully restored known services.
        saved.unlink()
        return {"status":"LAB_SESSION_COMPLETE","result":state,
                "restored":sorted(restored),
                "gpu_submits":"0_or_1_from_dispatcher_exact_record"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--dispatcher",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run(args.root,args.dispatcher),sort_keys=True))


if __name__=="__main__":
    main()
