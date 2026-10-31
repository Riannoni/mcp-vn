#!/usr/bin/env python3
"""Independent SHA-bound review receipt for lab candidates, never a QA shortcut."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

VALID = {"verified", "violated", "unobservable", "not_applicable"}

def audit(root, file):
    root = Path(root).expanduser().resolve()
    review = json.loads(Path(file).read_text())
    required = {"experiment_id", "reviewer_task", "prompt_id", "png_sha256",
                "original_pixels_reviewed", "mandatory", "observations"}
    if not isinstance(review, dict) or set(review) != required:
        raise ValueError("review_schema_invalid")
    name = review["experiment_id"]
    if not isinstance(name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_-]{5,55}", name):
        raise ValueError("bad_experiment_id")
    if not re.fullmatch(r"G-[0-9]{1,4}", str(review["reviewer_task"])):
        raise ValueError("not_independent_golden_task")
    if review["original_pixels_reviewed"] is not True:
        raise ValueError("original_pixels_not_seen")
    checks = review["mandatory"]
    if not isinstance(checks, dict) or not checks:
        raise ValueError("no_checked_scene_contract")
    if any(v not in VALID or v == "not_applicable" for v in checks.values()):
        raise ValueError("invalid_or_skipped_mandatory")
    if not isinstance(review["observations"], str) or len(review["observations"]) < 35:
        raise ValueError("not_enough_direct_visual_evidence")
    waiting = root / "review_pending" / (name + ".json")
    result_file = root / "runs" / name / "result.json"
    if not waiting.is_file() or not result_file.is_file():
        raise ValueError("candidate_not_waiting_review")
    candidate = json.loads(result_file.read_text())
    if candidate.get("status") != "GPU_FINISHED_REVIEW_REQUIRED":
        raise ValueError("no_confirmed_original_gpu_output")
    if candidate.get("prompt_id") != review["prompt_id"] or candidate.get("png_sha256") != review["png_sha256"]:
        raise ValueError("review_not_bound_to_exact_gpu_output")
    image = Path(candidate["original_png_path"])
    if not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != review["png_sha256"]:
        raise ValueError("original_png_missing_or_changed")
    # This public text-only benchmark has no canonical identity reference. It
    # cannot produce a release G2 PASS even if all visible facts look good.
    label = "FAIL" if "violated" in checks.values() else "UNVERIFIED"
    target = root / "runs" / name / "golden-review.json"
    if target.exists():
        raise ValueError("review_replay")
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(review, sort_keys=True, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    candidate["g2"] = label
    candidate["independent_review_task"] = review["reviewer_task"]
    stage = result_file.with_suffix(".json.tmp")
    stage.write_text(json.dumps(candidate, sort_keys=True, indent=2) + "\n")
    os.chmod(stage, 0o600)
    os.replace(stage, result_file)
    waiting.replace(root / "reviewed" / waiting.name)
    return {"status": "REVIEW_RECORDED", "id": name, "g2": label}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--review", required=True)
    a = p.parse_args()
    print(json.dumps(audit(a.root, a.review), sort_keys=True))
