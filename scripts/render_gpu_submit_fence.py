"""In-memory-only TOCTOU submit-fence rehearsal for render-v1.

This module has NO live ComfyUI client, network transport, GPU submit,
filesystem queue or production authorization. All queue mutations are local
synthetic state. Even a successful mock record returns can_submit_gpu=False.

The lock and revision protect only THIS Python object, not other processes,
ComfyUI clients, restarts or the real queue. A real integration must atomically
fence an authenticated queue submit, exact job/prompt ID and independently
reviewed disposable source/scene within a single trusted coordination domain.
No amount of two sequential GET /queue calls supplies that guarantee.
"""
from __future__ import annotations

import math
import re
import threading
from collections.abc import Mapping

from scripts.render_gpu_governor import ShadowGpuGovernor

_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_FENCE = re.compile(r"[0-9a-f]{32}\Z")


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def _valid_clock(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _deny(reason: str) -> dict[str, object]:
    return {"status": "denied", "reason": reason, "can_submit_gpu": False}


class ShadowQueue:
    """One-process mock queue with monotonic revision; not a ComfyUI queue."""

    def __init__(self):
        self._lock = threading.RLock()
        self._revision = 0
        self._running: list[str] = []
        self._pending: list[str] = []

    def _state_locked(self, now: float) -> dict[str, object]:
        return {
            "known": True,
            "running": list(self._running),
            "pending": list(self._pending),
            "observed_at": now,
            "revision": self._revision,
        }

    def observe(self, *, now: float) -> dict[str, object]:
        if not _valid_clock(now):
            raise ValueError("invalid mock clock")
        with self._lock:
            return self._state_locked(now)

    def inject_foreign_job(self, job_id: str) -> None:
        """Simulate another writer. Never sends an external request."""
        if not _valid_id(job_id):
            raise ValueError("invalid synthetic job")
        with self._lock:
            self._pending.append(job_id)
            self._revision += 1

    def clear_for_test(self) -> None:
        """Simulate queue ABA: even empty-again is a new generation."""
        with self._lock:
            self._pending.clear()
            self._running.clear()
            self._revision += 1


def shadow_submit(
    governor: ShadowGpuGovernor,
    queue: ShadowQueue,
    *,
    owner: str,
    fence: str,
    expected_revision: int,
    job_id: str,
    snapshot: object,
    now: float,
) -> dict[str, object]:
    """Recheck a mock lease/scene and append under ONE mock queue lock.

    Caller-observed revision is compared inside the same critical section as
    the mock append. A foreign mock enqueue between observation and this lock
    fails closed. This is a deterministic NEGATIVE test, never live permission.
    """
    if (
        not isinstance(governor, ShadowGpuGovernor)
        or not isinstance(queue, ShadowQueue)
        or not _valid_id(owner)
        or not isinstance(fence, str)
        or not _FENCE.fullmatch(fence)
        or type(expected_revision) is not int
        or expected_revision < 0
        or not _valid_id(job_id)
        or not _valid_clock(now)
        or not isinstance(snapshot, Mapping)
    ):
        return _deny("invalid_shadow_request")

    scene = snapshot.get("scene")
    if not isinstance(scene, Mapping) or scene.get("expected_job_id") != job_id:
        return _deny("job_binding_mismatch")

    with queue._lock:
        if queue._revision != expected_revision:
            return _deny("queue_revision_changed")
        if queue._running or queue._pending:
            return _deny("queue_busy")

        # Never trust the caller's lease or queue: the governor re-reads its
        # own mock lease and this method replaces the mock queue observation.
        fresh = dict(snapshot)
        fresh["queue"] = queue._state_locked(now)
        verdict = governor.recheck(
            owner=owner, fence=fence, snapshot=fresh, now=now
        )
        if verdict.get("status") != "shadow_ready":
            return _deny(str(verdict.get("reason", "preflight_denied")))

        # Atomic with the mock queue revision check ONLY, not with ComfyUI.
        queue._pending.append(job_id)
        queue._revision += 1
        return {
            "status": "shadow_recorded_only",
            "reason": "in_memory_queue_only",
            "can_submit_gpu": False,
            "revision": queue._revision,
        }
