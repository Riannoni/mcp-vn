#!/usr/bin/env python3
"""Read-only private original-PNG evidence index; NEVER certifies G2/G3.

Cross-checks G-01 provenance, G-02 QA-vs-human labels and G-03 measured
latencies. It hashes real local PNG bytes and their private capture receipts,
but metadata claiming "human" cannot independently prove who viewed pixels.
Synthetic test PNGs, self-labels, duplicate provenance, missing receipts and
unobservable mandatory evidence cannot be silently counted as G2 PASS.

All private paths, image bytes, prompts and IDs stay on the PC. Reports
contain only counts, generic indexed errors and descriptive measurements.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
from typing import Any
import zlib

from render_golden_set_audit import audit_manifest
from render_quality_metrics import summarize_quality
from render_latency_metrics import summarize_latency

SHA = re.compile(r"^[0-9a-f]{64}$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_RECEIPT_BYTES = 256 * 1024
MAX_CASES = 500
IDENTITY = ("scene_id", "frame_id", "job_id", "prompt_id",
            "png_sha256", "contract_sha256")
PROVENANCE = ("frame_id", "job_id", "prompt_id", "png_sha256",
              "source_sha256", "contract_sha256", "scene_id")


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _time(value: Any) -> datetime | None:
    if not _text(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _safe_file(root: Path, relative: Any, max_bytes: int, suffix: str) -> bytes:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("invalid relative path")
    name = PurePosixPath(relative)
    if name.is_absolute() or ".." in name.parts or "." in name.parts or name.suffix.lower() != suffix:
        raise ValueError("unsafe relative path")
    current = root
    for part in name.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink is not permitted")
    path = current.resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("path outside private root or not regular file")
    size = path.stat().st_size
    if size <= 0 or size > max_bytes:
        raise ValueError("file size out of bounds")
    return path.read_bytes()


def _validate_png(raw: bytes) -> bool:
    """Validate PNG chunk framing and CRC, not semantic visual correctness."""
    if not raw.startswith(PNG_SIGNATURE):
        return False
    pos = len(PNG_SIGNATURE)
    first = True
    idat = False
    ended = False
    while pos + 12 <= len(raw):
        length = struct.unpack_from(">I", raw, pos)[0]
        pos += 4
        kind = raw[pos:pos + 4]
        pos += 4
        if length > len(raw) - pos - 4:
            return False
        payload = raw[pos:pos + length]
        pos += length
        checksum = struct.unpack_from(">I", raw, pos)[0]
        pos += 4
        if zlib.crc32(kind + payload) & 0xffffffff != checksum:
            return False
        if first:
            if kind != b"IHDR" or length != 13:
                return False
            width, height = struct.unpack_from(">II", payload)
            if not 0 < width <= 32768 or not 0 < height <= 32768:
                return False
            first = False
        elif kind == b"IHDR":
            return False
        if kind == b"IDAT":
            idat = True
        if kind == b"IEND":
            ended = length == 0 and pos == len(raw)
            break
    return idat and ended


def _empty_quality() -> dict[str, Any]:
    return {
        "status": "NOT_MEASURED", "confusion": {"tp": 0, "fn": 0, "fp": 0, "tn": 0},
        "false_accept_rate": None, "false_reject_rate": None,
        "human_unknown": 0, "human_unobservable": 0,
        "qa_unknown_on_labeled": 0, "qa_unobservable_on_labeled": 0,
        "unsafe_pass_on_unlabeled": 0,
    }


def audit_evidence(document: Any, private_root: Path, *, min_cases: int = 30) -> dict[str, Any]:
    if type(min_cases) is not int or min_cases < 1:
        raise ValueError("min_cases must be positive")
    issues: list[str] = []
    rows = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(rows, list):
        issues.append("root: invalid schema_version or cases")
        rows = []
    if len(rows) > MAX_CASES:
        issues.append("root: too many cases")
        rows = []
    root = Path(private_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("private root is not a directory")

    seen = {field: set() for field in IDENTITY}
    file_verified = 0
    real_receipts = 0
    human_attested = 0
    missing_qa = 0
    qualified: dict[str, dict[str, Any]] = {}
    quality_rows: list[dict[str, Any]] = []
    for index, case in enumerate(rows):
        prefix = f"case[{index}]"
        if not isinstance(case, dict):
            issues.append(f"{prefix}: invalid case object")
            continue
        prov = case.get("provenance")
        if not isinstance(prov, dict):
            issues.append(f"{prefix}: invalid provenance")
            continue
        ids = dict(prov)
        ids["scene_id"] = case.get("scene_id")
        if any(not _text(ids.get(k)) for k in ("scene_id", "frame_id", "job_id", "prompt_id")) or any(
            not _sha(ids.get(k)) for k in ("png_sha256", "contract_sha256")
        ):
            issues.append(f"{prefix}: missing or invalid provenance identities")
            continue
        if any(ids[k] in seen[k] for k in IDENTITY):
            issues.append(f"{prefix}: duplicate independent provenance")
            continue
        for k in IDENTITY:
            seen[k].add(ids[k])

        # G-01 validates actor/object evidence, source/reference attribution,
        # exact reviewed PNG hash and mandatory observability declarations.
        g01 = audit_manifest({"schema_version": 1, "cases": [case]}, min_cases=1)
        if not g01["manifest_valid"]:
            issues.append(f"{prefix}: G-01 schema or attribution rejected")
            continue

        artifact = case.get("artifact")
        if not isinstance(artifact, dict) or not _sha(artifact.get("receipt_sha256")):
            issues.append(f"{prefix}: missing private capture artifact")
            continue
        try:
            raw = _safe_file(root, artifact.get("png_path"), MAX_PNG_BYTES, ".png")
            if not _validate_png(raw) or hashlib.sha256(raw).hexdigest() != ids["png_sha256"]:
                raise ValueError("PNG bytes or digest invalid")
        except (OSError, ValueError):
            issues.append(f"{prefix}: original PNG bytes unavailable or invalid")
            continue
        file_verified += 1
        try:
            receipt_raw = _safe_file(root, artifact.get("receipt_path"), MAX_RECEIPT_BYTES, ".json")
            if hashlib.sha256(receipt_raw).hexdigest() != artifact["receipt_sha256"]:
                raise ValueError("receipt digest mismatch")
            receipt = json.loads(receipt_raw)
            if not isinstance(receipt, dict) or receipt.get("capture_kind") != "real_comfy_job":
                raise ValueError("synthetic or unknown capture")
            captured = _time(receipt.get("captured_at"))
            if captured is None or receipt.get("scene_id") != case["scene_id"]:
                raise ValueError("missing capture attribution")
            if any(receipt.get(field) != case.get(field) for field in ("source_sha256", "reference_sha256")):
                raise ValueError("source/reference mismatch")
            rp = receipt.get("provenance")
            if not isinstance(rp, dict) or any(rp.get(field) != prov.get(field) for field in PROVENANCE):
                raise ValueError("job/prompt/PNG/contract mismatch")
        except (OSError, ValueError, TypeError):
            issues.append(f"{prefix}: private capture receipt missing or mismatched")
            continue
        real_receipts += 1

        human = case.get("human_label", {})
        reviewed = _time(human.get("reviewed_at")) if isinstance(human, dict) else None
        if (not isinstance(human, dict)
                or human.get("reviewer_type") != "human"
                or human.get("review_source") != "independent_human"
                or human.get("method") != "original_pixels"
                or human.get("reviewed_png_sha256") != ids["png_sha256"]
                or reviewed is None or reviewed < captured
                or not _text(human.get("reviewer_id"))
                or not _text(human.get("observation"))):
            issues.append(f"{prefix}: no independently human-attested original-pixel label")
            continue
        human_attested += 1
        qualified[case["scene_id"]] = case

        qa = case.get("qa")
        if not isinstance(qa, dict) or qa.get("status") not in (
            "passed", "rejected", "unknown", "unobservable"
        ) or qa.get("png_sha256") != ids["png_sha256"]:
            missing_qa += 1
            issues.append(f"{prefix}: QA status or PNG attribution missing")
            continue
        quality_rows.append(case)

    quality = _empty_quality()
    if quality_rows:
        try:
            quality = summarize_quality({"schema_version": 1, "cases": quality_rows})
            quality["status"] = "DECLARED_METADATA_ONLY"
        except ValueError:
            issues.append("root: G-02 QA comparison rejected")
    latency_input = document.get("latency_observations", []) if isinstance(document, dict) else []
    if not isinstance(latency_input, list):
        issues.append("root: latency_observations must be an array")
        latency_input = []
    matching_latency = []
    seen_latency: set[str] = set()
    for index, observation in enumerate(latency_input):
        if not isinstance(observation, dict) or not isinstance(observation.get("provenance"), dict):
            issues.append(f"latency[{index}]: missing provenance")
            continue
        candidate = qualified.get(observation.get("scene_id"))
        if candidate is None or observation["scene_id"] in seen_latency:
            issues.append(f"latency[{index}]: no unique real human-attested scene")
            continue
        expected = candidate["provenance"]
        if any(observation["provenance"].get(field) != expected.get(field)
               for field in PROVENANCE if field != "scene_id"):
            issues.append(f"latency[{index}]: different source/job/contract/PNG")
            continue
        seen_latency.add(observation["scene_id"])
        matching_latency.append(observation)
    latency = summarize_latency({"schema_version": 1, "observations": matching_latency})
    if latency["invalid_observations"]:
        issues.append("root: G-03 rejected invalid stage timestamps or attribution")
    coverage = {
        "required": min_cases,
        "meets_30": human_attested >= min_cases,
        "attested_fraction_of_required": round(min(human_attested / min_cases, 1.0), 4),
        "human_attestation_is_independently_authenticated": False,
    }
    return {
        "manifest_cases": len(rows),
        "verified_png_files": file_verified,
        "real_capture_receipt_cases": real_receipts,
        "human_attested_real_cases": human_attested,
        "missing_qa": missing_qa,
        "coverage": coverage,
        "quality": quality,
        "latency": latency,
        "issues": issues,
        "original_pixels_viewed_by_this_tool": False,
        "g2_status": "UNVERIFIED",
        "g3_status": "NO_GO",
        "release_eligible": False,
        "note": "Local PNG bytes and private receipts were hashed, not visually reviewed. "
                "Human identity/labels are self-declared metadata, never cryptographic proof. "
                "Independent original-pixel adjudication, >=30 diverse scenes, "
                "E2E/restart/rollback and measured latency remain external release gates.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only private PNG + receipt + human label index")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.private_root.resolve(strict=True)
        manifest = args.manifest.resolve(strict=True)
        if not manifest.is_relative_to(root):
            raise ValueError("manifest must be inside private root")
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        report = audit_evidence(doc, root)
    except (OSError, ValueError):
        print(json.dumps({"valid": False, "error": "private manifest unreadable or invalid"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["issues"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
