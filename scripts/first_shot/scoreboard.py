#!/usr/bin/env python3
"""Fail-closed scoreboard for real FIRST GPU outputs and independent original-pixel reviews.

No model calls, no GPU calls, no game or published asset writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

CASE_IDS=("BG-01","SPR-01","CG-01","CG-02","CG-03")
VERDICTS={"verified","violated","unobservable","not_applicable"}
REVIEWED=("verified","not_applicable")

def evaluate(root):
    root=Path(root).expanduser().resolve()
    rows=[]
    seen=set()
    for case in CASE_IDS:
        result_file=root/(case+"-result.json")
        review_file=root/(case+"-pixel-review.json")
        row={"case":case,"g1":"NOT_MEASURED","g2":"NOT_REVIEWED","first_attempt":None,
             "submit_to_png_seconds":None,"failures":[]}
        if not result_file.is_file():
            row["failures"].append("no_first_gpu_result")
            rows.append(row)
            continue
        r=json.loads(result_file.read_text())
        row["g1"]=r.get("g1","NOT_MEASURED")
        row["first_attempt"]=r.get("first_attempt")
        row["submit_to_png_seconds"]=r.get("total_submit_to_output_seconds")
        if r.get("case")!=case or row["first_attempt"]!=1 or r.get("g1")!="PASS":
            row["failures"].append("invalid_first_attempt_or_G1")
            rows.append(row)
            continue
        pid=r.get("prompt_id")
        sha=r.get("png_sha256")
        if not isinstance(pid,str) or not isinstance(sha,str) or len(sha)!=64:
            row["failures"].append("missing_exact_prompt_or_png_sha")
            rows.append(row)
            continue
        if pid in seen:
            row["failures"].append("repeated_prompt_id")
            rows.append(row)
            continue
        seen.add(pid)
        original=Path(r.get("original_png_path",""))
        if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest()!=sha:
            row["failures"].append("original_pixel_hash_mismatch")
            rows.append(row)
            continue
        if not review_file.is_file():
            row["failures"].append("original_pixels_not_reviewed")
            rows.append(row)
            continue
        review=json.loads(review_file.read_text())
        if review.get("case")!=case or review.get("png_sha256")!=sha or review.get("prompt_id")!=pid:
            row["failures"].append("review_not_linked_to_exact_prompt_png")
            rows.append(row)
            continue
        if review.get("original_pixels_reviewed") is not True:
            row["failures"].append("original_pixels_not_directly_reviewed")
            rows.append(row)
            continue
        checks=review.get("checks")
        if not isinstance(checks,dict) or not checks:
            row["failures"].append("missing_scene_checks")
            rows.append(row)
            continue
        mandatory=review.get("mandatory",[])
        if not mandatory or any(field not in checks for field in mandatory):
            row["failures"].append("missing_mandatory_scene_fields")
            rows.append(row)
            continue
        if any(x not in VERDICTS for x in checks.values()):
            row["failures"].append("invalid_check_verdict")
            rows.append(row)
            continue
        failed=[field for field in mandatory if checks[field]!="verified"]
        if failed:
            row["failures"].extend("mandatory_"+field+":"+checks[field] for field in failed)
            row["g2"]="FAIL"
        else:
            row["g2"]="PASS"
        rows.append(row)
    measured=[row["submit_to_png_seconds"] for row in rows if isinstance(row["submit_to_png_seconds"],(int,float))]
    return {"schema":"first-shot-score-v1","cases":rows,
            "g1_pass":sum(r["g1"]=="PASS" for r in rows),
            "g2_pass":sum(r["g2"]=="PASS" for r in rows),
            "five_frame_complete":sum(r["g2"]=="PASS" for r in rows)==5,
            "under_20_sec":sum(isinstance(x,(int,float)) and x<=20 for x in measured),
            "gpu_submit_to_png_p50_seconds":statistics.median(measured) if measured else None,
            "gpu_submit_to_png_max_seconds":max(measured) if measured else None,
            "human_labeled_cases":0,
            "g3":"NO_GO"}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--lab-dir",required=True)
    args=p.parse_args()
    print(json.dumps(evaluate(args.lab_dir),sort_keys=True,indent=2))
