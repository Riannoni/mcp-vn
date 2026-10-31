#!/usr/bin/env python3
"""Offline QA-vs-human confusion matrix over private, declared frame labels.

No image bytes are loaded and no claims of independent pixel review or G2/G3
certification are made. The input schema is a JSON object:
  {"schema_version": 1, "cases": [
    {"scene_id": "unique-scene", "provenance": {"png_sha256": "64 hex"},
     "human_label": {"status": "verified|violated|unknown|unobservable",
                     "reviewed_png_sha256": "same digest"},
     "qa": {"status": "passed|rejected|unknown|unobservable",
            "png_sha256": "same digest"}}]}

Human "verified" means the scene meets all mandatory conditions *as declared
by the reviewer*, "violated" means it fails at least one mandatory condition.
Human unknown/unobservable cases are excluded from the binary confusion
matrix, not silently treated as positives or negatives. QA unknown/
unobservable on determinate human labels are abstentions, not false rejects.
All assertions are untrusted metadata until independent original-pixel review.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
HUMAN = frozenset(("verified", "violated", "unknown", "unobservable"))
QA = frozenset(("passed", "rejected", "unknown", "unobservable"))


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name}: expected object")
    return value


def _status(value: Any, valid: frozenset[str], name: str) -> str:
    if not isinstance(value, str) or value not in valid:
        raise ValueError(f"{name}: missing or invalid explicit status")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"{name}: missing or invalid SHA-256")
    return value


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize_quality(document: Any) -> dict[str, Any]:
    """Compute descriptive metrics only; reject invalid/mismatched labels.

    This is not a visual reviewer, an unbiased dataset audit, or a release
    decision. In particular, absent denominator returns null, never 0%.
    """
    root = _object(document, "root")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        raise ValueError("root: unsupported schema_version")
    cases = root.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("root: cases must be a non-empty array")

    counts = {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
    human_unknown = human_unobservable = 0
    qa_unknown_on_labeled = qa_unobservable_on_labeled = 0
    unsafe_pass_on_unlabeled = 0
    seen_scenes: set[str] = set()
    seen_pngs: set[str] = set()

    for index, raw in enumerate(cases):
        case = _object(raw, f"case[{index}]")
        scene = case.get("scene_id")
        if not isinstance(scene, str) or not scene.strip():
            raise ValueError(f"case[{index}].scene_id: missing or invalid")
        if scene in seen_scenes:
            raise ValueError(f"case[{index}].scene_id: duplicate")
        seen_scenes.add(scene)

        provenance = _object(case.get("provenance"), f"case[{index}].provenance")
        png = _sha(provenance.get("png_sha256"), f"case[{index}].provenance.png_sha256")
        if png in seen_pngs:
            raise ValueError(f"case[{index}].provenance.png_sha256: duplicate")
        seen_pngs.add(png)

        human = _object(case.get("human_label"), f"case[{index}].human_label")
        qa = _object(case.get("qa"), f"case[{index}].qa")
        human_status = _status(human.get("status"), HUMAN, f"case[{index}].human_label")
        qa_status = _status(qa.get("status"), QA, f"case[{index}].qa")
        for field, value in (("human_label.reviewed_png_sha256", human.get("reviewed_png_sha256")),
                             ("qa.png_sha256", qa.get("png_sha256"))):
            if _sha(value, f"case[{index}].{field}") != png:
                raise ValueError(f"case[{index}].{field}: wrong frame attribution")

        if human_status == "unknown":
            human_unknown += 1
        elif human_status == "unobservable":
            human_unobservable += 1

        if human_status in ("unknown", "unobservable"):
            if qa_status == "passed":
                unsafe_pass_on_unlabeled += 1
            continue

        if qa_status == "unknown":
            qa_unknown_on_labeled += 1
            continue
        if qa_status == "unobservable":
            qa_unobservable_on_labeled += 1
            continue
        if human_status == "verified":
            counts["tp" if qa_status == "passed" else "fn"] += 1
        else:
            counts["fp" if qa_status == "passed" else "tn"] += 1

    decisive = sum(counts.values())
    labeled = decisive + qa_unknown_on_labeled + qa_unobservable_on_labeled
    return {
        "case_count": len(cases),
        "confusion": counts,
        "human_unknown": human_unknown,
        "human_unobservable": human_unobservable,
        "qa_unknown_on_labeled": qa_unknown_on_labeled,
        "qa_unobservable_on_labeled": qa_unobservable_on_labeled,
        "unsafe_pass_on_unlabeled": unsafe_pass_on_unlabeled,
        "decisive_coverage": _rate(decisive, labeled),
        "false_accept_rate": _rate(counts["fp"], counts["fp"] + counts["tn"]),
        "false_reject_rate": _rate(counts["fn"], counts["fn"] + counts["tp"]),
        "positive_precision": _rate(counts["tp"], counts["tp"] + counts["fp"]),
        "positive_recall": _rate(counts["tp"], counts["tp"] + counts["fn"]),
        "sample_count_meets_30": len(cases) >= 30,
        "g2_status": "NOT_INDEPENDENTLY_VERIFIED",
        "g3_status": "NO_GO",
        "release_eligible": False,
        "note": "Declared labels only; requires independent original-PNG review, "
                "representative 30+ human-labeled scenes, E2E latency and rollback.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline QA/human label metrics; not G2/G3 approval.")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        report = summarize_quality(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        # Schema errors contain only field paths; do not print private manifest.
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
