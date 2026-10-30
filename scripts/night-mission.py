#!/usr/bin/env python3
"""Deterministic source-only P0 mission selection for web-vn night agent.

Never trusts the model to close an issue or merge. Max two cycles per task;
skipped tasks remain explicitly BLOCKED, not completed.
"""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.home() / ".local/share/web-vn-night-runner"
WORK = ROOT / "work/web-vn"
PR49_REF = "refs/remotes/origin/pr-49"

# Order derives from render-v1 #20, draft #49 and handoff 2026-10-31.
# No GPU, no production, no private assets, no public issue closures.
STAGES = [
    ("pr49-review", "#49 / #32", "Review existing PR #49 source against this checkout with git show refs/remotes/origin/pr-49:worker/atomic_prop_gate.py; DO NOT reimplement a duplicate. Reconcile the local source and strict tests; document exact deltas and the evidence gap. No automatic merge."),
    ("shadow-adapter", "#49 / #32", "Implement/verify a read-only shadow adapter for required objects, two-hand contact and provenance. Couple exact actor+scene+observation IDs with no publication; no runtime wiring. Add negative contract tests."),
    ("shadow-replay", "#2 / #32", "Build a privacy-safe offline replay harness for shadow QA on synthetic, pre-labeled CG contract/evidence JSON. Track false_accept, false_reject, unobservable and latency. No access to private images/GPU."),
    ("object-regression", "#32 / #44", "Expand hostile synthetic object/landmark/contact cases: missing map, wrong fruit basket, ambiguous target, oversized box, disconnected wrist, multiple actors, occluded hands. Fail closed; measure outputs."),
    ("wardrobe-contract", "#23 / #31", "Add source-only outfit/identity continuity contract fixtures: separate actor face anchor from historical body/clothing, verify current outfit per actor. Negative tests; no neural image claims."),
    ("cast-observability", "#3 / #24", "Improve source-only principal vs ambient extras and unobservable actor matching contract tests. Avoid classifying backgrounds as extra named actors, never mark uncertain as verified."),
    ("version-fence", "#6 / #10", "Add offline idempotency/restart/version-fence regression tests using synthetic scene snapshots; stale asynchronous candidates cannot be published."),
    ("golden-harness", "#2 / #20", "Build golden-set human-review manifest/schema and neutral evaluation CLI to support >=30 externally labeled real CG scenes later. Do not fabricate labels or claim G2/G3 PASS."),
]

MAX_ATTEMPTS_PER_STAGE = 2


def read(path):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def checkpoint_name(step):
    return "NIGHT_TASK_RESULT_" + step + ".json"


def test_evidence(step):
    """Only fixed read-only test discovery; never shell-eval the LLM's commands."""
    timeout = 70
    if step in ("pr49-review", "shadow-adapter", "shadow-replay", "object-regression"):
        pattern = "atomic-prop*.test.py"
    else:
        pattern = "*.test.py"
    try:
        command = ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", pattern]
        result = subprocess.run(command, cwd=WORK, capture_output=True, text=True, timeout=timeout)
        combined = (result.stdout + "\n" + result.stderr)[-1400:]
        return result.returncode == 0 and "Ran " in combined, "passed" if result.returncode == 0 and "Ran " in combined else "tests_failed"
    except (OSError, subprocess.TimeoutExpired):
        return False, "test_unavailable"


def next_task(run_dir):
    manifest = Path(run_dir) / "mission-state.json"
    state = read(manifest)
    if not state:
        state = {
            "scope": "render-v1-p0", "stage_index": 0,
            "attempts": 0, "last_selection": None, "history": [],
        }
    if state["stage_index"] >= len(STAGES):
        state["active"] = None
        state["outcome"] = "all_source_stages_attempted_requires_human_visual_gate"
        write(manifest, state)
        return {"status": "requires_human", "reason": state["outcome"]}
    previous = state.get("last_selection")
    if previous:
        step, issue, goal = STAGES[state["stage_index"]]
        result_file = WORK / checkpoint_name(step)
        evidence = read(result_file)
        done = evidence.get("stage_id") == step and evidence.get("status") == "source_completed"
        if done:
            passed, check = test_evidence(step)
            if passed:
                state["history"].append({"stage_id": step, "status": "source_completed", "evidence": check})
                state["stage_index"] += 1
                state["attempts"] = 0
            else:
                state["history"].append({"stage_id": step, "status": "blocked", "reason": check})
                state["stage_index"] += 1
                state["attempts"] = 0
        elif state["attempts"] >= MAX_ATTEMPTS_PER_STAGE:
            state["history"].append({
                "stage_id": step, "status": "blocked",
                "reason": "max_bounded_attempts_no_verified_checkpoint"
            })
            state["stage_index"] += 1
            state["attempts"] = 0
    if state["stage_index"] >= len(STAGES):
        state["active"] = None
        state["outcome"] = "all_source_stages_attempted_requires_human_visual_gate"
        write(manifest, state)
        return {"status": "requires_human", "reason": state["outcome"]}
    stage, issue, goal = STAGES[state["stage_index"]]
    state["attempts"] += 1
    state["last_selection"] = stage
    state["active"] = {"stage_id": stage, "issue": issue, "attempt": state["attempts"]}
    state["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    write(manifest, state)
    note = (
        "MISSION stage_id=" + stage + " (" + issue + "), bounded attempt "
        + str(state["attempts"]) + "/" + str(MAX_ATTEMPTS_PER_STAGE) + ". "
        + goal + " Before writing any file inspect the CURRENT source and PR #49. "
        "Do not duplicate implemented work. Read current NIGHT_HANDOFF.md and latest "
        "source issues, but don't pull new changes into a dirty worktree. "
        "When source-level acceptance is supported by specific tests, write "
        + checkpoint_name(stage)
        + ' with JSON {"stage_id":"' + stage + '","status":"source_completed"} '
        "plus evidence description in NIGHT_HANDOFF.md. "
        "If incomplete, DO NOT fake completion; do not write a completion checkpoint. "
        "Model assertions without independent tests cannot close this stage or issue. "
        "When blocked, report exact blocker; next stage is chosen autonomously. "
        "All tasks contribute to render-v1 #20; G2/G3 remain unverified."
    )
    return {"status": "ready", "stage_id": stage, "issue": issue,
            "attempt": state["attempts"], "instruction": note,
            "history_size": len(state["history"])}


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "next":
        print("Usage: night-mission.py next RUN_DIRECTORY", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[2]).resolve()
    expected = (ROOT / "runs").resolve()
    if run_dir.parent != expected:
        print("Invalid run directory", file=sys.stderr)
        return 2
    print(json.dumps(next_task(run_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
