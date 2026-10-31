"""Negative-only synthetic, source-only preflight policy tests: no Comfy calls."""
import copy
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "render_gpu_preflight.py"
SPEC = importlib.util.spec_from_file_location("render_gpu_preflight", MODULE)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)

H = lambda char: char * 64
NOW = 1_800_000_000.0


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.s = {
            "lease": {"owner": "S-unique", "fence": "fence-123", "exclusive": True,
                      "active_owners": ["S-unique"], "expires_at": NOW + 120},
            "queue": {"known": True, "running": [], "pending": [],
                      "observed_at": NOW - 3},
            "sandbox": {"disposable": True, "source_game_id": "real-source",
                        "sandbox_game_id": "disposable-123",
                        "source_save_sha256": H("a"),
                        "sandbox_save_sha256": H("b"),
                        "baseline_source_sha256": H("a"),
                        "baseline_sandbox_sha256": H("b"),
                        "diff_sha256": H("c"), "dirty": False,
                        "observed_at": NOW - 8},
            "review": {"approved": True, "reviewer": "independent-governor",
                       "source_save_sha256": H("a"),
                       "sandbox_save_sha256": H("b"),
                       "diff_sha256": H("c"),
                       "reviewed_at": NOW - 4},
            "scene": {"expected_game_id": "disposable-123",
                      "current_game_id": "disposable-123",
                      "expected_version": 5, "current_version": 5,
                      "expected_fingerprint": H("d"),
                      "current_fingerprint": H("d"),
                      "expected_action_id": "action-1",
                      "current_action_id": "action-1",
                      "expected_job_id": "job-1", "current_job_id": "job-1",
                      "observed_at": NOW - 2},
        }

    def result(self):
        return POLICY.evaluate_preflight(copy.deepcopy(self.s), now=NOW)

    def denied(self, reason):
        result = self.result()
        self.assertEqual(result["status"], "denied")
        self.assertEqual(result["reason"], reason)
        self.assertIs(result["can_submit_gpu"], False)

    def test_valid_metadata_only_shadow_ready_never_authorizes_gpu(self):
        r = self.result()
        self.assertEqual(r["status"], "shadow_ready")
        self.assertIs(r["can_submit_gpu"], False)

    def test_unknown_queue_denied(self):
        self.s["queue"]["known"] = False
        self.denied("queue_unknown")

    def test_queue_running_denied(self):
        self.s["queue"]["running"] = ["another-job"]
        self.denied("queue_busy")

    def test_queue_pending_denied(self):
        self.s["queue"]["pending"] = ["another-job"]
        self.denied("queue_busy")

    def test_expired_lease_denied(self):
        self.s["lease"]["expires_at"] = NOW
        self.denied("lease_expired")

    def test_nonexclusive_lease_denied(self):
        self.s["lease"]["exclusive"] = False
        self.denied("lease_not_exclusive")

    def test_competing_lease_owner_denied(self):
        self.s["lease"]["active_owners"].append("other-worker")
        self.denied("competing_owner")

    def test_missing_fence_denied(self):
        self.s["lease"]["fence"] = ""
        self.denied("invalid_lease")

    def test_dirty_sandbox_denied(self):
        self.s["sandbox"]["dirty"] = True
        self.denied("sandbox_dirty")

    def test_changed_source_save_denied(self):
        self.s["sandbox"]["source_save_sha256"] = H("e")
        self.denied("source_save_changed")

    def test_changed_sandbox_save_denied(self):
        self.s["sandbox"]["sandbox_save_sha256"] = H("e")
        self.denied("sandbox_save_changed")

    def test_missing_review_denied(self):
        self.s["review"] = None
        self.denied("review_missing")

    def test_unapproved_review_denied(self):
        self.s["review"]["approved"] = False
        self.denied("review_unapproved")

    def test_self_review_denied(self):
        self.s["review"]["reviewer"] = "S-unique"
        self.denied("review_not_independent")

    def test_changed_diff_after_review_denied(self):
        self.s["sandbox"]["diff_sha256"] = H("e")
        self.denied("review_mismatch")

    def test_review_not_current_for_sandbox_denied(self):
        self.s["review"]["reviewed_at"] = NOW - 20
        self.denied("review_stale")

    def test_not_disposable_game_denied(self):
        self.s["sandbox"]["disposable"] = False
        self.denied("sandbox_not_disposable")

    def test_source_and_sandbox_same_game_denied(self):
        self.s["sandbox"]["sandbox_game_id"] = "real-source"
        self.denied("sandbox_not_disposable")

    def test_changed_scene_version_denied(self):
        self.s["scene"]["current_version"] = 6
        self.denied("scene_version_changed")

    def test_changed_scene_fingerprint_denied(self):
        self.s["scene"]["current_fingerprint"] = H("e")
        self.denied("scene_fingerprint_changed")

    def test_changed_scene_action_denied(self):
        self.s["scene"]["current_action_id"] = "action-2"
        self.denied("scene_action_changed")

    def test_changed_scene_job_denied(self):
        self.s["scene"]["current_job_id"] = "job-2"
        self.denied("scene_job_changed")

    def test_stale_queue_observation_denied(self):
        self.s["queue"]["observed_at"] = NOW - 100
        self.denied("queue_stale")

    def test_future_observation_denied(self):
        self.s["scene"]["observed_at"] = NOW + 1
        self.denied("scene_observation_stale")

    def test_missing_scene_field_denied(self):
        del self.s["scene"]["current_fingerprint"]
        self.denied("invalid_scene")

    def test_boolean_version_denied(self):
        self.s["scene"]["current_version"] = True
        self.denied("invalid_scene")

    def test_invalid_input_denied(self):
        self.assertEqual(POLICY.evaluate_preflight(None, now=NOW)["reason"],
                         "invalid_snapshot")

    def test_no_direct_io_or_network_calls(self):
        import ast
        source = MODULE.read_text() if MODULE.exists() else ""
        tree = ast.parse(source)
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {alias.name.split(".")[0] for n in imports for alias in n.names}
        self.assertFalse(names & {"subprocess", "socket", "requests", "urllib", "os",
                                  "pathlib", "http", "aiohttp", "paramiko"})


if __name__ == "__main__":
    unittest.main()
