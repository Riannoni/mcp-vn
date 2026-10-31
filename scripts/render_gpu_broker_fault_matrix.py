"""Deterministic SOURCE-ONLY fault matrix for the shadow Comfy broker.

No Comfy URL, HTTP client, GPU, live save, or authorization is present.
A synthetic queue and source are re-read under ONE in-process lock before
ShadowBrokerAdmission.admit. This closes the demonstrated stale-caller
observation hole *only inside this mock*. It does NOT attest the real queue,
isolate direct /prompt callers, or make admission+POST atomic. Every verdict
retains can_submit_gpu=False, including a recorded shadow intent.

A process restart is conservatively modeled as a new coordinator epoch:
old fenced work becomes blocked pending independent reconciliation. This is
a test model, not evidence of live OS isolation or crash recovery.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import threading
from collections.abc import Mapping

from scripts.render_gpu_broker_admission import ShadowBrokerAdmission


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def synthetic_manifest() -> dict[str, object]:
    return {
        "source_sha": _digest("source"),
        "save_sha": _digest("save"),
        "scene_sha": _digest("scene"),
        "scene_version": 7,
        "reviewer_id": "independent-mock-reviewer",
        "reviewer_sha": _digest("review"),
        "request_sha": _digest("request"),
        "idempotency_key": "synthetic-one-shot-001",
    }


def synthetic_isolation() -> dict[str, object]:
    # This is intentionally NOT an attestation of any actual OS ACL.
    return {
        "kind": "os_network_isolation",
        "enforced": True,
        "independent_attestation_sha": _digest("mock-attestation"),
        "blocked_bypass_tests_sha": _digest("mock-bypass"),
    }


class SyntheticQueue:
    """Monotonic synthetic history, including empty-again (ABA) transitions."""

    def __init__(self):
        self.lock = threading.RLock()
        self.generation = 1
        self.history_sha = _digest("queue-initial")
        self.running = 0
        self.pending = 0
        self.foreign_submit = False

    def _event(self, name: str) -> None:
        self.generation += 1
        self.history_sha = _digest(self.history_sha + ":" + name)

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "authoritative": True,  # mock-only assertion, never live proof
                "generation": self.generation,
                "history_sha": self.history_sha,
                "running": self.running,
                "pending": self.pending,
                "foreign_submit": self.foreign_submit,
            }

    def transient_aba(self) -> None:
        with self.lock:
            self.pending += 1
            self._event("pending")
            self.pending -= 1
            self._event("drained")

    def foreign_then_drain(self) -> None:
        with self.lock:
            self.pending += 1
            self.foreign_submit = True
            self._event("foreign")
            self.pending -= 1
            self._event("foreign-drained")

    def make_busy(self) -> None:
        with self.lock:
            self.pending += 1
            self._event("busy")


class MockFaultMatrix:
    """One in-process mock coordination domain backed by a durable shadow DB."""

    def __init__(self, db_path: str | pathlib.Path, *, epoch: str,
                 queue: SyntheticQueue | None = None,
                 manifest: Mapping[str, object] | None = None):
        self.db_path = pathlib.Path(db_path)
        self.epoch = epoch
        self.queue = queue if queue is not None else SyntheticQueue()
        self.manifest = dict(manifest) if manifest is not None else synthetic_manifest()
        self.broker = ShadowBrokerAdmission(self.db_path)

    def claim(self, *, owner: str = "S-matrix-owner", now: float = 1000,
              ttl: int = 120) -> dict[str, object]:
        with self.queue.lock:
            return self.broker.claim(
                owner=owner, boot_id=self.epoch, now=now, ttl=ttl,
                manifest=dict(self.manifest),
                queue_baseline=self.queue.snapshot(),
            )

    def change_manifest(self, field: str, value: object) -> None:
        with self.queue.lock:
            self.manifest[field] = value

    def attempt(self, *, owner: str, fence: str, now: float = 1001,
                isolation: Mapping[str, object] | None = None) -> dict[str, object]:
        # No caller-supplied queue or manifest is accepted. Fresh mock state
        # is observed in the same critical section as the shadow DB commit.
        with self.queue.lock:
            return self.broker.admit(
                owner=owner, fence=fence, boot_id=self.epoch, now=now,
                observed_manifest=dict(self.manifest),
                observed_queue=self.queue.snapshot(),
                isolation_evidence=(
                    synthetic_isolation() if isolation is None else isolation
                ),
            )

    def restart(self, *, new_epoch: str) -> "MockFaultMatrix":
        # Reopen the durable DB; never recover an old owner/fence automatically.
        return MockFaultMatrix(self.db_path, epoch=new_epoch,
                               queue=self.queue, manifest=self.manifest)


def run_fault_matrix() -> dict[str, object]:
    """Exercise independent failure scenarios, with no external side effects."""
    scenarios = ("transient_aba", "foreign_submit", "stale_save",
                 "invalid_fence", "expired_lease", "duplicate_intent",
                 "crash_before_intent", "crash_after_intent")
    expected = {
        "transient_aba": "queue_generation_changed",
        "foreign_submit": "foreign_submission_detected",
        "stale_save": "immutable_manifest_changed",
        "invalid_fence": "fence_mismatch",
        "expired_lease": "expired_requires_manual_reconciliation",
        "duplicate_intent": "idempotency_replayed",
        "crash_before_intent": "boot_changed_requires_reconciliation",
        "crash_after_intent": "boot_changed_requires_reconciliation",
    }
    results: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="shadow-fault-matrix-") as tmp:
        for name in scenarios:
            mock = MockFaultMatrix(pathlib.Path(tmp) / (name + ".sqlite"),
                                   epoch="mock-epoch-0001")
            lease = mock.claim()
            if lease.get("status") != "claimed":
                raise AssertionError("synthetic claim failed")
            fence = str(lease["fence"])
            if name == "transient_aba":
                mock.queue.transient_aba()
            elif name == "foreign_submit":
                mock.queue.foreign_then_drain()
            elif name == "stale_save":
                mock.change_manifest("save_sha", _digest("changed-save"))
            elif name == "invalid_fence":
                fence = "0" * 32 if fence != "0" * 32 else "1" * 32
            elif name == "expired_lease":
                pass
            elif name == "duplicate_intent":
                first = mock.attempt(owner="S-matrix-owner", fence=fence)
                if first.get("status") != "shadow_recorded_only":
                    raise AssertionError("synthetic first intent not recorded")
            elif name == "crash_before_intent":
                mock = mock.restart(new_epoch="mock-epoch-0002")
            elif name == "crash_after_intent":
                first = mock.attempt(owner="S-matrix-owner", fence=fence)
                if first.get("status") != "shadow_recorded_only":
                    raise AssertionError("synthetic first intent not recorded")
                mock = mock.restart(new_epoch="mock-epoch-0002")
            result = mock.attempt(owner="S-matrix-owner", fence=fence,
                                  now=1120 if name == "expired_lease" else 1001)
            if result.get("can_submit_gpu") is not False:
                raise AssertionError("mock must never authorize GPU")
            if result.get("reason") != expected[name]:
                raise AssertionError(f"{name}: {result.get('reason')}")
            results[name] = str(result["reason"])
    return {
        "source_only": True, "can_submit_gpu": False,
        "cases": results, "passed": len(results), "total": len(scenarios),
        "live_atomicity": "UNVERIFIED", "g2": "UNVERIFIED", "g3": "NO_GO",
    }


if __name__ == "__main__":
    print(json.dumps(run_fault_matrix(), sort_keys=True))
