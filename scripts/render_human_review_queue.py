#!/usr/bin/env python3
"""Local-only original-PNG human review queue, never an image reviewer.

Only signed real Comfy capture receipts, byte-verified PNGs and byte-verified
typed Scene Contracts enter the PRIVATE pending queue. No labels are produced.
An HMAC protects locally attested receipt integrity; it does NOT independently
prove capture authenticity or that any human inspected the image. No network,
GPU, model, deployment, or canonical game data is accessed.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
from typing import Any

from render_golden_evidence_index import (
    MAX_PNG_BYTES, MAX_RECEIPT_BYTES, _safe_file, _sha, _text,
    _time, _validate_png,
)

MAX_CASES = 500
MAX_CONTRACT_BYTES = 256 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
ATTRIBUTES = frozenset({
    "environment", "cast", "identity", "wardrobe", "props",
    "landmarks", "pose", "contact", "composition", "alpha",
})
IDENTITIES = ("scene_id", "frame_id", "job_id", "prompt_id",
              "png_sha256", "contract_sha256")
SIGNED_FIELDS = (
    "scene_id", "frame_id", "job_id", "prompt_id", "kind",
    "png_sha256", "contract_sha256", "source_sha256",
    "reference_sha256",
)


def _canonical(document: Any) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _validate_contract(contract: Any, candidate: dict[str, Any]) -> list[dict[str, Any]]:
    if (not isinstance(contract, dict)
            or contract.get("schema_version") != 1
            or contract.get("scene_id") != candidate["scene_id"]
            or contract.get("kind") != candidate["kind"]):
        raise ValueError("contract identity")
    facts = contract.get("required_facts")
    if not isinstance(facts, list) or not 1 <= len(facts) <= 100:
        raise ValueError("missing typed mandatory facts")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fact in facts:
        if (not isinstance(fact, dict)
                or not _text(fact.get("fact_id"))
                or fact["fact_id"] in seen
                or fact.get("attribute") not in ATTRIBUTES
                or fact.get("mandatory") is not True
                or not _text(fact.get("expectation"))
                or len(fact["expectation"]) > 1000):
            raise ValueError("invalid mandatory fact")
        seen.add(fact["fact_id"])
        result.append({
            "fact_id": fact["fact_id"], "attribute": fact["attribute"],
            "mandatory": True, "expectation": fact["expectation"],
            "verdict": None, "observation": None, "roi": None,
        })
    return result


def _verify_receipt(receipt: Any, candidate: dict[str, Any], key: bytes) -> None:
    if not isinstance(receipt, dict) or receipt.get("capture_kind") != "real_comfy_job":
        raise ValueError("not a real Comfy capture receipt")
    if _time(receipt.get("captured_at")) is None:
        raise ValueError("missing capture time")
    if any(receipt.get(field) != candidate.get(field) for field in SIGNED_FIELDS):
        raise ValueError("capture attribution mismatch")
    signature = receipt.get("signature")
    if (not isinstance(signature, dict)
            or signature.get("scheme") != "hmac-sha256-v1"
            or signature.get("key_id") != "capture-local-v1"
            or not _sha(signature.get("mac"))):
        raise ValueError("unsigned or unknown signer")
    unsigned = {k: v for k, v in receipt.items() if k != "signature"}
    expected = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature["mac"], expected):
        raise ValueError("capture receipt signature mismatch")


def _verify_candidate(candidate: Any, root: Path, key: bytes) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("candidate not object")
    if any(field in candidate for field in (
            "human_label", "reviewer", "reviewed_at", "review",
            "auto_label", "synthetic_label")):
        raise ValueError("pre-filled or automatic human label forbidden")
    if (candidate.get("synthetic") is True
            or candidate.get("origin", "real_comfy_job") != "real_comfy_job"):
        raise ValueError("synthetic source forbidden")
    if (any(not _text(candidate.get(k)) for k in (
            "scene_id", "frame_id", "job_id", "prompt_id"))
            or any(not _sha(candidate.get(k)) for k in (
                "png_sha256", "contract_sha256", "source_sha256",
                "reference_sha256"))
            or candidate.get("kind") not in ("background", "sprite", "cg")):
        raise ValueError("incomplete capture provenance")

    png = _safe_file(root, candidate.get("png_path"), MAX_PNG_BYTES, ".png")
    if not _validate_png(png) or hashlib.sha256(png).hexdigest() != candidate["png_sha256"]:
        raise ValueError("PNG bytes or SHA mismatch")
    contract_raw = _safe_file(root, candidate.get("contract_path"), MAX_CONTRACT_BYTES, ".json")
    if hashlib.sha256(contract_raw).hexdigest() != candidate["contract_sha256"]:
        raise ValueError("contract SHA mismatch")
    contract = json.loads(contract_raw)
    facts = _validate_contract(contract, candidate)
    receipt_raw = _safe_file(root, candidate.get("receipt_path"), MAX_RECEIPT_BYTES, ".json")
    _verify_receipt(json.loads(receipt_raw), candidate, key)

    qa = candidate.get("qa")
    if qa is None:
        qa_result = {"status": "NOT_MEASURED", "png_sha256": candidate["png_sha256"]}
    elif (isinstance(qa, dict)
          and qa.get("status") in ("passed", "rejected", "unknown", "unobservable")
          and qa.get("png_sha256") == candidate["png_sha256"]):
        qa_result = {"status": qa["status"], "png_sha256": candidate["png_sha256"]}
    else:
        raise ValueError("QA provenance mismatch")

    return {
        "scene_id": candidate["scene_id"], "kind": candidate["kind"],
        "provenance": {k: candidate[k] for k in SIGNED_FIELDS},
        "artifact": {
            "png_path": candidate["png_path"],
            "contract_path": candidate["contract_path"],
            "receipt_path": candidate["receipt_path"],
        },
        "qa": qa_result,
        "review": {
            "state": "awaiting_independent_human",
            "reviewer_id": None, "reviewed_at": None,
            "reviewed_png_sha256": None, "method": None,
            "overall_verdict": None, "observation": None,
            "facts": facts,
        },
    }


def build_queue(document: Any, private_root: Path, receipt_key: bytes | None,
                *, inventory: Any = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build private *pending* queue; summary never includes paths or scene IDs.

    A G-04 aggregate inventory alone has no job/contract/receipt provenance
    and therefore cannot yield reviewable frames.
    """
    root = Path(private_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("private root not directory")
    if document is None:
        candidates: list[Any] = []
    elif (isinstance(document, dict) and document.get("schema_version") == 1
          and isinstance(document.get("candidates"), list)):
        candidates = document["candidates"]
    else:
        raise ValueError("candidate manifest schema invalid")
    if len(candidates) > MAX_CASES:
        raise ValueError("too many candidates")
    if candidates and (not isinstance(receipt_key, bytes) or len(receipt_key) < 32):
        raise ValueError("missing private capture receipt verification key")

    counts = {"input_candidates": len(candidates), "queued_for_human_review": 0,
              "rejected_duplicate": 0, "rejected_untrusted": 0,
              "human_labels": 0, "inventory_candidate_png_files": None,
              "inventory_unique_png_sha": None}
    if inventory is not None:
        if not isinstance(inventory, dict):
            raise ValueError("inventory schema invalid")
        for field, dest in (("candidate_png_files", "inventory_candidate_png_files"),
                            ("unique_png_sha", "inventory_unique_png_sha")):
            value = inventory.get(field)
            if type(value) is not int or value < 0:
                raise ValueError("invalid aggregate inventory count")
            counts[dest] = value

    seen = {field: set() for field in IDENTITIES}
    accepted: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, dict) and any(
                isinstance(candidate.get(k), str) and candidate[k] in seen[k]
                for k in IDENTITIES):
            counts["rejected_duplicate"] += 1
            continue
        try:
            row = _verify_candidate(candidate, root, receipt_key or b"")
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            counts["rejected_untrusted"] += 1
            continue
        accepted.append(row)
        for field in IDENTITIES:
            seen[field].add(candidate[field])

    counts["queued_for_human_review"] = len(accepted)
    summary = {
        **counts,
        "original_pixels_viewed_by_tool": False,
        "release_eligible": False, "g2": "UNVERIFIED", "g3": "NO_GO",
        "note": "Only private, signed, byte-matched candidates may enter a pending "
                "human queue. Signatures attest local receipt integrity, not independent "
                "human review or true Comfy provenance. 30+ real independent "
                "human-adjudicated scenes, QA comparison, latency and E2E remain required.",
    }
    queue = {
        "schema_version": 1, "queue_kind": "private_original_pixel_human_review",
        "state": "PENDING_HUMAN_REVIEW", "original_pixels_viewed_by_tool": False,
        "g2": "UNVERIFIED", "g3": "NO_GO", "cases": accepted,
    }
    return queue, summary


