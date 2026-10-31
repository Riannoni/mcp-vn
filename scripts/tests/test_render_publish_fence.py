"""Negative source-only tests for a conservative publish-time ABA fence.

These fixtures are synthetic. They do not inspect or modify live game data.
"""
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "render_publish_fence.py"
SPEC = importlib.util.spec_from_file_location("render_publish_fence", MODULE)
FENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FENCE)

FP = "a" * 64


class PublishFenceTests(unittest.TestCase):
    def setUp(self):
        self.expected = dict(game_id="game-a", game_version=12, scene_key="turn-3",
                             scene_fingerprint=FP, action_id="action-3",
                             job_id="job-3", attempt=1)
        self.current = {k: self.expected[k] for k in (
            "game_id", "game_version", "scene_key",
            "scene_fingerprint", "action_id")}
        self.candidate = dict(game_id="game-a", source_game_version=12,
                              scene_key="turn-3", scene_fingerprint=FP,
                              action_id="action-3", job_id="job-3",
                              attempt=1, status="done", superseded_by=None)

    def verdict(self):
        return FENCE.evaluate_fence(self.expected, self.current, self.candidate)

    def reject(self, reason):
        result = self.verdict()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], reason)
        self.assertFalse(result["can_publish"])

    def test_exact_snapshot_is_shadow_match_not_publish_authorization(self):
        result = self.verdict()
        self.assertEqual(result["status"], "shadow_match")
        self.assertFalse(result["can_publish"])

    def test_aba_same_scene_but_new_game_version_rejected(self):
        self.current["game_version"] = 14
        self.reject("version_changed")

    def test_same_fingerprint_but_new_scene_key_rejected(self):
        self.current["scene_key"] = "turn-5"
        self.reject("scene_changed")

    def test_same_scene_key_but_new_fingerprint_rejected(self):
        self.current["scene_fingerprint"] = "b" * 64
        self.reject("scene_fingerprint_changed")

    def test_same_scene_and_version_but_new_action_rejected(self):
        self.current["action_id"] = "action-4"
        self.reject("action_changed")

    def test_new_job_rejects_stale_candidate(self):
        self.candidate["job_id"] = "job-older"
        self.reject("job_mismatch")

    def test_old_retry_attempt_rejected(self):
        self.candidate["attempt"] = 0
        self.reject("invalid_candidate")
        self.candidate["attempt"] = 2
        self.reject("attempt_mismatch")

    def test_source_version_mismatch_rejected(self):
        self.candidate["source_game_version"] = 11
        self.reject("candidate_provenance_mismatch")

    def test_source_scene_fingerprint_mismatch_rejected(self):
        self.candidate["scene_fingerprint"] = "b" * 64
        self.reject("candidate_provenance_mismatch")

    def test_source_action_mismatch_rejected(self):
        self.candidate["action_id"] = "old-action"
        self.reject("candidate_provenance_mismatch")

    def test_wrong_game_rejected(self):
        self.current["game_id"] = "other-game"
        self.reject("game_mismatch")

    def test_candidate_wrong_game_rejected(self):
        self.candidate["game_id"] = "other-game"
        self.reject("candidate_provenance_mismatch")

    def test_superseded_candidate_rejected(self):
        self.candidate["superseded_by"] = "replacement"
        self.reject("candidate_superseded")

    def test_unfinished_candidate_rejected(self):
        self.candidate["status"] = "working"
        self.reject("candidate_not_done")

    def test_missing_or_malformed_fields_fail_closed(self):
        for key in tuple(self.expected):
            with self.subTest(field=key):
                original = self.expected.pop(key)
                self.reject("invalid_expected")
                self.expected[key] = original
        self.current["game_version"] = True
        self.reject("invalid_current")
        self.current["game_version"] = 12
        self.candidate["scene_fingerprint"] = "unknown"
        self.reject("invalid_candidate")

    def test_js_unsafe_integer_versions_fail_closed(self):
        self.current["game_version"] = 2**53
        self.reject("invalid_current")
        self.current["game_version"] = 12
        self.expected["game_version"] = -1
        self.reject("invalid_expected")
        self.expected["game_version"] = 12
        self.candidate["source_game_version"] = 2**53
        self.reject("invalid_candidate")

    def test_untrusted_nonmapping_payload_rejected(self):
        self.assertEqual(FENCE.evaluate_fence(None, self.current, self.candidate)["reason"],
                         "invalid_expected")
        self.assertEqual(FENCE.evaluate_fence(self.expected, [], self.candidate)["reason"],
                         "invalid_current")
        self.assertEqual(FENCE.evaluate_fence(self.expected, self.current, "not-json")["reason"],
                         "invalid_candidate")


if __name__ == "__main__":
    unittest.main()
