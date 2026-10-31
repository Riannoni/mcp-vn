"""SQLite WAL *shadow-only* GPU lease and pre-submit rehearsal.

No GPU, ComfyUI, network, live-save or production code path exists here.
SQLite BEGIN IMMEDIATE serializes competing mock claimants, and a persisted
fence prevents stale owners from heartbeat/release/recheck. Expiration is
fail-closed: an expired lease becomes BLOCKED and must be reconciled manually
by an operator after independently checking the *real* queue and job history.
There is intentionally no automatic expiry reclaim or reconciliation API.

This does NOT atomically reserve a live Comfy queue. Offline snapshots may
race a real submit; even "shadow_ready" ALWAYS means can_submit_gpu=False.
Actual production needs an independently reviewed queue-submit transaction,
fenced live job IDs, original PNG G2, rollback and >=30-scene G3 validation.
"""
from __future__ import annotations

import math
import pathlib
import re
import secrets
import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager

from scripts.render_gpu_preflight import evaluate_preflight

_OWNER = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_FENCE = re.compile(r"[0-9a-f]{32}\Z")
_MIN_TTL = 5
_MAX_TTL = 600


def _clock(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _ttl(value: object) -> bool:
    return type(value) is int and _MIN_TTL <= value <= _MAX_TTL


def _owner(value: object) -> bool:
    return isinstance(value, str) and bool(_OWNER.fullmatch(value))


def _fence(value: object) -> bool:
    return isinstance(value, str) and bool(_FENCE.fullmatch(value))


def _deny(reason: str) -> dict[str, object]:
    return {"status": "denied", "reason": reason, "can_submit_gpu": False}


class ShadowGpuGovernor:
    """Local mock-only lease; never provides authority to submit to GPU."""

    def __init__(self, db_path: str | pathlib.Path):
        self.path = str(db_path)
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS shadow_gpu_lease ("
                "resource INTEGER PRIMARY KEY CHECK(resource=1),"
                "owner TEXT NOT NULL, fence TEXT NOT NULL,"
                "state TEXT NOT NULL CHECK(state IN ('active','blocked')),"
                "issued_at REAL NOT NULL, last_seen_at REAL NOT NULL,"
                "expires_at REAL NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _row(db: sqlite3.Connection):
        return db.execute(
            "SELECT owner,fence,state,issued_at,last_seen_at,expires_at "
            "FROM shadow_gpu_lease WHERE resource=1"
        ).fetchone()

    @staticmethod
    def _blocked_if_expired(db: sqlite3.Connection, row, now: float) -> bool:
        if row[2] == "active" and now >= row[5]:
            db.execute(
                "UPDATE shadow_gpu_lease SET state='blocked' WHERE resource=1"
            )
            return True
        return False

    @contextmanager
    def _db(self):
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def journal_mode(self) -> str:
        with self._db() as db:
            return str(db.execute("PRAGMA journal_mode").fetchone()[0])

    def inspect(self, *, now: float) -> dict[str, object]:
        if not _clock(now):
            return _deny("invalid_clock")
        try:
            with self._db() as db:
                row = self._row(db)
            if row is None:
                return {"status": "empty", "can_submit_gpu": False}
            if row[2] == "blocked":
                return {"status": "blocked", "can_submit_gpu": False}
            if now >= row[5]:
                return {"status": "expired_unreconciled", "can_submit_gpu": False}
            return {"status": "active", "can_submit_gpu": False,
                    "expires_at": row[5]}
        except sqlite3.Error:
            return _deny("sqlite_error")

    def claim(self, *, owner: str, now: float,
              ttl: int = 120) -> dict[str, object]:
        if not _owner(owner) or not _clock(now) or not _ttl(ttl):
            return _deny("invalid_claim")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = self._row(db)
                if row is not None:
                    if self._blocked_if_expired(db, row, now):
                        return _deny("expired_requires_manual_reconciliation")
                    if row[2] == "blocked":
                        return _deny("manual_reconciliation_required")
                    return _deny("lease_busy")
                fence = secrets.token_hex(16)
                expires_at = now + ttl
                db.execute(
                    "INSERT INTO shadow_gpu_lease "
                    "(resource,owner,fence,state,issued_at,last_seen_at,expires_at) "
                    "VALUES (1,?,?,'active',?,?,?)",
                    (owner, fence, now, now, expires_at)
                )
            return {"status": "claimed", "owner": owner, "fence": fence,
                    "expires_at": expires_at, "can_submit_gpu": False}
        except sqlite3.Error:
            return _deny("sqlite_error")

    def _fenced(self, db, owner: str, fence: str, now: float):
        row = self._row(db)
        if row is None or row[0] != owner or row[1] != fence:
            return None, "fence_mismatch"
        if row[2] == "blocked":
            return None, "manual_reconciliation_required"
        if self._blocked_if_expired(db, row, now):
            return None, "expired_requires_manual_reconciliation"
        if now < row[4]:
            return None, "clock_regression"
        return row, None

    def heartbeat(self, *, owner: str, fence: str, now: float,
                  ttl: int = 120) -> dict[str, object]:
        if not _owner(owner) or not _fence(fence) or not _clock(now) or not _ttl(ttl):
            return _deny("invalid_heartbeat")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                _, error = self._fenced(db, owner, fence, now)
                if error:
                    return _deny(error)
                expires_at = now + ttl
                db.execute(
                    "UPDATE shadow_gpu_lease SET expires_at=?,last_seen_at=? "
                    "WHERE resource=1", (expires_at, now)
                )
            return {"status": "renewed", "expires_at": expires_at,
                    "can_submit_gpu": False}
        except sqlite3.Error:
            return _deny("sqlite_error")

    def release(self, *, owner: str, fence: str,
                now: float) -> dict[str, object]:
        """Release a *mock* lease only while valid, never reclaim expired."""
        if not _owner(owner) or not _fence(fence) or not _clock(now):
            return _deny("invalid_release")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                _, error = self._fenced(db, owner, fence, now)
                if error:
                    return _deny(error)
                db.execute("DELETE FROM shadow_gpu_lease WHERE resource=1")
            return {"status": "released", "can_submit_gpu": False}
        except sqlite3.Error:
            return _deny("sqlite_error")

    def recheck(self, *, owner: str, fence: str,
                snapshot: object, now: float) -> dict[str, object]:
        """Re-read mock lease and evaluate *fresh supplied* synthetic evidence.

        The caller's lease field is discarded. Queue, scene, source and sandbox
        observations are externally supplied; no actual file or queue probe is
        performed, so there is still a live TOCTOU gap after this method.
        """
        if not _owner(owner) or not _fence(fence) or not _clock(now):
            return _deny("invalid_recheck")
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row, error = self._fenced(db, owner, fence, now)
                if error:
                    return _deny(error)
                if not isinstance(snapshot, Mapping):
                    return _deny("invalid_snapshot")
                evidence = dict(snapshot)
                evidence["lease"] = {
                    "owner": row[0], "fence": row[1],
                    "exclusive": True, "active_owners": [row[0]],
                    "expires_at": row[5],
                }
                try:
                    verdict = evaluate_preflight(evidence, now=now)
                except (TypeError, ValueError, KeyError, AttributeError):
                    return _deny("invalid_snapshot")
                if verdict.get("status") != "shadow_ready":
                    return _deny(str(verdict.get("reason", "preflight_denied")))
                # Intentionally no submit path and no live queue reservation.
                return {"status": "shadow_ready",
                        "reason": "mock_recheck_consistent",
                        "can_submit_gpu": False}
        except sqlite3.Error:
            return _deny("sqlite_error")