def write_private_queue(output: Path, private_root: Path, queue: dict[str, Any]) -> None:
    root = Path(private_root).resolve(strict=True)
    output = Path(output)
    if output.suffix.lower() != ".json":
        raise ValueError("output must be JSON")
    parent = output.parent.resolve(strict=True)
    if not parent.is_relative_to(root):
        raise ValueError("output must stay inside private root")
    if output.is_symlink():
        raise ValueError("symlink output forbidden")
    raw = json.dumps(queue, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def _read_private_json(root: Path, relative: Path, max_bytes: int) -> Any:
    if relative.is_absolute():
        try:
            relative = relative.relative_to(root)
        except ValueError as exc:
            raise ValueError("input outside private root") from exc
    raw = _safe_file(root, relative.as_posix(), max_bytes, ".json")
    return json.loads(raw)


def _relative_input(requested: Path, supplied_root: Path, resolved_root: Path) -> Path:
    if not requested.is_absolute():
        return requested
    # The PC's /home/Xavok is an alias of /var/home/Xavok. Compare literal
    # roots before _safe_file rejects symlinks *within* the private directory.
    for base in (supplied_root.absolute(), resolved_root):
        try:
            return requested.relative_to(base)
        except ValueError:
            pass
    raise ValueError("input outside private root")


def main() -> int:
    parser = argparse.ArgumentParser(description="PRIVATE pending original-pixel human queue")
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--receipt-key", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        root = args.private_root.resolve(strict=True)
        if args.manifest is None and args.inventory is None:
            raise ValueError("manifest or inventory required")
        document = (_read_private_json(root, _relative_input(
                        args.manifest, args.private_root, root), MAX_MANIFEST_BYTES)
                    if args.manifest is not None else None)
        inventory = (_read_private_json(root, _relative_input(
                         args.inventory, args.private_root, root), MAX_RECEIPT_BYTES)
                     if args.inventory is not None else None)
        key = None
        if args.receipt_key is not None:
            key_path = _relative_input(args.receipt_key, args.private_root, root)
            key = _safe_file(root, key_path.as_posix(), 4096, ".key")
            mode = (root / key_path).stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise ValueError("private signing key permissions too open")
        queue, summary = build_queue(document, root, key, inventory=inventory)
        if args.output is not None:
            write_private_queue(args.output, root, queue)
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"valid": False, "error": "private inputs, provenance, key or output invalid"}))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
