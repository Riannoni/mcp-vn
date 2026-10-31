"""Source-only negative tests: a known Comfy /prompt bypass denies admission."""
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.render_gpu_exclusive_admission import (
    KNOWN_SINKS, collect_live_snapshot, evaluate_preflight,
)


def digest(s):
    return hashlib.sha256(s.encode("ascii")).hexdigest()


def good_snapshot():
    return {
        "sources": {
            path: {"sha256": digest(path), "direct_prompt": False,
                   "broker_only": True, "os_denied_direct": True}
            for path in KNOWN_SINKS
        },
        "topology": {
            "network_mode": "private", "host_publish": False,
            "host_listener": False, "worker_uid": 1001,
            "comfy_uid": 1002, "broker_uid": 1003,
            "podman_control_separated": True, "broker_socket_acl": True,
            "container_peer_denied": True, "foreign_client_denied": True,
        },
        "attestation": {
            "operator": "ops", "reviewer": "independent",
            "evidence_sha256": digest("attestation"),
            "host_bypass_denied": True, "worker_bypass_denied": True,
            "container_bypass_denied": True, "foreign_bypass_denied": True,
        },
        "admission": {
            "owner": "S-test", "fence": "f" * 32,
            "current_owner": "S-test", "current_fence": "f" * 32,
            "boot_id": "boot-1", "current_boot_id": "boot-1",
            "lease_valid": True, "atomic_fenced_submit": True,
            "durable_intent": True, "disposable_save": True,
            "save_sha": digest("save"), "current_save_sha": digest("save"),
            "scene_sha": digest("scene"), "current_scene_sha": digest("scene"),
            "scene_version": 7, "current_scene_version": 7,
            "queue_generation": 17, "baseline_generation": 17,
            "queue_history_sha": digest("queue"), "baseline_history_sha": digest("queue"),
            "queue_running": 0, "queue_pending": 0,
            "history_complete": True, "unknown_jobs": False,
            "concurrent_game_submit": False, "game_protected": True,
            "rollback_verified": True,
        },
    }


