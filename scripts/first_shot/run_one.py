#!/usr/bin/env python3
"""One-shot, opt-in, source-frozen private Comfy GPU probe. No publish/game writes.

G1 only. G2 needs a separate visual review of the exact original bytes.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "worker"))
from zimage_backend import create_graph
PACK = Path(__file__).with_name("pack-v1.json")
COMFY = "http://127.0.0.1:8188"
REVIEW_FIELDS = ["environment", "named_principals", "identity", "wardrobe", "props",
                 "landmarks", "pose", "contact", "camera", "sprite_alpha"]


def now():
    return datetime.now(timezone.utc).isoformat()


def api(path, data=None, timeout=8):
    req = urllib.request.Request(
        COMFY + path,
        data=None if data is None else json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def queue_empty():
    q = api("/queue")
    if not isinstance(q, dict):
        raise RuntimeError("Unexpected Comfy /queue shape")
    return not q.get("queue_running") and not q.get("queue_pending")


def load_case(case_id):
    p = json.loads(PACK.read_text())
    cases = [v for v in p["cases"] if v["id"] == case_id]
    if len(cases) != 1:
        raise ValueError("Unknown or ambiguous frozen case")
    c = cases[0]
    if c["canvas"][0] > 1024 or c["canvas"][1] > 1024:
        raise ValueError("Invalid bounded canary canvas")
    return c


def write_atomic(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def preflight(case, exp):
    if not queue_empty():
        raise RuntimeError("GPU_QUEUE_BUSY: another Comfy job exists")
    prefix = "vn_zimage_probe_fs_" + case["id"].lower().replace("-", "_") + "_"
    prefix += hashlib.sha256((case["id"] + str(case["seed"])).encode()).hexdigest()[:10]
    graph = create_graph(case["prompt"], seed=case["seed"], prefix=prefix,
                         width=case["canvas"][0], height=case["canvas"][1],
                         private_unanchored=True)
    if graph["10"]["inputs"]["filename_prefix"] != prefix:
        raise RuntimeError("Unexpected output prefix")
    graph_digest = hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()
    return graph, graph_digest, prefix


def run(case_id, outdir, submit=False, max_seconds=90):
    case = load_case(case_id)
    outdir = outdir.expanduser().resolve()
    outdir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(outdir, 0o700)
    lockdir = outdir.parent
    lockdir.mkdir(parents=True, exist_ok=True)
    with (lockdir / "gpu-exclusive-lab.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        graph, graph_digest, prefix = preflight(case, outdir)
        if not submit:
            return {"case":case_id, "status":"PREFLIGHT_ONLY", "graph_sha256":graph_digest,
                    "queue_empty":True, "gpu_jobs":0, "g2":"NOT_REVIEWED"}
        resultfile = outdir / (case_id + "-result.json")
        if resultfile.exists():
            raise RuntimeError("One-shot evidence already exists, do not rerun")
        # Store frozen source graph privately, before submission, no public prompt leak.
        write_atomic(outdir / (case_id + "-private-graph.json"), graph)
        record = {"schema":"private-first-shot-v1", "case":case_id, "started_at":now(),
                  "first_attempt":1, "model":"z_image_turbo_bf16_fp8_scaled_1.safetensors",
                  "seed":case["seed"], "expected":case["expected"],
                  "graph_sha256":graph_digest, "status":"PREPARED",
                  "g1":"NOT_MEASURED", "g2":"NOT_REVIEWED",
                  "original_pixels_reviewed":False, "published":False}
        write_atomic(resultfile, record)
        if not queue_empty():
            record["status"]="BLOCKED_QUEUE_CHANGED"
            write_atomic(resultfile, record)
            raise RuntimeError("Queue changed between graph creation and submit")
        start = time.monotonic()
        # One and only one direct Comfy submission, isolated filename prefix.
        reply = api("/prompt", {"prompt":graph, "client_id":"vn-first-shot-canary"}, timeout=12)
        prompt_id = reply.get("prompt_id")
        if not isinstance(prompt_id,str) or len(prompt_id)<8:
            record["status"]="UNKNOWN_SUBMISSION"
            write_atomic(resultfile, record)
            raise RuntimeError("No trusted prompt_id: STOP, do not retry")
        record["prompt_id"]=prompt_id
        record["status"]="SUBMITTED"
        record["submit_seconds"]=round(time.monotonic()-start,3)
        write_atomic(resultfile, record)
        deadline=start+max_seconds
        history=None
        while time.monotonic()<deadline:
            h=api("/history/"+prompt_id, timeout=8)
            if prompt_id in h:
                history=h[prompt_id]
                break
            time.sleep(1.0)
        if history is None:
            record["status"]="TIMEOUT_STOP_NO_RETRY"
            record["observed_wall_seconds"]=round(time.monotonic()-start,3)
            write_atomic(resultfile,record)
            raise RuntimeError("Timeout; UNKNOWN ongoing GPU job, do not resubmit")
        if history.get("status",{}).get("status_str")=="error":
            record["status"]="GPU_ERROR_STOP"
            write_atomic(resultfile,record)
            raise RuntimeError("Comfy history indicates error")
        images=[item for node in history.get("outputs",{}).values()
                for item in node.get("images",[]) if isinstance(item,dict)]
        acceptable=[x for x in images
                    if isinstance(x.get("filename"),str) and x["filename"].startswith(prefix)
                    and x.get("type","output")=="output" and not x.get("subfolder")]
        if len(acceptable)!=1:
            record["status"]="AMBIGUOUS_OUTPUT_STOP"
            record["candidate_count"]=len(acceptable)
            write_atomic(resultfile,record)
            raise RuntimeError("Cannot establish exact one output image")
        from PIL import Image
        image=acceptable[0]["filename"]
        output_dir=Path.home()/".local/share/mcp-vn-comfy/output"
        source=(output_dir/image).resolve()
        if not source.is_relative_to(output_dir.resolve()) or not source.is_file():
            raise RuntimeError("Unsafe/missing Comfy output")
        raw=source.read_bytes()
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Comfy output not a PNG")
        with Image.open(source) as im:
            im.verify()
            size=list(im.size)
        record.update(status="GPU_FINISHED_G2_PENDING",g1="PASS",png_sha256=hashlib.sha256(raw).hexdigest(),
                      original_png_path=str(source),canvas=size,
                      total_submit_to_output_seconds=round(time.monotonic()-start,3),
                      completed_at=now())
        write_atomic(resultfile,record)
        return {k:record[k] for k in ("case","status","prompt_id","png_sha256","canvas",
                                      "total_submit_to_output_seconds","g1","g2")}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--outdir", type=Path,required=True)
    p.add_argument("--submit",action="store_true",help="EXPLICIT opt-in to ONE GPU job")
    p.add_argument("--max-seconds",type=int,default=90)
    args=p.parse_args()
    if not 25<=args.max_seconds<=180:raise ValueError("bad max-seconds")
    result=run(args.case,args.outdir,args.submit,args.max_seconds)
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
