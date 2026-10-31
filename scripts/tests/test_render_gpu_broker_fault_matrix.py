"""Adversarial mock-only fault matrix; independent from live Comfy."""
import pathlib
import socket
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from scripts.render_gpu_broker_fault_matrix import (
    MockFaultMatrix, SyntheticQueue, _digest, run_fault_matrix,
    synthetic_isolation,
)


class FaultMatrixTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = pathlib.Path(tmp.name) / "matrix.sqlite"
        self.mock = MockFaultMatrix(self.db, epoch="mock-epoch-0001")
        self.owner = "S-matrix-owner"
        self.lease = self.mock.claim(owner=self.owner)
        self.assertEqual(self.lease["status"], "claimed")
        self.fence = self.lease["fence"]

    def attempt(self, mock=None, *, fence=None, now=1001, isolation=None):
        target = mock or self.mock
        return target.attempt(
            owner=self.owner, fence=self.fence if fence is None else fence,
            now=now, isolation=isolation,
        )

    def test_red_baseline_transient_aba_reobserved_not_stale(self):
        before = self.mock.queue.snapshot()
        self.mock.queue.transient_aba()
        after = self.mock.queue.snapshot()
        self.assertEqual(before["pending"], after["pending"])
        self.assertNotEqual(before["generation"], after["generation"])
        self.assertNotEqual(before["history_sha"], after["history_sha"])
        result = self.attempt()
        self.assertEqual(result["reason"], "queue_generation_changed")
        self.assertEqual(self.mock.broker.consumed_count(), 0)
        self.assertEqual(self.mock.broker.inspect(now=1002)["status"], "blocked")

    def test_foreign_submit_then_drain_fails_even_if_empty(self):
        self.mock.queue.foreign_then_drain()
        self.assertEqual(self.mock.queue.snapshot()["pending"], 0)
        self.assertEqual(self.attempt()["reason"], "foreign_submission_detected")
        self.assertEqual(self.mock.broker.consumed_count(), 0)

    def test_stale_save_snapshot_denied(self):
        self.mock.change_manifest("save_sha", _digest("new-save"))
        self.assertEqual(self.attempt()["reason"], "immutable_manifest_changed")
        self.assertEqual(self.mock.broker.inspect(now=1002)["status"], "blocked")

    def test_source_scene_review_and_request_drift_denied(self):
        for field, value in (
            ("source_sha", _digest("changed-source")),
            ("scene_sha", _digest("changed-scene")),
            ("scene_version", 8),
            ("reviewer_sha", _digest("changed-review")),
            ("request_sha", _digest("changed-request")),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                mock = MockFaultMatrix(pathlib.Path(tmp) / "db.sqlite",
                                       epoch="mock-epoch-0001")
                lease = mock.claim(owner=self.owner)
                mock.change_manifest(field, value)
                r = mock.attempt(owner=self.owner, fence=lease["fence"])
                self.assertEqual(r["reason"], "immutable_manifest_changed")
                self.assertEqual(mock.broker.consumed_count(), 0)

    def test_wrong_fence_denied_without_consuming(self):
        wrong = "0" * 32 if self.fence != "0" * 32 else "1" * 32
        self.assertEqual(self.attempt(fence=wrong)["reason"], "fence_mismatch")
        self.assertEqual(self.mock.broker.consumed_count(), 0)

    def test_lease_expiry_blocks_until_manual_reconciliation(self):
        self.assertEqual(self.attempt(now=1120)["reason"],
                         "expired_requires_manual_reconciliation")
        self.assertEqual(self.mock.broker.inspect(now=1121)["status"], "blocked")

    def test_duplicate_intent_fails_closed(self):
        first = self.attempt()
        self.assertEqual(first["status"], "shadow_recorded_only")
        self.assertIs(first["can_submit_gpu"], False)
        self.assertEqual(self.attempt()["reason"], "idempotency_replayed")
        self.assertEqual(self.mock.broker.consumed_count(), 1)

    def test_crash_after_recorded_intent_does_not_replay(self):
        self.assertEqual(self.attempt()["status"], "shadow_recorded_only")
        restarted = self.mock.restart(new_epoch="mock-epoch-0002")
        self.assertEqual(self.attempt(restarted)["reason"],
                         "boot_changed_requires_reconciliation")
        self.assertEqual(restarted.broker.consumed_count(), 1)
        self.assertEqual(restarted.broker.inspect(now=1002)["status"], "blocked")

    def test_crash_before_recorded_intent_blocks(self):
        restarted = self.mock.restart(new_epoch="mock-epoch-0002")
        self.assertEqual(self.attempt(restarted)["reason"],
                         "boot_changed_requires_reconciliation")
        self.assertEqual(restarted.broker.consumed_count(), 0)

    def test_restart_cannot_reclaim_foreign_lease(self):
        restarted = self.mock.restart(new_epoch="mock-epoch-0002")
        result = restarted.claim(owner="S-another-owner")
        self.assertEqual(result["reason"], "lease_busy")
        self.assertIs(result["can_submit_gpu"], False)

    def test_busy_queue_denied(self):
        self.mock.queue.make_busy()
        self.assertEqual(self.attempt()["reason"], "queue_busy")

    def test_missing_isolation_evidence_denied(self):
        self.assertEqual(self.attempt(isolation={})["reason"],
                         "external_os_isolation_unproven")
        self.assertEqual(self.mock.broker.consumed_count(), 0)

    def test_unsupported_isolation_kind_denied(self):
        evidence = synthetic_isolation()
        evidence["kind"] = "mock-only"
        self.assertEqual(self.attempt(isolation=evidence)["reason"],
                         "external_os_isolation_unproven")

    def test_clock_regression_denied_and_blocks(self):
        self.assertEqual(self.attempt(now=999)["reason"], "clock_regression")
        self.assertEqual(self.mock.broker.inspect(now=1002)["status"], "blocked")

    def test_concurrent_mock_attempts_only_one_consumed(self):
        barrier = threading.Barrier(2)
        def contender():
            barrier.wait(timeout=5)
            return self.attempt()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            results = [f.result(timeout=10) for f in futures]
        self.assertEqual(sum(r["status"] == "shadow_recorded_only"
                             for r in results), 1)
        self.assertEqual(sum(r.get("reason") == "idempotency_replayed"
                             for r in results), 1)
        self.assertEqual(self.mock.broker.consumed_count(), 1)

    def test_network_transport_never_invoked(self):
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("network prohibited")), \
             patch.object(socket.socket, "connect",
                          side_effect=AssertionError("network prohibited")):
            self.assertIs(self.attempt()["can_submit_gpu"], False)

    def test_all_matrix_scenarios_fail_closed(self):
        report = run_fault_matrix()
        self.assertEqual(report["passed"], 8)
        self.assertEqual(report["total"], 8)
        self.assertFalse(report["can_submit_gpu"])
        self.assertEqual(report["g2"], "UNVERIFIED")
        self.assertEqual(report["g3"], "NO_GO")

    def test_reopen_existing_database_wal(self):
        self.assertEqual(self.mock.broker.journal_mode(), "wal")
        reopened = self.mock.restart(new_epoch="mock-epoch-0002")
        self.assertEqual(reopened.broker.journal_mode(), "wal")


if __name__ == "__main__":
    unittest.main()
