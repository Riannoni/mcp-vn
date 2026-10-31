"""Offline SQLite WAL lease + shadow-only pre-submit recheck regression suite."""
import copy
import importlib.util
import pathlib
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_gpu_governor", ROOT / "render_gpu_governor.py")
GOV = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GOV)

NOW = 1_800_000_000.0
H = lambda c: c * 64


def snapshot(now=NOW):
    return {
        "lease": {"owner": "forged", "fence": "forged", "exclusive": True,
                  "active_owners": ["forged"], "expires_at": now + 100},
        "queue": {"known": True, "running": [], "pending": [],
                  "observed_at": now - 3},
        "sandbox": {"disposable": True, "source_game_id": "canonical",
                    "sandbox_game_id": "disposable-1",
                    "source_save_sha256": H("a"), "baseline_source_sha256": H("a"),
                    "sandbox_save_sha256": H("b"), "baseline_sandbox_sha256": H("b"),
                    "diff_sha256": H("c"), "dirty": False, "observed_at": now - 8},
        "review": {"approved": True, "reviewer": "independent-reviewer",
                   "source_save_sha256": H("a"), "sandbox_save_sha256": H("b"),
                   "diff_sha256": H("c"), "reviewed_at": now - 4},
        "scene": {"expected_game_id": "disposable-1", "current_game_id": "disposable-1",
                  "expected_version": 5, "current_version": 5,
                  "expected_fingerprint": H("d"), "current_fingerprint": H("d"),
                  "expected_action_id": "act-1", "current_action_id": "act-1",
                  "expected_job_id": "job-1", "current_job_id": "job-1",
                  "observed_at": now - 2},
    }


class GovernorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "governor.sqlite"
        self.gov = GOV.ShadowGpuGovernor(self.path)

    def claim(self, owner="S-first", now=NOW, ttl=120):
        return self.gov.claim(owner=owner, now=now, ttl=ttl)

    def test_racing_claimants_only_one_wins(self):
        barrier = threading.Barrier(2)

        def race(owner):
            other = GOV.ShadowGpuGovernor(self.path)
            barrier.wait(timeout=5)
            return other.claim(owner=owner, now=NOW, ttl=120)

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(race, "S-race-a")
            b = pool.submit(race, "S-race-b")
            results = [a.result(timeout=10), b.result(timeout=10)]
        self.assertEqual(sum(r["status"] == "claimed" for r in results), 1)
        self.assertEqual(sum(r["status"] == "denied" for r in results), 1)
        self.assertEqual(GOV.ShadowGpuGovernor(self.path).inspect(now=NOW)["status"], "active")

    def test_wal_persists_lease_across_instances(self):
        r = self.claim()
        self.assertEqual(r["status"], "claimed")
        self.assertIs(r["can_submit_gpu"], False)
        self.assertEqual(self.gov.journal_mode(), "wal")
        self.assertEqual(GOV.ShadowGpuGovernor(self.path).claim(
            owner="S-other", now=NOW, ttl=120)["reason"], "lease_busy")

    def test_claimed_fence_is_random_and_not_user_supplied(self):
        r = self.claim()
        self.assertRegex(r["fence"], r"^[0-9a-f]{32}$")
        self.assertEqual(self.gov.claim(owner="S-first", now=NOW, ttl=120)["reason"],
                         "lease_busy")

    def test_valid_mock_recheck_is_only_shadow_ready(self):
        r = self.claim()
        result = self.gov.recheck(owner="S-first", fence=r["fence"],
                                  snapshot=snapshot(), now=NOW)
        self.assertEqual(result["status"], "shadow_ready")
        self.assertIs(result["can_submit_gpu"], False)

    def test_queue_busy_after_initial_preflight_denies(self):
        r = self.claim()
        first = self.gov.recheck(owner="S-first", fence=r["fence"],
                                 snapshot=snapshot(), now=NOW)
        self.assertEqual(first["status"], "shadow_ready")
        second_snapshot = snapshot(NOW + 5)
        second_snapshot["queue"]["running"] = ["foreign-job"]
        second = self.gov.recheck(owner="S-first", fence=r["fence"],
                                  snapshot=second_snapshot, now=NOW + 5)
        self.assertEqual(second["reason"], "queue_busy")
        self.assertIs(second["can_submit_gpu"], False)

    def test_expired_lease_blocked_until_manual_reconciliation(self):
        r = self.claim(ttl=10)
        self.assertEqual(self.gov.claim(owner="S-other", now=NOW + 11,
                                        ttl=10)["reason"], "expired_requires_manual_reconciliation")
        self.assertEqual(self.gov.claim(owner="S-third", now=NOW + 12,
                                        ttl=10)["reason"], "manual_reconciliation_required")
        self.assertEqual(self.gov.heartbeat(owner="S-first", fence=r["fence"],
                                            now=NOW + 12, ttl=10)["status"], "denied")
        self.assertEqual(self.gov.release(owner="S-first", fence=r["fence"],
                                          now=NOW + 12)["status"], "denied")
        self.assertEqual(self.gov.inspect(now=NOW + 12)["status"], "blocked")

    def test_changed_source_save_denies_recheck(self):
        r = self.claim()
        s = snapshot()
        s["sandbox"]["source_save_sha256"] = H("e")
        result = self.gov.recheck(owner="S-first", fence=r["fence"],
                                  snapshot=s, now=NOW)
        self.assertEqual(result["reason"], "source_save_changed")

    def test_changed_disposable_save_denies_recheck(self):
        r = self.claim()
        s = snapshot()
        s["sandbox"]["sandbox_save_sha256"] = H("e")
        self.assertEqual(self.gov.recheck(owner="S-first", fence=r["fence"],
                                          snapshot=s, now=NOW)["reason"],
                         "sandbox_save_changed")

    def test_changed_diff_after_independent_review_denies(self):
        r = self.claim()
        s = snapshot()
        s["sandbox"]["diff_sha256"] = H("e")
        self.assertEqual(self.gov.recheck(owner="S-first", fence=r["fence"],
                                          snapshot=s, now=NOW)["reason"],
                         "review_mismatch")

    def test_self_review_denied(self):
        r = self.claim()
        s = snapshot()
        s["review"]["reviewer"] = "S-first"
        self.assertEqual(self.gov.recheck(owner="S-first", fence=r["fence"],
                                          snapshot=s, now=NOW)["reason"],
                         "review_not_independent")

    def test_forged_snapshot_lease_is_not_trusted(self):
        r = self.claim()
        s = snapshot()
        s["lease"]["owner"] = "malicious"
        s["lease"]["expires_at"] = NOW + 999999
        self.assertEqual(self.gov.recheck(owner="S-first", fence=r["fence"],
                                          snapshot=s, now=NOW)["status"],
                         "shadow_ready")

    def test_wrong_owner_and_fence_never_authorized(self):
        r = self.claim()
        self.assertEqual(self.gov.recheck(owner="S-other", fence=r["fence"],
                                          snapshot=snapshot(), now=NOW)["reason"],
                         "fence_mismatch")
        self.assertEqual(self.gov.recheck(owner="S-first", fence="0" * 32,
                                          snapshot=snapshot(), now=NOW)["reason"],
                         "fence_mismatch")
        self.assertEqual(self.gov.release(owner="S-first", fence="0" * 32,
                                          now=NOW)["status"], "denied")

    def test_heartbeat_validates_fence_and_expiration(self):
        r = self.claim(ttl=10)
        self.assertEqual(self.gov.heartbeat(owner="S-first", fence="0" * 32,
                                            now=NOW + 2, ttl=10)["status"], "denied")
        hb = self.gov.heartbeat(owner="S-first", fence=r["fence"],
                                now=NOW + 2, ttl=10)
        self.assertEqual(hb["status"], "renewed")
        self.assertEqual(hb["expires_at"], NOW + 12)
        self.assertEqual(self.gov.heartbeat(owner="S-first", fence=r["fence"],
                                            now=NOW + 13, ttl=10)["reason"],
                         "expired_requires_manual_reconciliation")

    def test_expired_recheck_fails_closed(self):
        r = self.claim(ttl=10)
        self.assertEqual(self.gov.recheck(owner="S-first", fence=r["fence"],
                                          snapshot=snapshot(NOW + 11), now=NOW + 11)["reason"],
                         "expired_requires_manual_reconciliation")

    def test_clean_release_fenced_then_new_owner(self):
        r = self.claim()
        self.assertEqual(self.gov.release(owner="S-first", fence=r["fence"],
                                          now=NOW + 1)["status"], "released")
        next_ = self.claim(owner="S-next", now=NOW + 2)
        self.assertEqual(next_["status"], "claimed")
        self.assertNotEqual(r["fence"], next_["fence"])
        self.assertEqual(self.gov.release(owner="S-first", fence=r["fence"],
                                          now=NOW + 3)["status"], "denied")

    def test_invalid_ttl_owner_and_clock_denied(self):
        for ttl in (0, -1, 601, True, float("nan")):
            self.assertEqual(self.claim(ttl=ttl)["status"], "denied")
        self.assertEqual(self.claim(owner="bad owner")["status"], "denied")
        self.assertEqual(self.claim(now=float("nan"))["status"], "denied")

    def test_unknown_queue_and_stale_scene_fail_closed(self):
        r = self.claim()
        s = snapshot()
        s["queue"]["known"] = False
        self.assertEqual(self.gov.recheck(owner="S-first", fence=r["fence"],
                                          snapshot=s, now=NOW)["reason"], "queue_unknown")
        s = snapshot()
        s["scene"]["current_version"] = 6
        self.assertEqual(self.gov.recheck(owner="S-first", fence=r["fence"],
                                          snapshot=s, now=NOW)["reason"], "scene_version_changed")

    def test_no_live_comfy_or_network_path(self):
        import ast
        tree = ast.parse((ROOT / "render_gpu_governor.py").read_text())
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name.split(".")[0] for n in imports for a in n.names}
        self.assertFalse(names & {"socket", "requests", "urllib", "http",
                                  "subprocess", "paramiko", "aiohttp"})


if __name__ == "__main__":
    unittest.main()
