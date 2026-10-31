"""Source-only, DENY-only checklist for a proposed ComfyUI network migration.

This module neither reads a host nor attests OS controls. All input is caller
supplied and can be forged. A 'candidate_unverified' is NOT an authorization.
No sockets, subprocesses, GPU operations, network calls or filesystem writes.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

KNOWN_DIRECT_SINKS = frozenset({
    "active/worker.py",
    "worker/worker.py",
    "worker/pose_geometry_runtime.py",
    "worker/pose_reference_pipeline.py",
    "standalone-web/server.py",
    "scripts/smoke-local-repair.py",
})
BYPASS_ACTORS = frozenset({
    "worker", "pose", "reference", "web", "smoke",
    "host_local", "container_peer", "foreign",
})
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _deny(*reasons: str) -> dict[str, object]:
    return {
        "status": "blocked", "can_submit_gpu": False,
        "known_sinks": len(KNOWN_DIRECT_SINKS),
        "blockers": sorted(set(reasons) | {"source_only_not_live_authority"}),
    }


def assess_isolation_plan(plan: object) -> dict[str, object]:
    """Evaluate claimed migration completeness, never live authorization.

    This is a negative test oracle, NOT an OS verifier. Even complete,
    independent-looking evidence hashes and a fully green bypass matrix
    remain self-reported and cannot enable a real GPU submission.
    """
    if not isinstance(plan, Mapping) or not all(
        isinstance(plan.get(k), Mapping)
        for k in ("observed", "migration", "attestation", "recovery")
    ):
        return _deny("invalid_plan")

    observed = plan["observed"]
    migration = plan["migration"]
    attestation = plan["attestation"]
    recovery = plan["recovery"]
    blockers: set[str] = set()

    # Pin the actual observed 2026-10-31 rootless topology. A change in
    # this snapshot requires fresh inspection, never an inferred PASS.
    if not (
        type(observed.get("worker_uid")) is int
        and type(observed.get("comfy_uid")) is int
        and observed["worker_uid"] == observed["comfy_uid"]
        and observed.get("comfy_network_mode") == "pasta"
        and observed.get("loopback_publish") is True
        and observed.get("container_netns_separate") is True
        and observed.get("host_listener_pasta") is True
    ):
        blockers.add("observed_topology_requires_reinspection")

    sinks = migration.get("sinks")
    if not isinstance(sinks, Mapping):
        blockers.update(("known_sink_unbrokered", "sink_inventory_unverified"))
    else:
        if any(sinks.get(path) != "broker_only" for path in KNOWN_DIRECT_SINKS):
            blockers.add("known_sink_unbrokered")
        if set(sinks) != KNOWN_DIRECT_SINKS:
            blockers.add("sink_inventory_unverified")
    if (migration.get("dynamic_clients_accounted") is not True
            or migration.get("foreign_clients_accounted") is not True):
        blockers.add("unaccounted_clients")

    # A same-UID worker can reach today's host-loopback pasta socket.
    # A claimed network mode alone cannot distinguish it from the broker.
    ids = [migration.get(k) for k in ("worker_uid", "comfy_uid", "broker_uid")]
    if (any(type(uid) is not int or uid <= 0 for uid in ids)
            or len(set(ids)) != 3
            or ids[0] != observed.get("worker_uid")
            or migration.get("podman_control_separated") is not True):
        blockers.add("os_identity_boundary_missing")
    if (migration.get("host_publish_removed") is not True
            or migration.get("host_loopback_bypass_blocked") is not True
            or migration.get("comfy_private_netns") is not True):
        blockers.add("host_loopback_bypass_possible")
    if migration.get("container_peer_bypass_blocked") is not True:
        blockers.add("container_peer_bypass_possible")
    if migration.get("broker_socket_acl_enforced") is not True:
        blockers.add("broker_socket_acl_unverified")

    executor = attestation.get("executor")
    reviewer = attestation.get("reviewer")
    sha = attestation.get("evidence_sha")
    if not (
        isinstance(executor, str) and bool(executor.strip())
        and isinstance(reviewer, str) and bool(reviewer.strip())
        and executor != reviewer
        and attestation.get("independent") is True
        and isinstance(sha, str) and _SHA.fullmatch(sha)
    ):
        blockers.add("independent_attestation_missing")
    matrix = attestation.get("bypass_matrix")
    if (not isinstance(matrix, Mapping)
            or set(matrix) != BYPASS_ACTORS
            or any(matrix.get(actor) is not True for actor in BYPASS_ACTORS)):
        blockers.add("bypass_matrix_incomplete")

    if (recovery.get("durable_intent") is not True
            or recovery.get("queue_generation") is not True):
        blockers.add("durable_admission_protocol_missing")
    if recovery.get("unknown_post_reconciliation") is not True:
        blockers.add("unknown_post_reconciliation_missing")
    if recovery.get("complete_prompt_history") is not True:
        blockers.add("prompt_history_reconciliation_missing")
    if recovery.get("restart_blocks_until_reconciled") is not True:
        blockers.add("restart_reconciliation_missing")

    # Never mistake self-reported assertions for a real isolation proof.
    if blockers:
        return _deny(*blockers)
    return {
        "status": "candidate_unverified",
        "can_submit_gpu": False,
        "known_sinks": len(KNOWN_DIRECT_SINKS),
        "blockers": ["source_only_not_live_authority"],
        "unverified_live_preconditions": [
            "owner_approved_root_managed_distinct_uid_and_network_migration",
            "independent_os_namespace_and_socket_acl_attestation",
            "negative_host_and_container_peer_bypass_probes",
            "durable_atomic_submit_and_crash_reconciliation",
            "independent_visual_g2_and_labeled_g3",
        ],
    }
