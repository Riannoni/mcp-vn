"""Durable, fail-closed *shadow* broker admission, not a live GPU broker.

This is an isolated source-only model: NO listener, Comfy /prompt POST,
GPU/network call, live-save access, service wiring, or live authorization.
All queue, boot, source, reviewer and OS-isolation observations are supplied
by the caller and are NOT authenticated by this module. Even a fully matched
record ALWAYS returns can_submit_gpu=False. Do not use it as a permission bit.

One SQLite WAL BEGIN IMMEDIATE transaction serializes each lease/consumption.
The single active owner is fenced, bound to an OS boot identifier and immutable
source/save/scene/version/reviewer/request hashes. A consumed idempotency key
persists across lease release. Expired, rebooted, changed or foreign-submission
leases are BLOCKED until independently reconciled; no auto-reclaim API exists.

REQUIRED live integration (NOT implemented or authorized):
* OS/container network ACL or namespace must make direct Comfy /prompt
  unreachable from EVERY non-broker client, including existing workers,
  scripts, local users and container peers. An attestation mapping here is
  ONLY a claimed test fixture, never actual isolation proof.
* A trusted broker must own the ONLY Comfy endpoint and derive boot ID,
  immutable game/save/scene snapshots, signed independent review, queue
  generation and complete history itself. GET /queue is not authoritative.
* Admission, queue generation compare, durable intent, POST and prompt-ID
  recovery need an enforceable single-writer protocol; crash between POST
  and receipt must block/reconcile, not retry blindly.
* Verify bypass attempts from every client, original PNG G2, 30+ human
  labeled G3 scenes, restart/rollback, full latency and save integrity.

Rollback: close broker admission, prevent all direct POST, reconcile
in-flight prompt IDs/history and source hashes, restore backed-up network
and service config only with owner approval. Never re-open an unfenced path.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import secrets
import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager

_ID = re.compile(r"[A-Za-z0-9_.:-]{4,128}\Z")
_FENCE = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST_FIELDS = frozenset({
    "source_sha", "save_sha", "scene_sha", "scene_version", "reviewer_id",
    "reviewer_sha", "request_sha", "idempotency_key",
})
_QUEUE_FIELDS = frozenset({
    "authoritative", "generation", "history_sha", "running", "pending",
    "foreign_submit",
})
_ISOLATION_FIELDS = frozenset({
    "kind", "enforced", "independent_attestation_sha",
    "blocked_bypass_tests_sha",
})
_LIVE_BLOCKERS = (
    "os_isolation_requires_external_proof",
    "authoritative_queue_generation_requires_live_broker",
    "atomic_comfy_submit_not_integrated",
    "prompt_id_crash_recovery_not_integrated",
    "independent_g2_g3_not_verified",
)


def _deny(reason: str) -> dict[str, object]:
    return {"status": "denied", "reason": reason, "can_submit_gpu": False}


def _id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _sha(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _clock(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _manifest(value: object, owner: str) -> bool:
    if not isinstance(value, Mapping) or set(value) != _MANIFEST_FIELDS:
        return False
    return (
        all(_sha(value[field]) for field in (
            "source_sha", "save_sha", "scene_sha", "reviewer_sha", "request_sha"
        ))
        and type(value["scene_version"]) is int
        and value["scene_version"] >= 0
        and _id(value["reviewer_id"])
        and value["reviewer_id"] != owner
        and _id(value["idempotency_key"])
    )


def _queue(value: object) -> bool:
    if not isinstance(value, Mapping) or set(value) != _QUEUE_FIELDS:
        return False
    return (
        value["authoritative"] is True
        and type(value["generation"]) is int and value["generation"] >= 0
        and _sha(value["history_sha"])
        and type(value["running"]) is int and value["running"] >= 0
        and type(value["pending"]) is int and value["pending"] >= 0
        and type(value["foreign_submit"]) is bool
    )


def _isolation(value: object) -> bool:
    # Shape validation ONLY. These strings do not prove an OS ACL exists.
    return (
        isinstance(value, Mapping)
        and set(value) == _ISOLATION_FIELDS
        and value["kind"] == "os_network_isolation"
        and value["enforced"] is True
        and _sha(value["independent_attestation_sha"])
        and _sha(value["blocked_bypass_tests_sha"])
    )


def _canonical(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"))


class ShadowBrokerAdmission:
    """SQLite-only serialized rehearsal; never grants GPU authority."""

    def __init__(self, db_path: str | pathlib.Path):
        self.path = str(db_path)
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS broker_lease ("
                "resource INTEGER PRIMARY KEY CHECK(resource=1),"
                "owner TEXT NOT NULL, fence TEXT NOT NULL, boot_id TEXT NOT NULL,"
                "state TEXT NOT NULL CHECK(state IN ('active','blocked')),"
                "manifest_json TEXT NOT NULL,"
                "queue_generation INTEGER NOT NULL, queue_history_sha TEXT NOT NULL,"
                "issued_at REAL NOT NULL, last_seen_at REAL NOT NULL,"
                "expires_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS broker_consumed ("
                "idempotency_key TEXT PRIMARY KEY, request_sha TEXT NOT NULL,"
                "owner TEXT NOT NULL, fence TEXT NOT NULL, boot_id TEXT NOT NULL,"
                "consumed_at REAL NOT NULL,"
                "state TEXT NOT NULL CHECK(state='shadow_consumed'))"
            )

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=5000")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _row(db: sqlite3.Connection):
        return db.execute(
            "SELECT owner,fence,boot_id,state,manifest_json,"
            "queue_generation,queue_history_sha,issued_at,last_seen_at,"
            "expires_at FROM broker_lease WHERE resource=1"
        ).fetchone()

    @staticmethod
    def _block(db: sqlite3.Connection) -> None:
        db.execute("UPDATE broker_lease SET state='blocked' WHERE resource=1")

    def journal_mode(self) -> str:
        with self._db() as db:
            return str(db.execute("PRAGMA journal_mode").fetchone()[0])

    def consumed_count(self) -> int:
        """Read-only audit count, never an actual Comfy submission count."""
        with self._db() as db:
            return int(db.execute("SELECT COUNT(*) FROM broker_consumed").fetchone()[0])

    def inspect(self, *, now: float) -> dict[str, object]:
        if not _clock(now):
            return _deny("invalid_clock")
        try:
            with self._db() as db:
                row = self._row(db)
            if row is None:
                return {"status": "empty", "can_submit_gpu": False}
            if row[3] == "blocked":
                return {"status": "blocked", "can_submit_gpu": False}
            if now >= row[9]:
                return {"status": "expired_unreconciled", "can_submit_gpu": False}
            return {"status": "active", "can_submit_gpu": False}
        except sqlite3.Error:
            return _deny("sqlite_error")

    def claim(self, *, owner: str, boot_id: str, now: float, ttl: int,
              manifest: Mapping[str, object],
              queue_baseline: Mapping[str, object]) -> dict[str, object]:
        if (not _id(owner) or not _id(boot_id) or not _clock(now)
                or type(ttl) is not int or not 5 <= ttl <= 600):
            return _deny("invalid_claim")
        if not _manifest(manifest, owner):
            return _deny("invalid_manifest")
        if not _queue(queue_baseline):
            return _deny("queue_not_authoritative")
        if queue_baseline["foreign_submit"]:
            return _deny("foreign_submission_detected")
        if queue_baseline["running"] or queue_baseline["pending"]:
            return _deny("queue_busy")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = self._row(db)
                if row is not None:
                    if row[3] == "blocked":
                        return _deny("manual_reconciliation_required")
                    if now >= row[9]:
                        self._block(db)
                        return _deny("expired_requires_manual_reconciliation")
                    return _deny("lease_busy")
                if db.execute(
                    "SELECT 1 FROM broker_consumed WHERE idempotency_key=?",
                    (manifest["idempotency_key"],),
                ).fetchone():
                    return _deny("idempotency_replayed")
                fence = secrets.token_hex(16)
                db.execute(
                    "INSERT INTO broker_lease (resource,owner,fence,boot_id,"
                    "state,manifest_json,queue_generation,queue_history_sha,"
                    "issued_at,last_seen_at,expires_at) "
                    "VALUES (1,?,?,?,'active',?,?,?,?,?,?)",
                    (owner, fence, boot_id, _canonical(manifest),
                     queue_baseline["generation"], queue_baseline["history_sha"],
                     now, now, now + ttl),
                )
            return {"status": "claimed", "fence": fence,
                    "can_submit_gpu": False}
        except sqlite3.Error:
            return _deny("sqlite_error")

    def _fenced(self, db, owner: str, fence: str, boot_id: str, now: float):
        row = self._row(db)
        if row is None or row[0] != owner or row[1] != fence:
            return None, "fence_mismatch"
        if row[3] == "blocked":
            return None, "manual_reconciliation_required"
        if row[2] != boot_id:
            self._block(db)
            return None, "boot_changed_requires_reconciliation"
        if now >= row[9]:
            self._block(db)
            return None, "expired_requires_manual_reconciliation"
        if now < row[7] or now < row[8]:
            self._block(db)
            return None, "clock_regression"
        return row, None

    def admit(self, *, owner: str, fence: str, boot_id: str, now: float,
              observed_manifest: Mapping[str, object],
              observed_queue: Mapping[str, object],
              isolation_evidence: Mapping[str, object]) -> dict[str, object]:
        """Consume one durable *shadow* intent; no POST or live permission."""
        if (not _id(owner) or not isinstance(fence, str)
                or _FENCE.fullmatch(fence) is None
                or not _id(boot_id) or not _clock(now)):
            return _deny("invalid_admission")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row, error = self._fenced(db, owner, fence, boot_id, now)
                if error:
                    return _deny(error)
                if (not _manifest(observed_manifest, owner)
                        or _canonical(observed_manifest) != row[4]):
                    self._block(db)
                    return _deny("immutable_manifest_changed")
                if not _queue(observed_queue):
                    self._block(db)
                    return _deny("queue_not_authoritative")
                if observed_queue["foreign_submit"]:
                    self._block(db)
                    return _deny("foreign_submission_detected")
                if observed_queue["running"] or observed_queue["pending"]:
                    self._block(db)
                    return _deny("queue_busy")
                if observed_queue["generation"] != row[5]:
                    self._block(db)
                    return _deny("queue_generation_changed")
                if observed_queue["history_sha"] != row[6]:
                    self._block(db)
                    return _deny("queue_history_changed")
                if not _isolation(isolation_evidence):
                    return _deny("external_os_isolation_unproven")
                if db.execute(
                    "SELECT 1 FROM broker_consumed WHERE idempotency_key=?",
                    (observed_manifest["idempotency_key"],),
                ).fetchone():
                    return _deny("idempotency_replayed")
                db.execute(
                    "INSERT INTO broker_consumed (idempotency_key,request_sha,"
                    "owner,fence,boot_id,consumed_at,state) "
                    "VALUES (?,?,?,?,?,?,'shadow_consumed')",
                    (observed_manifest["idempotency_key"],
                     observed_manifest["request_sha"], owner, fence,
                     boot_id, now),
                )
                db.execute(
                    "UPDATE broker_lease SET last_seen_at=? WHERE resource=1",
                    (now,),
                )
            return {"status": "shadow_recorded_only",
                    "reason": "source_only_no_live_authority",
                    "can_submit_gpu": False,
                    "live_blockers": list(_LIVE_BLOCKERS)}
        except (sqlite3.Error, TypeError, ValueError):
            return _deny("sqlite_error")

    def release(self, *, owner: str, fence: str, boot_id: str,
                now: float) -> dict[str, object]:
        if (not _id(owner) or not isinstance(fence, str)
                or _FENCE.fullmatch(fence) is None
                or not _id(boot_id) or not _clock(now)):
            return _deny("invalid_release")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                _, error = self._fenced(db, owner, fence, boot_id, now)
                if error:
                    return _deny(error)
                db.execute("DELETE FROM broker_lease WHERE resource=1")
            return {"status": "released", "can_submit_gpu": False}
        except sqlite3.Error:
            return _deny("sqlite_error")
