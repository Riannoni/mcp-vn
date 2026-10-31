#!/usr/bin/env python3
"""Offline schema/provenance audit of a private, human-labeled render golden set.

This is intentionally NOT a pixel reviewer or G2/G3 release gate. Even a
synthetic manifest with 30 internally consistent "verified" declarations
cannot prove that the referenced original PNGs were actually inspected.
No image, save, story, prompt, GPU, or network access is performed here.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
VERDICTS = frozenset(("verified", "violated", "unobservable"))
KINDS = frozenset(("background", "sprite", "cg"))


def _string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def audit_manifest(document: Any, *, min_cases: int = 30) -> dict[str, Any]:
    """Check declared identities and evidence links, never certify real pixels.

    The input is a JSON object with schema_version=1 and a cases array.
    Each case carries its own scene/source/reference hashes, immutable
    job/frame provenance, per-actor and per-required-object annotations,
    and a human label tied to the exact output PNG digest. The reviewer
    assertion is untrusted: it is checked for consistency, not truth.
    """
    if type(min_cases) is not int or min_cases < 1:
        raise ValueError("min_cases must be a positive integer")

    issues: list[str] = []
    if not isinstance(document, dict):
        return _report(["root: expected object"], 0, 0, 0)
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        issues.append("root: unsupported schema_version")
    cases = document.get("cases")
    if not isinstance(cases, list):
        return _report(issues + ["root: cases must be an array"], 0, 0, 0)
    if len(cases) < min_cases:
        issues.append("root: fewer than required independent cases")

    scene_ids: set[str] = set()
    frame_ids: set[str] = set()
    png_digests: set[str] = set()
    contract_digests: set[str] = set()
    job_ids: set[str] = set()
    prompt_ids: set[str] = set()
    declared_complete = 0
    blocked = 0

    for index, case in enumerate(cases):
        prefix = f"case[{index}]"
        start_errors = len(issues)

        def fail(field: str) -> None:
            issues.append(f"{prefix}: invalid {field}")

        if not isinstance(case, dict):
            fail("case object")
            blocked += 1
            continue

        scene = case.get("scene_id")
        kind = case.get("kind")
        source = case.get("source_sha256")
        reference = case.get("reference_sha256")
        if not _string(scene):
            fail("scene_id")
        elif scene in scene_ids:
            fail("duplicate scene_id")
        else:
            scene_ids.add(scene)
        if not isinstance(kind, str) or kind not in KINDS:
            fail("kind")
        if not _sha(source):
            fail("source_sha256")
        if not _sha(reference):
            fail("reference_sha256")

        provenance = case.get("provenance")
        if not isinstance(provenance, dict):
            fail("provenance")
            provenance = {}
        frame = provenance.get("frame_id")
        png = provenance.get("png_sha256")
        if not _string(frame):
            fail("provenance.frame_id")
        elif frame in frame_ids:
            fail("duplicate provenance.frame_id")
        else:
            frame_ids.add(frame)
        if not _sha(png):
            fail("provenance.png_sha256")
        elif png in png_digests:
            fail("duplicate provenance.png_sha256")
        else:
            png_digests.add(png)
        contract = provenance.get("contract_sha256")
        if not _sha(contract):
            fail("provenance.contract_sha256")
        elif contract in contract_digests:
            fail("duplicate provenance.contract_sha256")
        else:
            contract_digests.add(contract)
        for field, seen in (("job_id", job_ids), ("prompt_id", prompt_ids)):
            value = provenance.get(field)
            if not _string(value):
                fail(f"provenance.{field}")
            elif value in seen:
                fail(f"duplicate provenance.{field}")
            else:
                seen.add(value)
        for field, expected in (("scene_id", scene), ("source_sha256", source)):
            if not _string(expected) or provenance.get(field) != expected:
                fail(f"provenance.{field} attribution")

        mandatory_verified = True
        for collection, id_key in (("named_actors", "actor_id"), ("required_objects", "object_id")):
            rows = case.get(collection)
            if not isinstance(rows, list):
                fail(collection)
                mandatory_verified = False
                continue
            if collection == "named_actors" and kind in ("sprite", "cg") and not rows:
                fail("named_actors missing for principal frame")
                mandatory_verified = False
            seen: set[str] = set()
            for item_index, item in enumerate(rows):
                item_path = f"{collection}[{item_index}]"
                if not isinstance(item, dict):
                    fail(item_path)
                    mandatory_verified = False
                    continue
                item_id = item.get(id_key)
                if not _string(item_id):
                    fail(f"{item_path}.{id_key}")
                elif item_id in seen:
                    fail(f"{item_path}.duplicate {id_key}")
                else:
                    seen.add(item_id)
                status = item.get("status")
                if not isinstance(status, str) or status not in VERDICTS:
                    fail(f"{item_path}.status")
                if status != "verified":
                    mandatory_verified = False
                evidence = item.get("evidence")
                if not isinstance(evidence, dict):
                    fail(f"{item_path}.evidence")
                    continue
                for field, expected in (
                    ("scene_id", scene),
                    ("frame_id", frame),
                    ("png_sha256", png),
                    ("source_sha256", source),
                ):
                    if not _string(expected) or evidence.get(field) != expected:
                        fail(f"{item_path}.evidence.{field} attribution")
                for field in ("method", "observation"):
                    if not _string(evidence.get(field)):
                        fail(f"{item_path}.evidence.{field}")

        human = case.get("human_label")
        if not isinstance(human, dict):
            fail("human_label")
            human = {}
        status = human.get("status")
        if not isinstance(status, str) or status not in VERDICTS:
            fail("human_label.status")
        if status != "verified":
            mandatory_verified = False
        if not _string(human.get("reviewer_id")):
            fail("human_label.reviewer_id")
        if human.get("method") != "original_pixels":
            fail("human_label.method (original_pixels required)")
        if not _string(human.get("observation")):
            fail("human_label.observation")
        if not _sha(png) or human.get("reviewed_png_sha256") != png:
            fail("human_label.reviewed_png_sha256 attribution")

        if len(issues) == start_errors and mandatory_verified:
            declared_complete += 1
        else:
            blocked += 1

    return _report(issues, len(cases), declared_complete, blocked)


def _report(issues: list[str], count: int, declared: int, blocked: int) -> dict[str, Any]:
    return {
        "manifest_valid": not issues,
        "case_count": count,
        "declared_complete_cases": declared,
        "blocked_cases": blocked,
        "issues": issues,
        "g2_status": "NOT_INDEPENDENTLY_VERIFIED",
        "g3_status": "NO_GO",
        "release_eligible": False,
        "note": "Schema and attribution only; independent original-PNG review, measured E2E and rollback remain required.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline golden-set manifest consistency audit; never certifies G2/G3.")
    parser.add_argument("manifest", type=Path, help="Private JSON manifest on local disk")
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(json.dumps(_report(["root: unreadable or invalid JSON"], 0, 0, 0)))
        return 2
    report = audit_manifest(data)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["manifest_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