class AdmissionTests(unittest.TestCase):
    def check_denied(self, changed, reason):
        result = evaluate_preflight(changed)
        self.assertFalse(result["can_submit_gpu"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn(reason, result["blockers"])

    def test_complete_mock_is_only_unverified_candidate(self):
        result = evaluate_preflight(good_snapshot())
        self.assertEqual(result["status"], "candidate_unverified")
        self.assertFalse(result["can_submit_gpu"])
        self.assertIn("source_only_not_live_authority", result["blockers"])

    def test_known_direct_prompt_path_is_denied_even_if_everything_else_green(self):
        s = good_snapshot()
        s["sources"]["worker/worker.py"]["direct_prompt"] = True
        self.check_denied(s, "direct_prompt_bypass")

    def test_all_known_sinks_must_be_inventoried(self):
        s = good_snapshot()
        del s["sources"]["active/worker.py"]
        self.check_denied(s, "sink_inventory_incomplete")

    def test_unexpected_sink_requires_new_review(self):
        s = good_snapshot()
        s["sources"]["custom/plugin.py"] = {"sha256": digest("plugin"),
            "direct_prompt": False, "broker_only": True, "os_denied_direct": True}
        self.check_denied(s, "sink_inventory_incomplete")

    def test_voluntary_broker_only_flag_is_not_os_enforcement(self):
        s = good_snapshot()
        s["sources"]["standalone-web/server.py"]["os_denied_direct"] = False
        self.check_denied(s, "sink_os_bypass_not_denied")

    def test_real_pasta_same_uid_host_loopback_bypass(self):
        s = good_snapshot()
        s["topology"].update(network_mode="pasta", host_publish=True,
                             host_listener=True, comfy_uid=1001)
        self.check_denied(s, "uncontrolled_host_comfy_listener")
        self.check_denied(s, "os_uid_boundary_missing")

    def test_queue_empty_aba_must_deny(self):
        s = good_snapshot()
        s["admission"]["queue_generation"] += 2
        self.check_denied(s, "queue_aba_or_foreign_generation")

    def test_queue_history_gap_must_deny(self):
        s = good_snapshot()
        s["admission"]["queue_history_sha"] = digest("different")
        self.check_denied(s, "queue_history_changed")

    def test_stale_fence_must_deny(self):
        s = good_snapshot()
        s["admission"]["current_fence"] = "e" * 32
        self.check_denied(s, "stale_fence_or_owner")

    def test_boot_change_must_deny(self):
        s = good_snapshot()
        s["admission"]["current_boot_id"] = "boot-2"
        self.check_denied(s, "stale_boot_or_lease")

    def test_scene_or_save_change_must_deny(self):
        for field in ("current_save_sha", "current_scene_sha", "current_scene_version"):
            with self.subTest(field=field):
                s = good_snapshot()
                s["admission"][field] = 8 if field.endswith("version") else digest("changed")
                self.check_denied(s, "disposable_scene_or_save_changed")

    def test_concurrent_user_game_submit_denied(self):
        s = good_snapshot()
        s["admission"]["concurrent_game_submit"] = True
        self.check_denied(s, "concurrent_game_or_unknown_job")

    def test_unknown_job_even_when_queue_empty_denied(self):
        s = good_snapshot()
        s["admission"]["unknown_jobs"] = True
        self.check_denied(s, "concurrent_game_or_unknown_job")

    def test_missing_independent_attestation_denied(self):
        s = good_snapshot()
        s["attestation"]["reviewer"] = "ops"
        self.check_denied(s, "independent_bypass_attestation_missing")

    def test_missing_rollback_denied(self):
        s = good_snapshot()
        s["admission"]["rollback_verified"] = False
        self.check_denied(s, "rollback_or_game_protection_missing")

    def test_live_path_fixture_scans_actual_named_sink_and_listener(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for path in KNOWN_SINKS:
                if path == "active/worker.py":
                    continue
                f = root / path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text('URL = "http://127.0.0.1:8188/prompt"\n' if
                             path == "worker/worker.py" else 'x = 1\n', encoding="utf8")
            active = root / "active-worker.py"
            active.write_text("x = 1\n", encoding="utf8")
            def run(cmd, **kwargs):
                if cmd[0] == "ss":
                    return subprocess.CompletedProcess(cmd, 0,
                        'LISTEN 0 128 127.0.0.1:8188 0.0.0.0:* users:(("pasta.avx2",pid=1234,fd=3))\n', "")
                if cmd[0] == "podman":
                    return subprocess.CompletedProcess(cmd, 0, "pasta|1235|\n", "")
                if cmd[0] == "systemctl":
                    return subprocess.CompletedProcess(cmd, 0, "1236\n", "")
                raise AssertionError(cmd)
            with patch("scripts.render_gpu_exclusive_admission.subprocess.run", side_effect=run):
                with patch("scripts.render_gpu_exclusive_admission._pid_uid", return_value=1000):
                    snapshot = collect_live_snapshot(root, active)
            self.assertTrue(snapshot["sources"]["worker/worker.py"]["direct_prompt"])
            self.assertTrue(snapshot["topology"]["host_listener"])
            self.assertEqual(snapshot["topology"]["network_mode"], "pasta")
            self.check_denied(snapshot, "direct_prompt_bypass")




class IsolatedCliSmokeTests(unittest.TestCase):
    def run_fixture(self, snapshot):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "fixture.json"
            path.write_text(json.dumps(snapshot), encoding="utf8")
            return subprocess.run(
                [sys.executable, "-m", "scripts.render_gpu_exclusive_admission",
                 "--snapshot", str(path)],
                capture_output=True, text=True, timeout=8, check=False,
            )

    def test_cli_green_fixture_is_not_gpu_permission(self):
        result = self.run_fixture(good_snapshot())
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "candidate_unverified")
        self.assertFalse(report["can_submit_gpu"])

    def test_cli_direct_bypass_fails_closed_with_exit_2(self):
        snapshot = good_snapshot()
        snapshot["sources"]["active/worker.py"]["direct_prompt"] = True
        result = self.run_fixture(snapshot)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("direct_prompt_bypass", json.loads(result.stdout)["blockers"])

    def test_rollback_plan_never_reopens_unfenced_post(self):
        from scripts.render_gpu_exclusive_admission import reversible_isolation_proposal
        steps = reversible_isolation_proposal()
        self.assertTrue(any("ROLLBACK" in x for x in steps))
        self.assertTrue(any("Never reopen unfenced" in x for x in steps))
        self.assertTrue(any("Chief approval" in x for x in steps))

if __name__ == "__main__":
    unittest.main()
