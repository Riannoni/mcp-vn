#!/usr/bin/env python3
"""Atomic *advisory* cross-wake reservation for native ChatGPT Scheduled Tasks.

This NEVER calls OpenAI or a model. Each caller MUST first verify a genuinely
new exact source/PNG SHA, check official Automations.peek that the target is
enabled and not in_progress, and only then reserve + issue ONE official run_now.
The platform decides actual availability and rate limits. No Codex quota read.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import time

TARGETS = {
    "broker": "6ae5d49054d48191ba1a0c2f2ba55816",
    "broker_reviewer": "6ae5dcb9fb3c8191935b5ef13fab8f5b",
    "chief": "6ae57ba332a48191923e7f51ccfe7dd5",
    "integration": "6ae5dcbce2c481919e6cd302c223c279",
    "renderer": "6ae57b3727688191ab20279ff8fba0af",
    "golden": "6ae57b3d794c8191aff21eac865b780b",
    "golden_evidence": "6ae5dcacb7908191b72d98510a3db5b6",
    "pose": "6ae5dcafbf7c8191aaf823beed911ff2",
    "identity": "6ae5dcb38de4819193cccf1a9c5954d2",
    "provenance": "6ae5dd11d4748191adb005926b42c083",
    "reliability": "6ae57b40434c8191857969a577627d2f",
    "e2e": "6ae5dcb6f8c88191b2cc46a83f64d8da",
}
KINDS = {"source_pr_ready", "review_accepted", "visual_candidate_ready",
         "blocker_cleared", "contract_verified", "integration_ready"}
SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
MIN_SECONDS_BETWEEN_TARGET_WAKES = 240
MAX_TARGET_WAKES_PER_HOUR = 3
MAX_GLOBAL_WAKES_PER_HOUR = 18


def check(root, target, kind, evidence_sha, requestor, reserve=False, now=None):
    if target not in TARGETS or requestor not in TARGETS:
        raise ValueError("unknown cloud role")
    if requestor == target:
        return {"eligible": False, "reason": "self_wake_not_needed", "target": target}
    if kind not in KINDS or not isinstance(evidence_sha, str) or not SHA.fullmatch(evidence_sha):
        raise ValueError("unverified event type or source hash")
    root = Path(root).expanduser().resolve()
    state = root / "state"
    if not state.is_dir():
        raise FileNotFoundError("native team state missing")
    path = state / "scheduled-wake-history.sqlite3"
    instant = time.time() if now is None else now
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        if path.is_file():
            os.chmod(path, 0o600)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("CREATE TABLE IF NOT EXISTS wake_signal ("
                   "target TEXT NOT NULL,event_kind TEXT NOT NULL,"
                   "evidence_sha TEXT NOT NULL,requestor TEXT NOT NULL,"
                   "requested_at REAL NOT NULL,"
                   "PRIMARY KEY(target,event_kind,evidence_sha))")
        if reserve:
            db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM wake_signal WHERE target=? AND event_kind=? AND evidence_sha=?",
                      (target, kind, evidence_sha)).fetchone():
            result = {"eligible":False, "reason":"already_requested_for_exact_evidence"}
        else:
            latest = db.execute("SELECT MAX(requested_at) FROM wake_signal WHERE target=?", (target,)).fetchone()[0]
            lane_count = db.execute(
                "SELECT COUNT(*) FROM wake_signal WHERE target=? AND requested_at>?",
                (target, instant-3600)).fetchone()[0]
            global_count = db.execute(
                "SELECT COUNT(*) FROM wake_signal WHERE requested_at>?",
                (instant-3600,)).fetchone()[0]
            if lane_count >= MAX_TARGET_WAKES_PER_HOUR:
                result = {"eligible":False, "reason":"per_target_hourly_budget"}
            elif global_count >= MAX_GLOBAL_WAKES_PER_HOUR:
                result = {"eligible":False, "reason":"global_hourly_budget"}
            elif latest is not None and instant-latest < MIN_SECONDS_BETWEEN_TARGET_WAKES:
                result = {"eligible":False,"reason":"target_wake_cooldown",
                          "retry_after_seconds":round(MIN_SECONDS_BETWEEN_TARGET_WAKES-(instant-latest))}
            else:
                result = {"eligible":True,"reason":"verified_event_requires_native_run_now"}
        result.update({"target":target,"automation_id":TARGETS[target],
                       "event_kind":kind,"evidence_sha":evidence_sha})
        if reserve and result["eligible"]:
            db.execute("INSERT INTO wake_signal VALUES (?,?,?,?,?)",
                       (target,kind,evidence_sha,requestor,instant))
            result["reserved"] = True
            result["note"] = "Use official Automations.run_now. Reservation is not a launch."
        if reserve:
            db.execute("COMMIT")
        return result
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--target", choices=sorted(TARGETS), required=True)
    p.add_argument("--event-kind", choices=sorted(KINDS), required=True)
    p.add_argument("--evidence-sha", required=True)
    p.add_argument("--requestor", choices=sorted(TARGETS), required=True)
    p.add_argument("--reserve", action="store_true")
    args = p.parse_args()
    print(json.dumps(check(args.root,args.target,args.event_kind,
                           args.evidence_sha,args.requestor,args.reserve),
                     sort_keys=True))


if __name__ == "__main__":
    main()
