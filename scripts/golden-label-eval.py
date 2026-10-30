#!/usr/bin/env python3
"""Offline, fail-closed summary of candidate-bound human labels vs shadow QA.

This tool cannot inspect pixels, authenticate reviewers, or certify G2/G3.
It never imports the render worker and never writes to game/save directories.
"""
import argparse
import json
import re
import sys
from pathlib import Path

VERDICTS = {"verified", "violated", "unobservable", "not_applicable"}
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_BYTES = 5_000_000
MAX_ROWS = 1000


def _require_hash(value, field):
    if not isinstance(value, str) or HASH.fullmatch(value) is None:
        raise ValueError(f"{field}: expected lowercase SHA-256")
    return value


def _mandatory(row, index):
    names = row.get("mandatory")
    if (not isinstance(names, list) or not names or len(names) > 32
            or any(not isinstance(n, str) or not n.strip() for n in names)
            or len(set(names)) != len(names)):
        raise ValueError(f"sample {index}: invalid mandatory fields")
    return names


def _observations(value, names, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field}: observations must be an object")
    for key in names:
        if key not in value or not isinstance(value[key], str) or value[key] not in VERDICTS:
            raise ValueError(f"{field}: missing/invalid mandatory verdict {key}")
        if value[key] == "not_applicable":
            raise ValueError(f"{field}: mandatory verdict cannot be not_applicable")
    if any(not isinstance(v, str) or v not in VERDICTS for v in value.values()):
        raise ValueError(f"{field}: invalid verdict")
    return [value[key] for key in names]


def evaluate(samples):
    if not isinstance(samples, list) or len(samples) > MAX_ROWS:
        raise ValueError("samples must be an array of at most 1000 entries")
    seen = set()
    summary = {
        "total": 0, "first_attempt": 0, "human_accepted": 0,
        "human_rejected": 0, "human_unresolved": 0,
        "false_accept": 0, "false_reject": 0,
        "unsafe_accept": 0, "unresolved_accepted": 0,
    }
    for index, row in enumerate(samples):
        if not isinstance(row, dict):
            raise ValueError(f"sample {index}: expected object")
        scene_id = row.get("scene_id")
        if not isinstance(scene_id, str) or not scene_id.strip() or scene_id in seen:
            raise ValueError(f"sample {index}: missing or duplicate scene_id")
        seen.add(scene_id)
        if type(row.get("first_attempt")) is not bool:
            raise ValueError(f"sample {index}: first_attempt must be boolean")
        _require_hash(row.get("source_state_sha256"), f"sample {index} source")
        candidate = _require_hash(row.get("candidate_sha256"), f"sample {index} candidate")
        names = _mandatory(row, index)
        human, qa = row.get("human"), row.get("qa")
        if not isinstance(human, dict) or human.get("independent") is not True:
            raise ValueError(f"sample {index}: independent human label required")
        if not isinstance(qa, dict) or qa.get("decision") not in ("accept", "reject"):
            raise ValueError(f"sample {index}: QA decision must be accept or reject")
        if (_require_hash(human.get("candidate_sha256"), "human candidate") != candidate
                or _require_hash(qa.get("candidate_sha256"), "QA candidate") != candidate):
            raise ValueError(f"sample {index}: cross-candidate evidence")
        hv = _observations(human.get("verdicts"), names, "human")
        qv = _observations(qa.get("verdicts"), names, "qa")
        truth = ("rejected" if "violated" in hv else
                 "unresolved" if "unobservable" in hv else "accepted")
        decision = qa["decision"]
        summary["total"] += 1
        summary["first_attempt"] += int(row["first_attempt"])
        summary["human_" + truth] += 1
        if truth == "rejected" and decision == "accept":
            summary["false_accept"] += 1
        if truth == "accepted" and decision == "reject":
            summary["false_reject"] += 1
        if decision == "accept" and any(v != "verified" for v in qv):
            summary["unsafe_accept"] += 1
        if truth == "unresolved" and decision == "accept":
            summary["unresolved_accepted"] += 1
    summary["independent_scene_id_count"] = len(seen)
    summary["minimum_30_scene_ids_present"] = len(seen) >= 30
    summary["release_status"] = "NO_GO_SOURCE_ONLY"
    summary["limitations"] = (
        "Reviewer independence, scene independence and original pixels are "
        "not authenticated; no G2/G3 or E2E certification."
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Private local JSON: {samples:[...]}")
    args = parser.parse_args(argv)
    try:
        if args.dataset.stat().st_size > MAX_BYTES:
            raise ValueError("dataset exceeds 5 MB")
        data = json.loads(args.dataset.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"samples"}:
            raise ValueError("dataset must contain only a samples array")
        print(json.dumps(evaluate(data["samples"]), sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"INVALID_DATASET: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
