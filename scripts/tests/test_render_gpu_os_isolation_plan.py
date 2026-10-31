"""Offline-only negative tests for a proposed OS isolation migration."""
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "render_gpu_os_isolation_plan.py"
spec = importlib.util.spec_from_file_location("render_gpu_os_isolation_plan", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SINKS = (
    "active/worker.py",
    "worker/worker.py",
    "worker/pose_geometry_runtime.py",
    "worker/pose_reference_pipeline.py",
    "standalone-web/server.py",
    "scripts/smoke-local-repair.py",
)
SHA = "a" * 64


def fixture():
    return {
        "observed": {
            "worker_uid": 1000, "comfy_uid": 1000,
            "comfy_network_mode": "pasta", "loopback_publish": True,
            "container_netns_separate": True, "host_listener_pasta": True,
        },
        "migration": {
            "sinks": {path: "broker_only" for path in SINKS},
            "dynamic_clients_accounted": True,
            "foreign_clients_accounted": True,
            "worker_uid": 1000, "comfy_uid": 2201, "broker_uid": 2202,
            "host_publish_removed": True,
            "comfy_private_netns": True,
            "host_loopback_bypass_blocked": True,
            "container_peer_bypass_blocked": True,
            "podman_control_separated": True,
            "broker_socket_acl_enforced": True,
        },
        "attestation": {
            "executor": "migration-operator", "reviewer": "independent-auditor",
            "independent": True, "evidence_sha": SHA,
            "bypass_matrix": {
                "worker": True, "pose": True, "reference": True,
                "web": True, "smoke": True, "host_local": True,
                "container_peer": True, "foreign": True,
            },
        },
        "recovery": {
            "durable_intent": True, "queue_generation": True,
            "unknown_post_reconciliation": True,
            "complete_prompt_history": True, "restart_blocks_until_reconciled": True,
        },
    }


class IsolationPlanTests(unittest.TestCase):
    def assess(self, plan):
        result = module.assess_isolation_plan(plan)
        self.assertFalse(result["can_submit_gpu"])
        self.assertIn("source_only_not_live_authority", result["blockers"])
        return result

    def test_even_fully_claimed_plan_is_not_live_authority(self):
        result = self.assess(fixture())
        self.assertEqual(result["status"], "candidate_unverified")
        self.assertEqual(result["known_sinks"], 6)

    def test_missing_any_of_six_sinks_is_denied(self):
        for sink in SINKS:
            with self.subTest(sink=sink):
                p = fixture()
                del p["migration"]["sinks"][sink]
                self.assertIn("known_sink_unbrokered", self.assess(p)["blockers"])

    def test_direct_sink_unbrokered_is_denied(self):
        p = fixture()
        p["migration"]["sinks"][SINKS[0]] = "direct"
        self.assertIn("known_sink_unbrokered", self.assess(p)["blockers"])

    def test_unknown_extra_sink_is_denied(self):
        p = fixture()
        p["migration"]["sinks"]["foreign-plugin.py"] = "broker_only"
        self.assertIn("sink_inventory_unverified", self.assess(p)["blockers"])

    def test_dynamic_and_foreign_clients_must_be_accounted(self):
        for field in ("dynamic_clients_accounted", "foreign_clients_accounted"):
            p = fixture()
            p["migration"][field] = False
            self.assertIn("unaccounted_clients", self.assess(p)["blockers"])

    def test_existing_pasta_loopback_is_never_sufficient(self):
        p = fixture()
        p["migration"]["host_publish_removed"] = False
        self.assertIn("host_loopback_bypass_possible", self.assess(p)["blockers"])

    def test_claimed_localhost_acl_cannot_substitute_isolation(self):
        p = fixture()
        p["migration"]["host_loopback_bypass_blocked"] = False
        self.assertIn("host_loopback_bypass_possible", self.assess(p)["blockers"])

    def test_container_peer_bypass_must_be_denied(self):
        p = fixture()
        p["migration"]["container_peer_bypass_blocked"] = False
        self.assertIn("container_peer_bypass_possible", self.assess(p)["blockers"])

    def test_same_uid_cannot_be_an_enforced_boundary(self):
        p = fixture()
        p["migration"]["comfy_uid"] = 1000
        self.assertIn("os_identity_boundary_missing", self.assess(p)["blockers"])

    def test_same_uid_broker_cannot_be_an_enforced_boundary(self):
        p = fixture()
        p["migration"]["broker_uid"] = 1000
        self.assertIn("os_identity_boundary_missing", self.assess(p)["blockers"])

    def test_attestation_requires_distinct_reviewer(self):
        p = fixture()
        p["attestation"]["reviewer"] = p["attestation"]["executor"]
        self.assertIn("independent_attestation_missing", self.assess(p)["blockers"])

    def test_self_asserted_attestation_is_rejected(self):
        p = fixture()
        p["attestation"]["independent"] = False
        self.assertIn("independent_attestation_missing", self.assess(p)["blockers"])

    def test_missing_bypass_actor_is_rejected(self):
        p = fixture()
        del p["attestation"]["bypass_matrix"]["container_peer"]
        self.assertIn("bypass_matrix_incomplete", self.assess(p)["blockers"])

    def test_failed_host_local_probe_is_rejected(self):
        p = fixture()
        p["attestation"]["bypass_matrix"]["host_local"] = False
        self.assertIn("bypass_matrix_incomplete", self.assess(p)["blockers"])

    def test_unknown_post_requires_durable_reconciliation(self):
        p = fixture()
        p["recovery"]["unknown_post_reconciliation"] = False
        self.assertIn("unknown_post_reconciliation_missing", self.assess(p)["blockers"])

    def test_history_gap_is_denied(self):
        p = fixture()
        p["recovery"]["complete_prompt_history"] = False
        self.assertIn("prompt_history_reconciliation_missing", self.assess(p)["blockers"])

    def test_restart_must_fail_closed(self):
        p = fixture()
        p["recovery"]["restart_blocks_until_reconciled"] = False
        self.assertIn("restart_reconciliation_missing", self.assess(p)["blockers"])

    def test_malformed_and_claimed_hash_never_grants_authority(self):
        for bad in (None, {}, {"migration": {}}, "plan"):
            self.assertIn("invalid_plan", self.assess(bad)["blockers"])
        p = fixture()
        p["attestation"]["evidence_sha"] = "fake"
        self.assertIn("independent_attestation_missing", self.assess(p)["blockers"])


if __name__ == "__main__":
    unittest.main()
