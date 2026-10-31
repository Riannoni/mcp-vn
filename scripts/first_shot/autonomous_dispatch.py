#!/usr/bin/env python3
"""Local bounded GPU candidate executor for worker-authored one-factor proposals.

Never generates prompts or G2 verdicts. No model/API billing.
Use --tick from a one-minute systemd timer; no GPU work without an explicit
worker-proposed, frozen, SHA-checked, queued hypothesis.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "worker"))
sys.path.insert(0, str(HERE))
import zimage_backend as z
import run_one as r

ID = re.compile(r"^[A-Z][A-Z0-9_-]{5,55}$")
ALLOWED = {"prompt_text"}
STATES = ("pending", "running", "review_pending", "blocked", "reviewed")
MAX_WALL_SECONDS = 90


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def base_sha(case_id):
    c = r.load_case(case_id)
    return sha(json.dumps(c, sort_keys=True, separators=(",", ":")).encode())


def validate(p):
    if not isinstance(p, dict) or set(p) != {
        "schema", "id", "case", "base_case_sha256", "factor",
        "new_value", "hypothesis", "falsifier", "author_task"
    }:
        raise ValueError("unrecognized_plan_schema")
    if p["schema"] != "firstshot_one_factor_v1" or not isinstance(p["id"], str) or not ID.fullmatch(p["id"]):
        raise ValueError("invalid_id")
    if p["factor"] not in ALLOWED:
        raise ValueError("unverified_multi_factor_or_control_graph")
    if p["base_case_sha256"] != base_sha(p["case"]):
        raise ValueError("baseline_case_changed")
    if not isinstance(p["author_task"], str) or not re.fullmatch(r"R-[0-9]{1,4}", p["author_task"]):
        raise ValueError("not_renderer_authored")
    if not isinstance(p["hypothesis"], str) or not 30 <= len(p["hypothesis"]) <= 700:
        raise ValueError("hypothesis_not_falsifiable")
    if not isinstance(p["falsifier"], str) or not 30 <= len(p["falsifier"]) <= 700:
        raise ValueError("no_explicit_falsifier")
    value = p["new_value"]
    if not isinstance(value, str) or not 10 <= len(value) <= 5000 or "\x00" in value:
        raise ValueError("invalid_prompt")
    if value == r.load_case(p["case"])["prompt"]:
        raise ValueError("no_actual_changed_factor")
    return p


def setup(root):
    root = Path(root).expanduser().resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    for stage in STATES:
        (root / stage).mkdir(mode=0o700, exist_ok=True)
    return root


def queue(root, p):
    root = setup(root)
    p = validate(p)
    # G2 review must finish before next hypothesis to avoid blind rerender.
    if list((root / "running").glob("*.json")) or list((root / "review_pending").glob("*.json")):
        return {"enqueued": False, "reason": "one_candidate_requires_review"}
    if any((root / stage / (p["id"] + ".json")).exists() for stage in STATES):
        return {"enqueued": False, "reason": "experiment_id_already_used"}
    if list((root / "pending").glob("*.json")):
        return {"enqueued": False, "reason": "pending_candidate_exists"}
    atomic(root / "pending" / (p["id"] + ".json"), p)
    return {"enqueued": True, "id": p["id"]}


def tick(root):
    root = setup(root)
    with (root.parent.parent / "gpu-exclusive-lab.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "GPU_OWNER_LOCK_BUSY"}
        pending_review = sorted((root / "review_pending").glob("*.json"))
        if pending_review:
            return {"status": "WAIT_INDEPENDENT_ORIGINAL_PIXEL_REVIEW",
                    "id": pending_review[0].stem}
        incomplete = sorted((root / "running").glob("*.json"))
        if incomplete:
            return {"status": "STOP_UNKNOWN_PREVIOUS_SUBMISSION",
                    "id": incomplete[0].stem}
        todo = sorted((root / "pending").glob("*.json"))
        if not todo:
            return {"status": "NO_APPROVED_WORK"}
        path = todo[0]
        try:
            p = validate(json.loads(path.read_text()))
        except Exception as exc:
            path.replace(root / "blocked" / path.name)
            return {"status": "BLOCKED_INVALID_PLAN", "detail": type(exc).__name__}
        if not r.queue_empty():
            return {"status": "GPU_QUEUE_BUSY_DEFER", "id": p["id"]}
        case = r.load_case(p["case"])
        prefix = "vn_zimage_probe_ab_" + p["id"].lower() + "_"
        graph = z.create_graph(p["new_value"], seed=case["seed"], prefix=prefix,
                               width=case["canvas"][0], height=case["canvas"][1],
                               private_unanchored=True)
        graph_sha = sha(json.dumps(graph, sort_keys=True).encode())
        record = dict(p)
        record.update(status="PREPARED_NOT_SUBMITTED",
                      started_utc=datetime.now(timezone.utc).isoformat(),
                      source_pack_case_sha256=base_sha(p["case"]),
                      graph_sha256=graph_sha, first_attempt=2,
                      g1="NOT_MEASURED", g2="NOT_REVIEWED",
                      changed_factors=["prompt_text"], published=False)
        work = root / "runs" / p["id"]
        if work.exists():
            path.replace(root / "blocked" / path.name)
            return {"status": "BLOCKED_RUN_ALREADY_EXISTS"}
        work.mkdir(mode=0o700, parents=True)
        atomic(work / "graph-private.json", graph)
        atomic(work / "result.json", record)
        running_path = root / "running" / path.name
        path.replace(running_path)
        if not r.queue_empty():
            record["status"] = "STOP_QUEUE_CHANGED_BEFORE_SUBMIT"
            atomic(work / "result.json", record)
            return {"status": record["status"]}
        t = time.monotonic()
        try:
            answer = r.api("/prompt", {"prompt": graph, "client_id": "firstshot-autonomous-lab"},
                           timeout=12, idempotency_key="first-shot-ab:" + p["id"])
            pid = answer.get("prompt_id")
            if not isinstance(pid, str) or len(pid) < 8:
                raise RuntimeError("untrusted_comfy_prompt_id")
            record["prompt_id"] = pid
            record["status"] = "SUBMITTED"
            atomic(work / "result.json", record)
            history = None
            while time.monotonic() - t < MAX_WALL_SECONDS:
                h = r.api("/history/" + pid, timeout=8)
                if pid in h:
                    history = h[pid]
                    break
                time.sleep(1)
            if history is None:
                raise RuntimeError("TIMEOUT_UNKNOWN_GPU_JOB_NO_RETRY")
            if history.get("status", {}).get("status_str") == "error":
                raise RuntimeError("COMFY_REPORTED_ERROR")
            outputs = [item for node in history.get("outputs", {}).values()
                       for item in node.get("images", []) if isinstance(item, dict)]
            matched = [x for x in outputs if isinstance(x.get("filename"), str)
                       and x["filename"].startswith(prefix)
                       and x.get("type", "output") == "output" and not x.get("subfolder")]
            if len(matched) != 1:
                raise RuntimeError("not_exactly_one_original_png")
            output_root = Path.home() / ".local/share/mcp-vn-comfy/output"
            png = (output_root / matched[0]["filename"]).resolve()
            if not png.is_relative_to(output_root.resolve()):
                raise RuntimeError("nonlocal_output_path")
            raw = png.read_bytes()
            if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("invalid_png")
            from PIL import Image
            with Image.open(png) as im:
                im.verify()
                size = list(im.size)
            record.update(status="GPU_FINISHED_REVIEW_REQUIRED", g1="PASS",
                          png_sha256=sha(raw), original_png_path=str(png),
                          canvas=size, gpu_submit_to_png_seconds=round(time.monotonic()-t, 3),
                          completed_utc=datetime.now(timezone.utc).isoformat())
            atomic(work / "result.json", record)
            running_path.replace(root / "review_pending" / running_path.name)
            return {"status": record["status"], "id": p["id"],
                    "prompt_id": pid, "png_sha256": record["png_sha256"],
                    "submit_to_png_seconds": record["gpu_submit_to_png_seconds"]}
        except BaseException as exc:
            record["status"] = "STOP_UNKNOWN_OR_FAILED_NO_RETRY"
            record["error_type"] = type(exc).__name__
            # Keep original in running: an unknown externally submitted job
            # must never be automatically re-executed or silently released.
            atomic(work / "result.json", record)
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["queue", "tick"])
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--plan", type=Path)
    args = ap.parse_args()
    if args.action == "queue":
        if not args.plan:
            ap.error("--plan required")
        out = queue(args.root, json.loads(args.plan.read_text()))
    else:
        out = tick(args.root)
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
