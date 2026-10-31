#!/usr/bin/env python3
"""Offline, provenance-fenced render-stage latency metrics.

Input is a PRIVATE JSON manifest; no GPU, image, save, network or live service
access. The manifest must contain independently attributed timestamp pairs:

  {"schema_version": 1, "observations": [
    {"scene_id": "...", "outcome": "published|rejected",
     "provenance": {"frame_id": "...", "job_id": "...",
                    "prompt_id": "...", "png_sha256": "<64 hex>",
                    "source_sha256": "<64 hex>",
                    "contract_sha256": "<64 hex>"},
     "stages": {
       "queue": {"started_at": "<ISO-8601 with offset>",
                 "ended_at": "<ISO-8601 with offset>",
                 "frame_id": "...", "job_id": "...",
                 "prompt_id": "...", "png_sha256": "<same digest>"},
       "...": "...",
       "full_turn": {"started_at": "...", "ended_at": "...",
                     "frame_id": "...", "job_id": "...",
                     "prompt_id": "...", "png_sha256": "..."}
     }}]}

Allowed stages: queue, preflight, comfy, postprocess, qa, repair, publish,
full_turn. Each stage is an observed start/end pair, not a guessed duration.
Absent stage means NOT_MEASURED, never 0ms. Repair may be absent if no repair.
Full-turn measurements require all non-optional stages for the outcome:
published requires publish; rejected ends after QA or optional repair.
Missing mandatory stage means full_turn NOT_MEASURED even if a full_turn
timestamp pair was supplied. All supplied stages must be nonoverlapping and
inside full_turn if present.

Percentiles use nearest-rank on actual millisecond durations, not fabricated
observations or interpolation. Mixed outcomes are reported separately.
Duplicate scene/contract/job/prompt/frame/PNG provenance is excluded from
independent samples. This validates timestamps and metadata consistency only;
it cannot prove that the job ran, the image was viewed, or G2/G3 passed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
STAGES = ("queue", "preflight", "comfy", "postprocess", "qa",
          "repair", "publish", "full_turn")
PIPELINE = STAGES[:-1]
PROVENANCE_FIELDS = ("frame_id", "job_id", "prompt_id", "png_sha256")
OUTCOMES = ("published", "rejected")
REQUIRED = ("queue", "preflight", "comfy", "postprocess", "qa")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: missing/invalid identifier")
    return value


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"{field}: invalid SHA-256")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: missing/invalid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: malformed timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field}: timezone required")
    return parsed.astimezone(timezone.utc)


def _millis(start: datetime, end: datetime, field: str) -> float:
    elapsed = (end - start).total_seconds() * 1000
    if not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError(f"{field}: reversed/zero timestamp interval")
    return round(elapsed, 3)


def _observation(raw: Any) -> tuple[str, dict[str, str], dict[str, float], bool]:
    if not isinstance(raw, dict):
        raise ValueError("expected observation object")
    scene = _text(raw.get("scene_id"), "scene_id")
    outcome = raw.get("outcome")
    if not isinstance(outcome, str) or outcome not in OUTCOMES:
        raise ValueError("outcome: must be published or rejected")
    provenance = raw.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("provenance: missing object")
    ids = {field: _text(provenance.get(field), f"provenance.{field}")
           for field in PROVENANCE_FIELDS if field != "png_sha256"}
    ids["png_sha256"] = _digest(provenance.get("png_sha256"), "provenance.png_sha256")
    ids["contract_sha256"] = _digest(provenance.get("contract_sha256"),
                                     "provenance.contract_sha256")
    ids["source_sha256"] = _digest(provenance.get("source_sha256"),
                                   "provenance.source_sha256")
    ids["scene_id"] = scene

    stages = raw.get("stages")
    if not isinstance(stages, dict) or not stages:
        raise ValueError("stages: nonempty object required")
    for stage in stages:
        if stage not in STAGES:
            raise ValueError("stages: unknown stage")
    if outcome == "rejected" and "publish" in stages:
        raise ValueError("publish: rejected frame cannot be published")

    pairs: dict[str, tuple[datetime, datetime]] = {}
    durations: dict[str, float] = {}
    for stage, record in stages.items():
        if not isinstance(record, dict):
            raise ValueError(f"{stage}: expected stage object")
        for field in PROVENANCE_FIELDS:
            value = record.get(field)
            if field == "png_sha256":
                _digest(value, f"{stage}.{field}")
            else:
                _text(value, f"{stage}.{field}")
            if value != ids[field]:
                raise ValueError(f"{stage}.{field}: mixed-frame attribution")
        start = _timestamp(record.get("started_at"), f"{stage}.started_at")
        end = _timestamp(record.get("ended_at"), f"{stage}.ended_at")
        durations[stage] = _millis(start, end, stage)
        pairs[stage] = (start, end)

    last_end: datetime | None = None
    for stage in PIPELINE:
        if stage not in pairs:
            continue
        start, end = pairs[stage]
        if last_end is not None and start < last_end:
            raise ValueError(f"{stage}: stage ordering/overlap")
        last_end = end

    if "full_turn" in pairs:
        turn_start, turn_end = pairs["full_turn"]
        for stage in PIPELINE:
            if stage not in pairs:
                continue
            start, end = pairs[stage]
            if start < turn_start or end > turn_end:
                raise ValueError("full_turn: does not enclose all stages")

    complete = (all(stage in pairs for stage in REQUIRED)
                and (outcome != "published" or "publish" in pairs)
                and "full_turn" in pairs)
    if not complete:
        durations.pop("full_turn", None)
    return outcome, ids, durations, complete


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def _metrics(samples: dict[str, list[float]]) -> dict[str, dict[str, Any]]:
    result = {}
    for stage in STAGES:
        values = samples[stage]
        result[stage] = {
            "status": "MEASURED" if values else "NOT_MEASURED",
            "n": len(values),
            "p50_ms": _percentile(values, .5),
            "p90_ms": _percentile(values, .9),
        }
    return result


def summarize_latency(document: Any) -> dict[str, Any]:
    """Validate independent provenance and compute only measured durations.

    Invalid observations contribute *zero* samples to any stage. Incomplete
    but internally valid observations contribute only their measured stages.
    All errors are field-only descriptions; private IDs/paths are not echoed.
    """
    if not isinstance(document, dict):
        raise ValueError("root: expected object")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise ValueError("root: unsupported schema_version")
    rows = document.get("observations")
    if not isinstance(rows, list):
        raise ValueError("root: observations must be an array")

    samples = {stage: [] for stage in STAGES}
    by_outcome = {outcome: {stage: [] for stage in STAGES} for outcome in OUTCOMES}
    seen: dict[str, set[str]] = {
        field: set() for field in ("scene_id", "frame_id", "job_id",
                                  "prompt_id", "png_sha256", "contract_sha256")
    }
    issues: list[str] = []
    valid = incomplete_turns = 0

    for index, raw in enumerate(rows):
        try:
            outcome, ids, durations, complete = _observation(raw)
            for field, observed in seen.items():
                if ids[field] in observed:
                    raise ValueError(f"provenance.{field}: duplicate independent observation")
        except ValueError as exc:
            issues.append(f"observation[{index}]: {exc}")
            continue
        for field, observed in seen.items():
            observed.add(ids[field])
        valid += 1
        if not complete:
            incomplete_turns += 1
        for stage, duration in durations.items():
            samples[stage].append(duration)
            by_outcome[outcome][stage].append(duration)

    return {
        "observations": len(rows),
        "valid_observations": valid,
        "invalid_observations": len(issues),
        "incomplete_full_turn_observations": incomplete_turns,
        "issues": issues,
        "metrics": _metrics(samples),
        "by_outcome": {outcome: _metrics(group) for outcome, group in by_outcome.items()},
        "percentile_method": "nearest_rank",
        "g2_status": "UNVERIFIED",
        "g3_status": "NO_GO",
        "release_eligible": False,
        "note": "Offline timestamp/provenance consistency only; no real PNG inspected, "
                "no human-label or representative 30+ E2E evidence established.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline private render-stage latency metrics")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        report = summarize_latency(json.loads(args.manifest.read_text(encoding="utf-8")))
    except OSError:
        # Do not echo the private manifest path from OSError.
        print(json.dumps({"valid": False, "error": "manifest unreadable"}))
        return 2
    except ValueError as exc:
        # JSON parse and schema errors contain only field paths/positions.
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["invalid_observations"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
