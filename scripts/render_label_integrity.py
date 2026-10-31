#!/usr/bin/env python3
"""Offline PRIVATE human-label integrity audit; never a visual G2/G3 gate.

Input: completed G-05 private review queue, enriched with case_id,
artifact.reference_path and review.attestation_path. Distinct capture and
human-review signing keys protect record integrity, NOT human authenticity.
Reference files must be SHA-named, byte-matched and read-only. No network,
GPU, image display, data writes, or publication. Synthetic fixtures are tests.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
from pathlib import Path, PurePosixPath
import stat
import struct
from typing import Any
from render_golden_evidence_index import (
    MAX_PNG_BYTES, MAX_RECEIPT_BYTES, _safe_file, _sha, _text, _time, _validate_png)
from render_human_review_queue import (
    MAX_CONTRACT_BYTES, MAX_MANIFEST_BYTES, SIGNED_FIELDS,
    _canonical, _validate_contract, _verify_receipt)

MAX_CASES = 500
REVIEW_FIELDS = (
    "state", "reviewer_role", "reviewer_id", "reviewed_at",
    "reviewed_png_sha256", "reviewed_contract_sha256", "method",
    "overall_verdict", "observation", "facts")
UNIQUE_FIELDS = (
    "case_id", "scene_id", "frame_id", "job_id", "prompt_id",
    "png_sha256", "contract_sha256")
LOCALIZED_FACTS = frozenset({"identity", "wardrobe", "props", "pose", "contact", "alpha"})
VERDICTS = frozenset({"verified", "violated", "unobservable"})
REFERENCE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def pinned_reference(root: Path, path: Any, expected: str) -> None:
    require(_sha(expected) and isinstance(path, str) and bool(path), "reference")
    name = PurePosixPath(path)
    require(name.suffix.lower() in REFERENCE_SUFFIXES
            and name.name == expected + name.suffix
            and not name.is_absolute() and ".." not in name.parts,
            "mutable_reference_path")
    raw = _safe_file(root, path, MAX_PNG_BYTES, name.suffix)
    require(hashlib.sha256(raw).hexdigest() == expected, "reference_bytes")
    mode = (root / path).stat().st_mode
    require(stat.S_ISREG(mode) and not (mode & 0o222), "writable_reference")


def check_facts(review: dict[str, Any], expected: list[dict[str, Any]],
                width: int, height: int) -> list[str]:
    rows = review.get("facts")
    require(isinstance(rows, list) and len(rows) == len(expected), "facts")
    by_id = {fact["fact_id"]: fact for fact in expected}
    seen: set[str] = set()
    verdicts: list[str] = []
    for fact in rows:
        require(isinstance(fact, dict), "fact_object")
        fid = fact.get("fact_id")
        require(isinstance(fid, str) and fid in by_id and fid not in seen, "fact_identity")
        seen.add(fid)
        target = by_id[fid]
        require(all(fact.get(k) == target[k] for k in (
            "fact_id", "attribute", "mandatory", "expectation")), "fact_contract")
        verdict = fact.get("verdict")
        require(verdict in VERDICTS, "fact_verdict")
        require(_text(fact.get("observation"))
                and fact.get("method") == "original_pixels", "fact_observation")
        roi = fact.get("roi")
        if target["attribute"] in LOCALIZED_FACTS:
            require(isinstance(roi, list) and len(roi) == 4
                    and all(type(n) is int for n in roi)
                    and roi[0] >= 0 and roi[1] >= 0
                    and roi[2] > 0 and roi[3] > 0
                    and roi[0] + roi[2] <= width
                    and roi[1] + roi[3] <= height, "fact_roi")
        elif roi is not None:
            require(isinstance(roi, list) and len(roi) == 4
                    and all(type(n) is int and n >= 0 for n in roi), "fact_roi")
        verdicts.append(verdict)
    return verdicts


def check_human_receipt(root: Path, review: dict[str, Any],
                        prov: dict[str, Any], key: bytes) -> None:
    raw = _safe_file(root, review.get("attestation_path"), MAX_RECEIPT_BYTES, ".json")
    receipt = json.loads(raw)
    require(isinstance(receipt, dict)
            and receipt.get("attestation_kind")
                == "independent_human_original_pixel_review", "human_attestation")
    require(receipt.get("reviewer_role") == "independent_human"
            and receipt.get("reviewer_id") == review["reviewer_id"]
            and receipt.get("reviewed_at") == review["reviewed_at"]
            and receipt.get("method") == "original_pixels", "human_attribution")
    require(all(receipt.get(k) == prov[k] for k in SIGNED_FIELDS),
            "human_capture_binding")
    digest = hashlib.sha256(_canonical({k: review[k] for k in REVIEW_FIELDS})).hexdigest()
    require(receipt.get("review_sha256") == digest, "human_label_binding")
    signature = receipt.get("signature")
    require(isinstance(signature, dict)
            and signature.get("scheme") == "hmac-sha256-v1"
            and signature.get("key_id") == "human-review-local-v1"
            and _sha(signature.get("mac")), "human_signature")
    unsigned = {k: v for k, v in receipt.items() if k != "signature"}
    expected = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
    require(hmac.compare_digest(signature["mac"], expected), "human_signature")


def validate_case(case: Any, root: Path, capture_key: bytes,
                  review_key: bytes) -> dict[str, str]:
    require(isinstance(case, dict), "case_object")
    require(_text(case.get("case_id"))
            and case.get("synthetic") is not True
            and "auto_label" not in case, "case_identity")
    prov = case.get("provenance")
    require(isinstance(prov, dict), "capture_provenance")
    require(all(_text(prov.get(k)) for k in (
        "scene_id", "frame_id", "job_id", "prompt_id"))
        and all(_sha(prov.get(k)) for k in (
            "png_sha256", "contract_sha256", "source_sha256", "reference_sha256"))
        and prov.get("kind") in ("background", "sprite", "cg")
        and case.get("scene_id") == prov["scene_id"]
        and case.get("kind") == prov["kind"], "capture_identity")
    artifact = case.get("artifact")
    require(isinstance(artifact, dict), "artifact")
    png = _safe_file(root, artifact.get("png_path"), MAX_PNG_BYTES, ".png")
    require(_validate_png(png)
            and hashlib.sha256(png).hexdigest() == prov["png_sha256"],
            "original_png")
    width, height = struct.unpack_from(">II", png, 16)
    contract_raw = _safe_file(root, artifact.get("contract_path"),
                              MAX_CONTRACT_BYTES, ".json")
    require(hashlib.sha256(contract_raw).hexdigest()
            == prov["contract_sha256"], "contract_bytes")
    facts = _validate_contract(json.loads(contract_raw), prov)
    capture_raw = _safe_file(root, artifact.get("receipt_path"),
                             MAX_RECEIPT_BYTES, ".json")
    capture = json.loads(capture_raw)
    _verify_receipt(capture, prov, capture_key)
    pinned_reference(root, artifact.get("reference_path"),
                     prov["reference_sha256"])

    review = case.get("review")
    require(isinstance(review, dict)
            and review.get("state") == "human_adjudicated"
            and review.get("reviewer_role") == "independent_human"
            and _text(review.get("reviewer_id"))
            and _time(review.get("reviewed_at")) is not None
            and review.get("method") == "original_pixels"
            and _text(review.get("observation"))
            and review.get("reviewed_png_sha256") == prov["png_sha256"]
            and review.get("reviewed_contract_sha256")
                == prov["contract_sha256"], "human_review")
    require(_time(review["reviewed_at"]) >= _time(capture["captured_at"]),
            "review_before_capture")
    verdicts = check_facts(review, facts, width, height)
    derived = ("violated" if "violated" in verdicts else
               "unobservable" if "unobservable" in verdicts else "verified")
    require(review.get("overall_verdict") == derived, "overall_verdict")
    check_human_receipt(root, review, prov, review_key)

    qa = case.get("qa")
    require(isinstance(qa, dict)
            and qa.get("status") in (
                "passed", "rejected", "unknown", "unobservable", "NOT_MEASURED")
            and qa.get("png_sha256") == prov["png_sha256"], "qa_attribution")
    return {
        "case_id": case["case_id"], "scene_id": prov["scene_id"],
        "frame_id": prov["frame_id"], "job_id": prov["job_id"],
        "prompt_id": prov["prompt_id"], "png_sha256": prov["png_sha256"],
        "contract_sha256": prov["contract_sha256"],
        "source_sha256": prov["source_sha256"],
        "reference_sha256": prov["reference_sha256"],
        "verdict": derived, "review_sha256": hashlib.sha256(
            _canonical({k: review[k] for k in REVIEW_FIELDS})).hexdigest(),
    }


def audit_labels(document: Any, private_root: Path, capture_key: bytes,
                 review_key: bytes, *, min_cases: int = 30) -> dict[str, Any]:
    """Validate declarations only; cannot prove actual original-pixel viewing."""
    if type(min_cases) is not int or min_cases < 1:
        raise ValueError("min_cases")
    root = Path(private_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("private_root")
    if (not isinstance(capture_key, bytes) or len(capture_key) < 32
            or not isinstance(review_key, bytes) or len(review_key) < 32
            or hmac.compare_digest(capture_key, review_key)):
        raise ValueError("separate_signing_keys")
    rows = document.get("cases") if isinstance(document, dict) else None
    if (not isinstance(document, dict) or document.get("schema_version") != 1
            or not isinstance(rows, list) or len(rows) > MAX_CASES):
        raise ValueError("manifest_schema")
    issues: list[str] = []
    valid: dict[int, dict[str, str]] = {}
    for i, row in enumerate(rows):
        try:
            valid[i] = validate_case(row, root, capture_key, review_key)
        except (OSError, ValueError, TypeError, KeyError, OverflowError,
                UnicodeError, struct.error):
            issues.append(f"case[{i}]: invalid_provenance_or_label")

    invalid: set[int] = set()
    for field in UNIQUE_FIELDS:
        groups: dict[str, list[int]] = {}
        for i, row in valid.items():
            groups.setdefault(row[field], []).append(i)
        for indexes in groups.values():
            if len(indexes) < 2:
                continue
            invalid.update(indexes)
            if field == "png_sha256":
                signatures = {(
                    valid[i]["scene_id"], valid[i]["source_sha256"],
                    valid[i]["contract_sha256"], valid[i]["review_sha256"],
                ) for i in indexes}
                code = "png_conflict" if len(signatures) > 1 else "duplicate_png"
            else:
                code = "duplicate_" + field
            for i in indexes:
                issues.append(f"case[{i}]: {code}")

    retained = [v for i, v in valid.items() if i not in invalid]
    if len(retained) < min_cases:
        issues.append("root: insufficient_independent_labeled_cases")
    return {
        "manifest_valid": not issues,
        "input_cases": len(rows),
        "valid_labeled_cases": len(retained),
        "unique_png_sha": len({v["png_sha256"] for v in retained}),
        "verified_declarations": sum(v["verdict"] == "verified" for v in retained),
        "violated_cases": sum(v["verdict"] == "violated" for v in retained),
        "unobservable_cases": sum(v["verdict"] == "unobservable" for v in retained),
        "issues": sorted(set(issues)),
        "original_pixels_viewed_by_tool": False,
        "independent_human_review_proven_by_tool": False,
        "release_eligible": False, "g2": "UNVERIFIED", "g3": "NO_GO",
        "note": "Signed declarations are not proof of a human or pixel review; "
                "independent verification, 30+ real scenes, QA comparison, "
                "E2E and latency gates remain required.",
    }


def private_key(root: Path, path: str) -> bytes:
    raw = _safe_file(root, path, 4096, ".key")
    mode = (root / path).stat().st_mode
    require(not (mode & (stat.S_IRWXG | stat.S_IRWXO)), "key_permissions")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="PRIVATE label integrity, NOT G2/G3")
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--capture-key", required=True)
    parser.add_argument("--review-key", required=True)
    parser.add_argument("--min-cases", type=int, default=30)
    args = parser.parse_args()
    try:
        root = args.private_root.resolve(strict=True)
        manifest = json.loads(_safe_file(root, args.manifest, MAX_MANIFEST_BYTES, ".json"))
        report = audit_labels(manifest, root, private_key(root, args.capture_key),
                              private_key(root, args.review_key),
                              min_cases=args.min_cases)
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"manifest_valid": False,
                          "error": "private manifest or keys invalid"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["manifest_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
