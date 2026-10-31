"""Deterministic, source-only tests for mock queue-submit TOCTOU fencing."""
import ast
import pathlib
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from scripts.render_gpu_governor import ShadowGpuGovernor
from scripts.render_gpu_submit_fence import ShadowQueue, shadow_submit

NOW = 1_800_000_000.0


def evidence(now=NOW):
    h = lambda c: c * 64
    return {
        "lease": {"owner": "forged", "fence": "0" * 32, "exclusive": True,
                  "active_owners": ["forged"], "expires_at": now + 500},
        "queue": {"known": True, "running": [], "pending": [], "observed_at": now},
        "sandbox": {"disposable": True, "source_game_id": "canonical",
                    "sandbox_game_id": "disposable-1",
                    "source_save_sha256": h("a"), "baseline_source_sha256": h("a"),
                    "sandbox_save_sha256": h("b"), "baseline_sandbox_sha256": h("b"),
                    "diff_sha256": h("c"), "dirty": False, "observed_at": now - 8},
        "review": {"approved": True, "reviewer": "independent-reviewer",
                   "source_save_sha256": h("a"), "sandbox_save_sha256": h("b"),
                   "diff_sha256": h("c"), "reviewed_at": now - 4},
        "scene": {"expected_game_id": "disposable-1", "current_game_id": "disposable-1",
                  "expected_version": 5, "current_version": 5,
                  "expected_fingerprint": h("d"), "current_fingerprint": h("d"),
                  "expected_action_id": "act-1", "current_action_id": "act-1",
                  "expected_job_id": "job-1", "current_job_id": "job-1",
                  "observed_at": now},
    }


class ShadowSubmitFenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.gov = ShadowGpuGovernor(pathlib.Path(tmp.name) / "shadow.sqlite")
        self.lease = self.gov.claim(owner="S-owner", now=NOW, ttl=120)
        self.assertEqual(self.lease["status"], "claimed")
        self.queue = ShadowQueue()

    def submit(self, *, expected_revision=None, now=NOW, snapshot=None,
               owner="S-owner", fence=None, job_id="job-1"):
        if expected_revision is None:
            expected_revision = self.queue.observe(now=now)["revision"]
        return shadow_submit(self.gov, self.queue, owner=owner,
                             fence=self.lease["fence"] if fence is None else fence,
                             expected_revision=expected_revision,
                             job_id=job_id, snapshot=evidence(now) if snapshot is None else snapshot,
                             now=now)

    def test_negative_concurrent_foreign_submit_between_preflight_and_commit(self):
        observed = self.queue.observe(now=NOW)
        first = self.gov.recheck(owner="S-owner", fence=self.lease["fence"],
                                 snapshot=evidence(), now=NOW)
        self.assertEqual(first["status"], "shadow_ready")
        ready = threading.Event()
        injected = threading.Event()

        def foreign_writer():
            self.assertTrue(ready.wait(timeout=3))
            self.queue.inject_foreign_job("foreign-1")
            injected.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(foreign_writer)
            ready.set()
            self.assertTrue(injected.wait(timeout=3))
            future.result(timeout=3)
        denied = self.submit(expected_revision=observed["revision"])
        self.assertEqual(denied["reason"], "queue_revision_changed")
        self.assertIs(denied["can_submit_gpu"], False)
        self.assertEqual(self.queue.observe(now=NOW)["pending"], ["foreign-1"])

    def test_current_busy_queue_denied_even_with_current_revision(self):
        self.queue.inject_foreign_job("foreign-2")
        result = self.submit()
        self.assertEqual(result["reason"], "queue_busy")
        self.assertIs(result["can_submit_gpu"], False)

    def test_aba_empty_queue_still_denied_on_revision_change(self):
        rev = self.queue.observe(now=NOW)["revision"]
        self.queue.inject_foreign_job("foreign-3")
        self.queue.clear_for_test()
        self.assertEqual(self.queue.observe(now=NOW)["pending"], [])
        self.assertEqual(self.submit(expected_revision=rev)["reason"],
                         "queue_revision_changed")

    def test_one_mock_commit_only_never_grants_live_gpu(self):
        rev = self.queue.observe(now=NOW)["revision"]
        result = self.submit(expected_revision=rev)
        self.assertEqual(result["status"], "shadow_recorded_only")
        self.assertIs(result["can_submit_gpu"], False)
        self.assertEqual(self.queue.observe(now=NOW)["pending"], ["job-1"])
        self.assertEqual(self.submit(expected_revision=rev)["reason"],
                         "queue_revision_changed")

    def test_two_concurrent_mock_submitters_only_one_wins(self):
        rev = self.queue.observe(now=NOW)["revision"]
        barrier = threading.Barrier(2)

        def runner():
            barrier.wait(timeout=3)
            return self.submit(expected_revision=rev)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(runner) for _ in range(2)]
            results = [f.result(timeout=5) for f in futures]
        self.assertEqual(sum(x["status"] == "shadow_recorded_only" for x in results), 1)
        self.assertEqual(sum(x["reason"] == "queue_revision_changed"
                             for x in results if x["status"] == "denied"), 1)

    def test_stale_lease_fence_and_expired_lease_fail_closed(self):
        self.assertEqual(self.submit(fence="0" * 32)["reason"], "fence_mismatch")
        expired = self.submit(now=NOW + 121, snapshot=evidence(NOW + 121))
        self.assertEqual(expired["reason"], "expired_requires_manual_reconciliation")
        self.assertEqual(self.queue.observe(now=NOW)["pending"], [])

    def test_scene_observation_before_atomic_queue_check_denied(self):
        s = evidence()
        s["scene"]["observed_at"] = NOW - 1
        self.assertEqual(self.submit(snapshot=s)["reason"],
                         "scene_observation_stale")
        self.assertEqual(self.queue.observe(now=NOW)["revision"], 0)

    def test_changed_source_hash_denies_without_queue_mutation(self):
        s = evidence()
        s["sandbox"]["source_save_sha256"] = "e" * 64
        self.assertEqual(self.submit(snapshot=s)["reason"], "source_save_changed")
        self.assertEqual(self.queue.observe(now=NOW)["revision"], 0)

    def test_snapshot_cannot_override_actual_mock_queue(self):
        self.queue.inject_foreign_job("foreign-4")
        forged = evidence()
        forged["queue"]["running"] = []
        forged["queue"]["pending"] = []
        self.assertEqual(self.submit(snapshot=forged)["reason"], "queue_busy")

    def test_job_id_not_bound_to_scene_denied(self):
        self.assertEqual(self.submit(job_id="different-job")["reason"],
                         "job_binding_mismatch")
        self.assertEqual(self.queue.observe(now=NOW)["revision"], 0)

    def test_invalid_revision_and_job_id_fail_closed(self):
        for revision in (-1, True, 1.5, "0"):
            self.assertEqual(self.submit(expected_revision=revision)["status"], "denied")
        self.assertEqual(self.submit(job_id="bad job id")["status"], "denied")
        self.assertEqual(self.queue.observe(now=NOW)["revision"], 0)

    def test_no_live_submit_transport_in_module(self):
        p = pathlib.Path(__file__).resolve().parents[1] / "render_gpu_submit_fence.py"
        tree = ast.parse(p.read_text())
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                imported.add(n.module.split(".")[0])
        self.assertFalse(imported & {"socket", "requests", "urllib", "http",
                                     "subprocess", "aiohttp", "paramiko"})
        self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr in
                             {"post", "put", "request", "urlopen"} for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
