"""Source-only fail-closed admission regression: no Comfy POST or GPU."""
import copy
import pathlib
import socket
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from scripts.render_gpu_broker_admission import ShadowBrokerAdmission

NOW = 1_800_000_000.0
H = lambda c: c * 64
BOOT = "boot-0001"


def manifest(key="one-shot-0001"):
    return {
        "source_sha": H("a"), "save_sha": H("b"), "scene_sha": H("c"),
        "scene_version": 7, "reviewer_id": "independent-G2-reviewer",
        "reviewer_sha": H("d"), "request_sha": H("e"),
        "idempotency_key": key,
    }


def queue(generation=9):
    return {
        "authoritative": True, "generation": generation,
        "history_sha": H("f"), "running": 0, "pending": 0,
        "foreign_submit": False,
    }


def isolation():
    return {
        "kind": "os_network_isolation", "enforced": True,
        "independent_attestation_sha": H("1"),
        "blocked_bypass_tests_sha": H("2"),
    }


class BrokerAdmissionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db_path = pathlib.Path(tmp.name) / "broker.sqlite"
        self.broker = ShadowBrokerAdmission(self.db_path)

    def claim(self, owner="S-owner", boot_id=BOOT, now=NOW, ttl=120,
              expected=None, observed_queue=None):
        return self.broker.claim(
            owner=owner, boot_id=boot_id, now=now, ttl=ttl,
            manifest=manifest() if expected is None else expected,
            queue_baseline=queue() if observed_queue is None else observed_queue,
        )

    def admit(self, lease, owner="S-owner", boot_id=BOOT, now=NOW,
              observed=None, observed_queue=None, os_evidence=None):
        return self.broker.admit(
            owner=owner, fence=lease["fence"], boot_id=boot_id, now=now,
            observed_manifest=manifest() if observed is None else observed,
            observed_queue=queue() if observed_queue is None else observed_queue,
            isolation_evidence=isolation() if os_evidence is None else os_evidence,
        )

    def test_first_negative_two_concurrent_clients_only_one_claim(self):
        barrier = threading.Barrier(2)

        def race(owner):
            broker = ShadowBrokerAdmission(self.db_path)
            barrier.wait(timeout=5)
            return broker.claim(owner=owner, boot_id=BOOT, now=NOW, ttl=120,
                                manifest=manifest(), queue_baseline=queue())

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(race, "S-first"), pool.submit(race, "S-second")]
            results = [f.result(timeout=10) for f in futures]
        self.assertEqual(sum(r["status"] == "claimed" for r in results), 1)
        self.assertEqual(sum(r["status"] == "denied" for r in results), 1)
        self.assertTrue(all(r["can_submit_gpu"] is False for r in results))

    def test_boot_change_denies_and_permanently_blocks(self):
        lease = self.claim()
        r = self.admit(lease, boot_id="boot-0002")
        self.assertEqual(r["reason"], "boot_changed_requires_reconciliation")
        self.assertEqual(self.broker.inspect(now=NOW)["status"], "blocked")
        self.assertEqual(self.claim(owner="S-next")["reason"],
                         "manual_reconciliation_required")

    def test_replayed_prompt_idempotency_denied_across_new_lease(self):
        lease = self.claim()
        first = self.admit(lease)
        self.assertEqual(first["status"], "shadow_recorded_only")
        self.assertIs(first["can_submit_gpu"], False)
        self.assertEqual(self.admit(lease)["reason"], "idempotency_replayed")
        self.assertEqual(self.broker.journal_mode(), "wal")
        self.assertEqual(self.broker.consumed_count(), 1)
        self.assertEqual(self.broker.release(owner="S-owner", fence=lease["fence"],
                                             boot_id=BOOT, now=NOW + 1)["status"],
                         "released")
        self.assertEqual(self.claim(owner="S-next")["reason"],
                         "idempotency_replayed")

    def test_foreign_direct_prompt_denied_even_when_queue_empty(self):
        lease = self.claim()
        observed = queue()
        observed["foreign_submit"] = True
        self.assertEqual(self.admit(lease, observed_queue=observed)["reason"],
                         "foreign_submission_detected")
        self.assertEqual(self.broker.consumed_count(), 0)
        self.assertEqual(self.broker.inspect(now=NOW)["status"], "blocked")

    def test_queue_aba_generation_changed_even_when_empty(self):
        lease = self.claim()
        self.assertEqual(self.admit(lease, observed_queue=queue(11))["reason"],
                         "queue_generation_changed")
        self.assertEqual(self.broker.consumed_count(), 0)

    def test_queue_history_change_denied(self):
        lease = self.claim()
        q = queue()
        q["history_sha"] = H("9")
        self.assertEqual(self.admit(lease, observed_queue=q)["reason"],
                         "queue_history_changed")

    def test_missing_authoritative_generation_history_denied(self):
        q = queue()
        q.pop("generation")
        self.assertEqual(self.claim(observed_queue=q)["reason"],
                         "queue_not_authoritative")
        q = queue()
        q["history_sha"] = None
        self.assertEqual(self.claim(observed_queue=q)["reason"],
                         "queue_not_authoritative")
        lease = self.claim()
        q = queue()
        q["authoritative"] = False
        self.assertEqual(self.admit(lease, observed_queue=q)["reason"],
                         "queue_not_authoritative")

    def test_busy_queue_denied(self):
        lease = self.claim()
        q = queue()
        q["pending"] = 1
        self.assertEqual(self.admit(lease, observed_queue=q)["reason"], "queue_busy")

    def test_stale_owner_or_fence_denied(self):
        lease = self.claim()
        self.assertEqual(self.admit(lease, owner="S-foreign")["reason"],
                         "fence_mismatch")
        self.assertEqual(self.broker.admit(
            owner="S-owner", fence="0" * 32, boot_id=BOOT, now=NOW,
            observed_manifest=manifest(), observed_queue=queue(),
            isolation_evidence=isolation())["reason"], "fence_mismatch")
        self.assertEqual(self.broker.consumed_count(), 0)

    def test_expired_lease_denies_and_stays_blocked(self):
        lease = self.claim(ttl=10)
        self.assertEqual(self.admit(lease, now=NOW + 10)["reason"],
                         "expired_requires_manual_reconciliation")
        self.assertEqual(self.claim(owner="S-next", now=NOW + 11)["reason"],
                         "manual_reconciliation_required")

    def test_changed_source_save_scene_version_or_review_denied(self):
        for field, value in (
            ("source_sha", H("9")), ("save_sha", H("9")),
            ("scene_sha", H("9")), ("scene_version", 8),
            ("reviewer_sha", H("9")), ("request_sha", H("9")),
            ("idempotency_key", "one-shot-0002"),
        ):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    b = ShadowBrokerAdmission(pathlib.Path(tmp) / "db.sqlite")
                    lease = b.claim(owner="S-owner", boot_id=BOOT, now=NOW,
                                    ttl=120, manifest=manifest(),
                                    queue_baseline=queue())
                    m = manifest()
                    m[field] = value
                    result = b.admit(owner="S-owner", fence=lease["fence"],
                                     boot_id=BOOT, now=NOW,
                                     observed_manifest=m, observed_queue=queue(),
                                     isolation_evidence=isolation())
                    self.assertEqual(result["reason"], "immutable_manifest_changed")
                    self.assertEqual(b.consumed_count(), 0)

    def test_self_review_or_missing_review_denied_at_claim(self):
        m = manifest()
        m["reviewer_id"] = "S-owner"
        self.assertEqual(self.claim(expected=m)["reason"], "invalid_manifest")
        m = manifest()
        m["reviewer_sha"] = None
        self.assertEqual(self.claim(expected=m)["reason"], "invalid_manifest")

    def test_isolation_boolean_is_not_an_attestation(self):
        lease = self.claim()
        self.assertEqual(self.admit(lease, os_evidence=True)["reason"],
                         "external_os_isolation_unproven")
        self.assertEqual(self.broker.consumed_count(), 0)

    def test_incomplete_isolation_attestation_denied(self):
        lease = self.claim()
        e = isolation()
        e.pop("blocked_bypass_tests_sha")
        self.assertEqual(self.admit(lease, os_evidence=e)["reason"],
                         "external_os_isolation_unproven")

    def test_mock_attestation_never_authorizes_live_gpu(self):
        lease = self.claim()
        result = self.admit(lease)
        self.assertEqual(result["status"], "shadow_recorded_only")
        self.assertFalse(result["can_submit_gpu"])
        self.assertIn("os_isolation_requires_external_proof",
                      result["live_blockers"])
        self.assertIn("atomic_comfy_submit_not_integrated",
                      result["live_blockers"])

    def test_no_network_or_gpu_request_sent(self):
        lease = self.claim()
        with patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK")), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK")):
            result = self.admit(lease)
        self.assertFalse(result["can_submit_gpu"])
        self.assertEqual(result["status"], "shadow_recorded_only")

    def test_double_admit_concurrent_only_one_consumption(self):
        lease = self.claim()
        barrier = threading.Barrier(2)

        def race():
            b = ShadowBrokerAdmission(self.db_path)
            barrier.wait(timeout=5)
            return b.admit(owner="S-owner", fence=lease["fence"],
                           boot_id=BOOT, now=NOW,
                           observed_manifest=manifest(), observed_queue=queue(),
                           isolation_evidence=isolation())

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(race) for _ in range(2)]
            results = [f.result(timeout=10) for f in futures]
        self.assertEqual(sum(r["status"] == "shadow_recorded_only" for r in results), 1)
        self.assertEqual(sum(r.get("reason") == "idempotency_replayed" for r in results), 1)
        self.assertEqual(self.broker.consumed_count(), 1)

    def test_no_auto_reclaim_after_restart(self):
        lease = self.claim(ttl=10)
        self.assertEqual(ShadowBrokerAdmission(self.db_path).claim(
            owner="S-other", boot_id="boot-0002", now=NOW + 20,
            ttl=10, manifest=manifest("other-shot-001"),
            queue_baseline=queue())["reason"],
            "expired_requires_manual_reconciliation")
        self.assertEqual(self.broker.inspect(now=NOW + 21)["status"], "blocked")

    def test_malformed_clock_and_manifest_rejected(self):
        self.assertEqual(self.claim(now=float("nan"))["reason"], "invalid_claim")
        self.assertEqual(self.claim(now=True)["reason"], "invalid_claim")
        m = manifest()
        m["scene_version"] = True
        self.assertEqual(self.claim(expected=m)["reason"], "invalid_manifest")
        m = manifest()
        m["unexpected"] = "bypass"
        self.assertEqual(self.claim(expected=m)["reason"], "invalid_manifest")


if __name__ == "__main__":
    unittest.main()
