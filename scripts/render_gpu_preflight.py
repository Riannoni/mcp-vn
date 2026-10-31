"""Pure, MOCKED, read-only GPU preflight policy; never submits a GPU job.

This module accepts trusted, independently gathered synthetic snapshots
for offline negative tests. It performs no I/O, no API calls, no GPU actions,
and cannot acquire a lease or atomically reserve the queue. Even an entirely
matching snapshot returns shadow_ready with can_submit_gpu=False.

Production use would require a separate reviewed governor that atomically
rechecks source/sandbox hashes, scene/version, GPU lease and Comfy queue at
the moment of submission. Neither this policy nor a passing test proves
G2 visual quality, G3 release readiness, or safe live deployment.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
MAX_QUEUE_AGE = 30
MAX_SCENE_AGE = 30
MAX_BASELINE_AGE = 120


def _id(value: object) -> bool:
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def _hash(value: object) -> bool:
    return isinstance(value, str) and bool(_HASH.fullmatch(value))


def _clock(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _recent(value: object, now: float, age: int) -> bool:
    return _clock(value) and now - age <= value <= now


def _fields(obj: object, fields: tuple[str, ...]) -> bool:
    return isinstance(obj, Mapping) and all(key in obj for key in fields)


def _deny(reason: str) -> dict[str, object]:
    return {"status": "denied", "reason": reason, "can_submit_gpu": False}


def evaluate_preflight(snapshot: object, *, now: float) -> dict[str, object]:
    """Return conservative shadow verdict; NEVER authorize a GPU operation.

    Expected keys: lease, queue, sandbox, review, scene. All are mocked
    read-only evidence, not direct probes or cryptographically signed facts.
    Missing, malformed, stale or contradictory evidence fails closed.
    """
    if not _clock(now) or not _fields(snapshot, ("lease", "queue", "sandbox",
                                                  "review", "scene")):
        return _deny("invalid_snapshot")
    lease = snapshot["lease"]
    if not _fields(lease, ("owner", "fence", "exclusive", "active_owners",
                           "expires_at")):
        return _deny("invalid_lease")
    if not _id(lease["owner"]) or not _id(lease["fence"]) or (
        lease["exclusive"] is not True or
        not isinstance(lease["active_owners"], list) or
        not all(_id(owner) for owner in lease["active_owners"]) or
        not _clock(lease["expires_at"])
    ):
        if lease["exclusive"] is False and _id(lease["owner"]) and _id(lease["fence"]):
            return _deny("lease_not_exclusive")
        return _deny("invalid_lease")
    if lease["expires_at"] <= now:
        return _deny("lease_expired")
    if lease["expires_at"] > now + 3600:
        return _deny("invalid_lease")
    if lease["active_owners"] != [lease["owner"]]:
        return _deny("competing_owner")

    queue = snapshot["queue"]
    if not _fields(queue, ("known", "running", "pending", "observed_at")):
        return _deny("queue_unknown")
    if queue["known"] is not True or not isinstance(queue["running"], list) or (
        not isinstance(queue["pending"], list)
    ):
        return _deny("queue_unknown")
    if not _recent(queue["observed_at"], now, MAX_QUEUE_AGE):
        return _deny("queue_stale")
    if queue["running"] or queue["pending"]:
        return _deny("queue_busy")

    sandbox = snapshot["sandbox"]
    fields = ("disposable", "source_game_id", "sandbox_game_id",
              "source_save_sha256", "sandbox_save_sha256",
              "baseline_source_sha256", "baseline_sandbox_sha256",
              "diff_sha256", "dirty", "observed_at")
    if not _fields(sandbox, fields) or not all(_id(sandbox[k]) for k in (
        "source_game_id", "sandbox_game_id"
    )) or not all(_hash(sandbox[k]) for k in (
        "source_save_sha256", "sandbox_save_sha256",
        "baseline_source_sha256", "baseline_sandbox_sha256", "diff_sha256"
    )) or type(sandbox["dirty"]) is not bool or (
        type(sandbox["disposable"]) is not bool
    ):
        return _deny("invalid_sandbox")
    if not sandbox["disposable"] or (
        sandbox["source_game_id"] == sandbox["sandbox_game_id"]
    ):
        return _deny("sandbox_not_disposable")
    if sandbox["dirty"]:
        return _deny("sandbox_dirty")
    if not _recent(sandbox["observed_at"], now, MAX_BASELINE_AGE):
        return _deny("sandbox_observation_stale")
    if sandbox["source_save_sha256"] != sandbox["baseline_source_sha256"]:
        return _deny("source_save_changed")
    if sandbox["sandbox_save_sha256"] != sandbox["baseline_sandbox_sha256"]:
        return _deny("sandbox_save_changed")

    review = snapshot["review"]
    if review is None or not isinstance(review, Mapping):
        return _deny("review_missing")
    fields = ("approved", "reviewer", "source_save_sha256",
              "sandbox_save_sha256", "diff_sha256", "reviewed_at")
    if not _fields(review, fields) or not _id(review["reviewer"]) or (
        not all(_hash(review[k]) for k in (
            "source_save_sha256", "sandbox_save_sha256", "diff_sha256"
        )) or not _clock(review["reviewed_at"]) or
        type(review["approved"]) is not bool
    ):
        return _deny("invalid_review")
    if not review["approved"]:
        return _deny("review_unapproved")
    if review["reviewer"] == lease["owner"]:
        return _deny("review_not_independent")
    if (review["source_save_sha256"] != sandbox["source_save_sha256"] or
        review["sandbox_save_sha256"] != sandbox["sandbox_save_sha256"] or
        review["diff_sha256"] != sandbox["diff_sha256"]):
        return _deny("review_mismatch")
    if not (_recent(review["reviewed_at"], now, MAX_BASELINE_AGE) and
            review["reviewed_at"] >= sandbox["observed_at"]):
        return _deny("review_stale")
    if queue["observed_at"] < review["reviewed_at"]:
        return _deny("queue_before_review")

    scene = snapshot["scene"]
    fields = ("expected_game_id", "current_game_id",
              "expected_version", "current_version",
              "expected_fingerprint", "current_fingerprint",
              "expected_action_id", "current_action_id",
              "expected_job_id", "current_job_id", "observed_at")
    if not _fields(scene, fields) or not all(_id(scene[k]) for k in (
        "expected_game_id", "current_game_id", "expected_action_id",
        "current_action_id", "expected_job_id", "current_job_id"
    )) or not all(_hash(scene[k]) for k in (
        "expected_fingerprint", "current_fingerprint"
    )) or not all(type(scene[k]) is int and 0 <= scene[k] < 2**53 for k in (
        "expected_version", "current_version"
    )):
        return _deny("invalid_scene")
    if not _recent(scene["observed_at"], now, MAX_SCENE_AGE) or (
        scene["observed_at"] < queue["observed_at"]
    ):
        return _deny("scene_observation_stale")
    if scene["expected_game_id"] != sandbox["sandbox_game_id"] or (
        scene["current_game_id"] != scene["expected_game_id"]
    ):
        return _deny("scene_game_changed")
    if scene["current_version"] != scene["expected_version"]:
        return _deny("scene_version_changed")
    if scene["current_fingerprint"] != scene["expected_fingerprint"]:
        return _deny("scene_fingerprint_changed")
    if scene["current_action_id"] != scene["expected_action_id"]:
        return _deny("scene_action_changed")
    if scene["current_job_id"] != scene["expected_job_id"]:
        return _deny("scene_job_changed")

    # No production authority: this snapshot can race the next GPU job.
    return {"status": "shadow_ready", "reason": "mock_metadata_consistent",
            "can_submit_gpu": False}
