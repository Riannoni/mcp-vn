#!/usr/bin/env python3
"""Independent SHA-bound review receipt for lab candidates, never a QA shortcut."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import io
import sqlite3
import sys

from PIL import Image, ImageFile

# Native teamctl #76 is the authority for an independently accepted task;
# an arbitrary G-999 string in a user-authored JSON is not.
NATIVE_ROOT = Path.home() / ".local/share/web-vn-native-team/run-20261031-full"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native_team"))
import golden_evidence as native_golden


def _full_png(raw, *, require_rgba=False):
    if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > 64_000_000 or ImageFile.LOAD_TRUNCATED_IMAGES:
        raise ValueError("original_or_derived_png_invalid")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG" or not (1 <= image.width <= 8192 and 1 <= image.height <= 8192):
                raise ValueError("original_or_derived_png_invalid")
            dims = image.size
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if require_rgba and (
                image.mode != "RGBA" or image.getchannel("A").getextrema() != (0, 255)
            ):
                raise ValueError("derived_sprite_alpha_invalid")
            if image.size != dims:
                raise ValueError("png_dimensions_changed")
            return dims
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("original_or_derived_png_undecodable") from exc


def _trusted_original_review(candidate, review):
    """Check accepted native task, immutable receipt, original source contract.

    This proves provenance/receipt integrity only. Neither this SQL check nor
    native teamctl proves a reviewer actually perceived semantic pixels.
    """
    database = NATIVE_ROOT / "state/team.sqlite3"
    if not database.is_file() or database.is_symlink():
        raise ValueError("trusted_visual_review_database_missing")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT t.action,t.state,t.result,v.spec_sha256,v.spec_json,"
            "r.reviewer,r.approved,r.g2,r.png_sha256 FROM task t "
            "JOIN visual_task v ON v.task_id=t.id "
            "JOIN visual_review r ON r.task_id=t.id WHERE t.id=?",
            (review["reviewer_task"],),
        ).fetchone()
    if row is None or row["action"] != "visual_evidence" or row["state"] != "done" or row["approved"] != 1:
        raise ValueError("trusted_visual_review_not_independently_approved")
    spec = json.loads(row["spec_json"])
    record = json.loads(row["result"])
    if hashlib.sha256(row["spec_json"].encode()).hexdigest() != row["spec_sha256"]:
        raise ValueError("trusted_visual_spec_changed")
    mandatory = native_golden._verified_spec(spec)
    if (spec["task_id"] != review["reviewer_task"] or
            spec["prompt_id"] != candidate.get("prompt_id") or
            spec["case_id"] != candidate.get("case") or
            spec["artifacts"]["original_png"]["sha256"] != candidate.get("png_sha256") or
            spec["artifacts"]["original_png"]["path"] != candidate.get("original_png_path")):
        raise ValueError("trusted_visual_wrong_candidate")
    submitted_by, generator, independent = (
        record.get("submitted_by"), spec["generator_owner"], row["reviewer"]
    )
    if not all(isinstance(x, str) and len(x) >= 3 for x in (submitted_by, generator, independent)):
        raise ValueError("trusted_visual_reviewer_missing")
    if len({submitted_by, generator, independent}) != 3:
        raise ValueError("trusted_visual_self_approval")
    if (record.get("status") != "visual-evidence-only" or
            record.get("task_id") != spec["task_id"] or
            record.get("spec_sha256") != row["spec_sha256"] or
            record.get("prompt_id") != candidate.get("prompt_id") or
            record.get("png_sha256") != candidate.get("png_sha256") or
            row["png_sha256"] != candidate.get("png_sha256") or
            record.get("g2") != row["g2"]):
        raise ValueError("trusted_visual_record_mismatch")
    rel = record.get("path")
    if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
        raise ValueError("trusted_visual_receipt_path_invalid")
    receipt_dir = (NATIVE_ROOT / "evidence/golden/immutable").resolve()
    receipt_path = NATIVE_ROOT / rel
    if receipt_path.is_symlink() or receipt_path.resolve().parent != receipt_dir or not receipt_path.is_file():
        raise ValueError("trusted_visual_receipt_missing")
    raw = receipt_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record.get("sha256"):
        raise ValueError("trusted_visual_receipt_changed")
    trusted = json.loads(raw)
    label = native_golden._validated_receipt(
        trusted, spec, submitted_by, trusted.get("fence"), mandatory
    )
    if label != row["g2"]:
        raise ValueError("trusted_visual_verdict_changed")
    if not isinstance(review.get("mandatory"), dict) or set(review["mandatory"]) != set(mandatory):
        raise ValueError("trusted_visual_mandatory_reduced")
    for key in mandatory:
        if review["mandatory"][key] != trusted["mandatory"][key]["verdict"]:
            raise ValueError("trusted_visual_verdict_not_from_reviewer")
    original_raw = native_golden._private_file(spec["artifacts"]["original_png"], "original_png")
    _full_png(original_raw)
    return mandatory


def _trusted_sprite_derivative(root, name, candidate):
    if candidate.get("factor") != "sdxl_sprite_body_source":
        if "derived_rgba_sha256" in candidate or "derived_rgba_path" in candidate:
            raise ValueError("unbound_sprite_derivative")
        return
    if candidate.get("postprocess_status") == "BLOCKED_UNSAFE":
        raise ValueError("sprite_postprocess_blocked")
    if candidate.get("original_png_sha256") != candidate.get("png_sha256"):
        raise ValueError("sprite_original_sha_mismatch")
    path_value = candidate.get("derived_rgba_path")
    expected = candidate.get("derived_rgba_sha256")
    if (not isinstance(path_value, str) or not isinstance(expected, str)
            or re.fullmatch(r"[a-f0-9]{64}", expected) is None):
        raise ValueError("sprite_derivative_missing")
    path = Path(path_value)
    private_run = (root / "runs" / name).resolve()
    if path.is_symlink() or not path.is_file() or path.resolve().parent != private_run:
        raise ValueError("sprite_derivative_missing_or_untrusted")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("sprite_derivative_sha_mismatch")
    original_size = _full_png(Path(candidate["original_png_path"]).read_bytes())
    if _full_png(raw, require_rgba=True) != original_size:
        raise ValueError("sprite_derivative_canvas_mismatch")


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
    # Integrity preflight MUST precede every terminal review mutation.
    _trusted_original_review(candidate, review)
    _trusted_sprite_derivative(root, name, candidate)
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
